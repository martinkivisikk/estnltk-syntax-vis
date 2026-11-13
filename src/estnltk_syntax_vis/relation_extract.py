"""Extraction of relation models from EstNLTK `RelationLayer`s.

Each relation becomes edges between span nodes. The words of the diagram are
the spans of a word layer; a named span covers the words it overlaps.
Sentences linked by the drawn relations form one diagram (a sentence group).
"""

from bisect import bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from estnltk import Text
from estnltk_core import RelationLayer
from estnltk_core.layer.relation_layer import Relation

from .extract import RowSpec, _layer, _row
from .relation_model import Edge, RelationModel, SpanNode

EdgeSpec = tuple[str, str, str | None]
"""An edge given by span names: `(source, target, label)`; label `None` = default."""


def target_name(relation: Relation, source: str, target: str) -> str:
    """Default edge label: the name of the target span."""
    return target


@dataclass(frozen=True)
class RelationConfig:
    hub: str | None = None
    edges: Callable[[Relation], Iterable[EdgeSpec]] | None = None
    label: str | Callable[[Relation, str, str], Any] | None = target_name
    span_names: bool = False
    hub_label: str | None = None
    attach: str = "centre"  # "centre" or "head"
    words_layer: str = "words"
    sentence_layer: str = "sentences"
    syntax_layer: str | None = None
    rows: tuple[RowSpec, ...] = ()
    ambiguous: str = "first"  # for rows
    missing: str = "-"


def _attribute(relation: Relation, attribute: str) -> str:
    """Distinct non-empty values of a relation attribute, joined with `|`."""
    values: list[str] = []
    for annotation in relation.annotations:
        value = annotation[attribute]
        if value is not None and str(value) not in values:
            values.append(str(value))
    return "|".join(values)


def _check_layer(layer: RelationLayer, config: RelationConfig) -> Text:
    if not isinstance(layer, RelationLayer):
        raise TypeError(f"expected a RelationLayer, got {type(layer).__name__}")
    if layer.text_object is None:
        raise ValueError(f"relation layer {layer.name!r} is not attached to a Text")
    if config.hub is not None and config.hub not in layer.span_names:
        raise ValueError(
            f"hub {config.hub!r} is not a span name of {layer.name!r} "
            f"(span names: {', '.join(layer.span_names)})"
        )
    for what, attribute in (("label", config.label), ("hub_label", config.hub_label)):
        if isinstance(attribute, str) and attribute not in layer.attributes:
            raise ValueError(
                f"{what} {attribute!r} is not an attribute of {layer.name!r} "
                f"(attributes: {', '.join(layer.attributes) or 'none'})"
            )
    if config.attach not in ("centre", "head"):
        raise ValueError(f"attach must be 'centre' or 'head', got {config.attach!r}")
    if config.attach == "head" and config.syntax_layer is None:
        raise ValueError("attach='head' needs a syntax_layer")
    return layer.text_object


def _hub(relation: Relation, named: dict, layer: RelationLayer, config: RelationConfig):
    """The relation's centre span: `config.hub` if filled, else its first span."""
    if config.hub is not None and config.hub in named:
        return config.hub
    return next(name for name in layer.span_names if name in named)


def _edge_specs(
    relation: Relation, named: dict, layer: RelationLayer, config: RelationConfig
) -> list[tuple[str, str, str]]:
    """Edges of a relation as `(source name, target name, label)`."""
    if config.edges is not None:
        specs = list(config.edges(relation))
    else:
        hub = _hub(relation, named, layer, config)
        specs = [(hub, name, None) for name in layer.span_names if name in named]
    result = []
    for spec in specs:
        if not (isinstance(spec, tuple) and len(spec) in (2, 3)):
            raise ValueError(
                f"edges must give (source, target) or (source, target, label), "
                f"got {spec!r}"
            )
        source, target = spec[0], spec[1]
        label = spec[2] if len(spec) == 3 else None
        for name in (source, target):
            if name not in layer.span_names:
                raise ValueError(
                    f"edge end {name!r} is not a span name of {layer.name!r}"
                )
        if source not in named or target not in named or source == target:
            continue
        if label is None:
            label = _label(relation, source, target, config)
        result.append((source, target, str(label)))
    return result


def _label(relation: Relation, source: str, target: str, config: RelationConfig) -> str:
    if config.label is None:
        return ""
    if callable(config.label):
        value = config.label(relation, source, target)
        return "" if value is None else str(value)
    return _attribute(relation, config.label)


class _Words:
    """Words of the text, their sentences and (optionally) their syntax heads."""

    def __init__(self, text: Text, config: RelationConfig):
        self.spans = list(_layer(text, config.words_layer, "Word"))
        self.starts = [w.start for w in self.spans]
        if config.sentence_layer in text.layers:
            sentences = list(text[config.sentence_layer])
            sentence_starts = [s.start for s in sentences]
            self.sentence = [
                max(bisect_right(sentence_starts, w.start) - 1, 0) for w in self.spans
            ]
        else:
            self.sentence = [0] * len(self.spans)
        self.head: list[int | None] | None = None
        if config.syntax_layer is not None:
            self.head = self._heads(text, config.syntax_layer)

    def _heads(self, text: Text, name: str) -> list[int | None]:
        """Head word index of each word (`None` for roots and unknown words)."""
        syntax = _layer(text, name, "Syntax")
        missing = [a for a in ("id", "head") if a not in syntax.attributes]
        if missing:
            raise ValueError(
                f"syntax layer {name!r} lacks the attribute(s) {', '.join(missing)}"
            )
        index = {(w.start, w.end): i for i, w in enumerate(self.spans)}
        info = {}  # word index -> (id, head)
        by_id = {}  # (sentence, id) -> word index
        for span in syntax:
            i = index.get((span.start, span.end))
            if i is None:
                continue
            annotation = span.annotations[0]
            info[i] = (annotation["id"], annotation["head"])
            by_id[(self.sentence[i], annotation["id"])] = i
        heads: list[int | None] = []
        for i in range(len(self.spans)):
            if i not in info or info[i][1] in (0, None):
                heads.append(None)
            else:
                heads.append(by_id.get((self.sentence[i], info[i][1])))
        return heads

    def covered(self, named_span) -> tuple[int, int]:
        """Word range `(first, last + 1)` of the words a named span overlaps."""
        hits = []
        for start, end in named_span.base_span.flatten():
            k = max(bisect_right(self.starts, start) - 1, 0)
            while k < len(self.spans) and self.spans[k].start < end:
                if start < self.spans[k].end:
                    hits.append(k)
                k += 1
        if not hits:
            raise ValueError(
                f"span {named_span.name!r} ({named_span.text!r}) covers no word of "
                f"the word layer"
            )
        return min(hits), max(hits) + 1

    def head_of(self, start: int, end: int) -> int:
        """First word of `start .. end - 1` whose syntactic head is outside it."""
        assert self.head is not None
        for i in range(start, end):
            head = self.head[i]
            if head is None or not start <= head < end:
                return i
        return start


def _relations(layer: RelationLayer, selection, what: str) -> list[Relation]:
    """Relations of `layer` given as a Relation or an iterable of them."""
    items = [selection] if isinstance(selection, Relation) else list(selection)
    for item in items:
        if not isinstance(item, Relation):
            raise ValueError(f"{what} must be a Relation or Relations, got {item!r}")
        if not any(item is r for r in layer.relations):
            raise ValueError(
                f"{what} contains a relation that is not in {layer.name!r}"
            )
    return items


def _groups(sentence_sets: list[set[int]]) -> list[set[int]]:
    """Merge sentence sets that share a sentence; ordered by first sentence."""
    groups: list[set[int]] = []
    for sentences in sentence_sets:
        joined = set(sentences)
        rest = []
        for group in groups:
            if group & joined:
                joined |= group
            else:
                rest.append(group)
        groups = [*rest, joined]
    return sorted(groups, key=min)


def extract_relations(
    layer: RelationLayer,
    config: RelationConfig,
    sentence: int | None = None,
    relation=None,
    highlight=None,
) -> list[tuple[tuple[int, ...], RelationModel]]:
    """Relation models of `layer` as `(sentence indices, model)` pairs.

    One model per sentence group: sentences linked by the drawn relations
    (`relation`, or all relations of the layer). `sentence` keeps only the group
    that contains that sentence; `highlight` (Relations) emphasises relations
    and, without `sentence`, keeps only the groups that contain them.
    """
    text = _check_layer(layer, config)
    words = _Words(text, config)
    drawn = (
        list(layer.relations)
        if relation is None
        else _relations(layer, relation, "relation")
    )
    marked = [] if highlight is None else _relations(layer, highlight, "highlight")
    for item in marked:
        if not any(item is r for r in drawn):
            raise ValueError("highlight contains a relation that is not drawn")

    # Relations as edges between word ranges, with their sentences
    parsed = []  # (relation, {name: (start, end)}, [(source, target, label)], hub)
    for rel in drawn:
        named = {span.name: span for span in rel.spans}
        if not named:
            continue
        ranges = {name: words.covered(span) for name, span in named.items()}
        specs = _edge_specs(rel, named, layer, config)
        parsed.append((rel, ranges, specs, _hub(rel, named, layer, config)))
    n_sentences = max(words.sentence, default=0) + 1
    sentence_sets = [
        {words.sentence[i] for start, end in ranges.values() for i in (start, end - 1)}
        for _, ranges, _, _ in parsed
    ]
    groups = _groups(sentence_sets)

    if sentence is not None:
        if not -n_sentences <= sentence < n_sentences:
            raise ValueError(
                f"sentence {sentence} is out of range (the Text has {n_sentences})"
            )
        sentence %= n_sentences
        groups = [g for g in groups if sentence in g] or [{sentence}]
    elif marked:
        marked_sentences = {
            s
            for (rel, _, _, _), sentences in zip(parsed, sentence_sets, strict=True)
            if any(rel is m for m in marked)
            for s in sentences
        }
        groups = [g for g in groups if g & marked_sentences]

    models = []
    for group in groups:
        members = [
            p
            for p, sentences in zip(parsed, sentence_sets, strict=True)
            if sentences <= group
        ]
        models.append(
            (tuple(sorted(group)), _model(text, words, group, members, marked, config))
        )
    return models


def _model(
    text, words: _Words, group: set[int], members, marked, config
) -> RelationModel:
    in_group = [i for i, s in enumerate(words.sentence) if s in group]
    lo, hi = in_group[0], in_group[-1] + 1
    nodes: dict[tuple[int, int, int | None], dict] = {}
    edges: dict[tuple, bool] = {}  # (source key, target key, label) -> highlight

    def node(start: int, end: int) -> tuple[int, int, int | None]:
        anchor = words.head_of(start, end) - lo if config.attach == "head" else None
        key = (start - lo, end - lo, anchor)
        nodes.setdefault(key, {"labels": [], "highlight": False})
        return key

    for rel, ranges, specs, hub in members:
        highlighted = any(rel is m for m in marked)
        keys = {name: node(*r) for name, r in ranges.items()}
        for name, key in keys.items():
            labels = nodes[key]["labels"]
            parts = []
            if config.span_names:
                parts.append(name)
            if config.hub_label is not None and name == hub:
                value = _attribute(rel, config.hub_label)
                if value:
                    parts.append(value)
            for part in parts:
                if part not in labels:
                    labels.append(part)
            nodes[key]["highlight"] |= highlighted
        for source, target, label in specs:
            if keys[source] == keys[target]:
                continue
            edge_key = (keys[source], keys[target], label)
            edges[edge_key] = edges.get(edge_key, False) or highlighted

    order = sorted(nodes)
    index = {key: k for k, key in enumerate(order)}
    span_words = words.spans[lo:hi]
    visible = frozenset(i - lo for i in in_group)
    return RelationModel(
        words=tuple(w.text for w in span_words),
        nodes=tuple(
            SpanNode(
                key[0],
                key[1],
                ", ".join(nodes[key]["labels"]),
                key[2],
                nodes[key]["highlight"],
            )
            for key in order
        ),
        edges=tuple(
            Edge(index[s], index[t], label, highlight)
            for (s, t, label), highlight in edges.items()
        ),
        rows=tuple(_row(text, spec, span_words, config) for spec in config.rows),
        visible=None if len(visible) == hi - lo else visible,
    )

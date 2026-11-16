"""Extraction of sentence models from EstNLTK `Text` objects.

Words are the spans of the syntax layer. Other layers (rows, boxes, highlight)
are matched to them by text position, so they only need to cover the same words,
not be the same layer object.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from estnltk import Span, Text

from .model import Box, Row, SentenceModel

SYNTAX_ATTRIBUTES = ("id", "head", "deprel")

RowSpec = tuple[str, str] | tuple[str, Callable[[Any], Any]] | Callable[[Any], Any]
"""A row under the words: `(layer, attribute)`, `(label, function)` or `function`.

Functions get the word's span of the syntax layer and return the value to show.
"""

Highlight = Any  # a span, an iterable of spans, or an iterable of word indices


@dataclass(frozen=True)
class ExtractionConfig:
    syntax_layer: str = "stanza_syntax"
    sentence_layer: str = "sentences"
    rows: tuple[RowSpec, ...] = ()
    overlay_layer: str | None = None
    overlay_label: str | None = None
    ambiguous: str = "first"  # rows only: "first" or "all" annotations
    missing: str = "-"  # shown for a missing span or value


def _layer(text: Text, name: str, what: str):
    if name not in text.layers:
        available = ", ".join(sorted(text.layers)) or "none"
        raise ValueError(
            f"{what} layer {name!r} is missing from the Text (layers: {available})"
        )
    return text[name]


def _positions(span: Span) -> list[tuple[int, int]]:
    """Text positions of the elementary parts a span covers.

    Read from the base span: attribute lookups on a `Span` (`span.spans`,
    `hasattr`) fall back to layers of the `Text` with the same name.
    """
    return list(span.base_span.flatten())


def _is_span(obj) -> bool:
    return isinstance(obj, Span)  # also `EnvelopingSpan`


class _SentenceIndex:
    """Positions of the sentences and syntax words of a `Text`."""

    def __init__(self, text: Text, config: ExtractionConfig):
        syntax = _layer(text, config.syntax_layer, "Syntax")
        missing = [a for a in SYNTAX_ATTRIBUTES if a not in syntax.attributes]
        if missing:
            raise ValueError(
                f"syntax layer {config.syntax_layer!r} lacks the attribute(s) "
                f"{', '.join(missing)}"
            )
        self.sentences = list(_layer(text, config.sentence_layer, "Sentence"))
        self.sentence_starts = [s.start for s in self.sentences]
        self.words = list(syntax)
        self.word_starts = [w.start for w in self.words]

    def words_of(self, k: int) -> list:
        sentence = self.sentences[k]
        lo = bisect_left(self.word_starts, sentence.start)
        hi = bisect_left(self.word_starts, sentence.end)
        return self.words[lo:hi]

    def sentence_of(self, start: int, end: int) -> int:
        """Index of the sentence that contains the text range `start .. end`."""
        k = bisect_right(self.sentence_starts, start) - 1
        if k < 0 or end > self.sentences[k].end:
            raise ValueError(
                f"text range {start}..{end} does not lie inside a single sentence"
            )
        return k


def _value(
    span, attribute: str, config: ExtractionConfig, ambiguous: str | None = None
) -> str:
    """The attribute's value, or distinct values joined with `|`.

    `ambiguous` overrides `config.ambiguous`; overlay labels pass `"all"`.
    """
    if span is None:
        return config.missing
    values = []
    for annotation in span.annotations:
        value = annotation[attribute]
        if value is not None and str(value) not in values:
            values.append(str(value))
    if not values:
        return config.missing
    mode = ambiguous or config.ambiguous
    return values[0] if mode == "first" else "|".join(values)


def _row(text: Text, spec: RowSpec, words: list, config: ExtractionConfig) -> Row:
    if callable(spec):
        label, function = getattr(spec, "__name__", ""), spec
    elif isinstance(spec, tuple) and len(spec) == 2 and callable(spec[1]):
        label, function = spec
    elif isinstance(spec, tuple) and len(spec) == 2:
        layer_name, attribute = spec
        layer = _layer(text, layer_name, "Row")
        if attribute not in layer.attributes:
            raise ValueError(f"layer {layer_name!r} has no attribute {attribute!r}")
        values = [_value(layer.get(w.base_span), attribute, config) for w in words]
        return Row(attribute, tuple(values))
    else:
        raise ValueError(
            f"a row must be (layer, attribute), (label, function) or a function, "
            f"got {spec!r}"
        )
    values = []
    for word in words:
        value = function(word)
        values.append(config.missing if value is None else str(value))
    return Row(label, tuple(values))


def _covered(words: list, start: int, end: int) -> tuple[int, int] | None:
    """Word range `(first, end)` of the words fully inside `start .. end`."""
    if not words or end <= words[0].start or start >= words[-1].end:
        return None
    inside = [i for i, w in enumerate(words) if start <= w.start and w.end <= end]
    if not inside:
        return None
    return inside[0], inside[-1] + 1


def _check_label(layer, config: ExtractionConfig) -> None:
    label = config.overlay_label
    if label is not None and label not in layer.attributes:
        raise ValueError(
            f"layer {config.overlay_layer!r} has no attribute {label!r} "
            f"(attributes: {', '.join(layer.attributes) or 'none'})"
        )


def _boxes(text: Text, words: list, config: ExtractionConfig) -> tuple[Box, ...]:
    if config.overlay_layer is None:
        return ()
    if config.overlay_layer in text.relation_layers:
        return _relation_boxes(text[config.overlay_layer], words, config)
    layer = _layer(text, config.overlay_layer, "Overlay")
    _check_label(layer, config)
    boxes = []
    for span in layer:
        covered = _covered(words, span.start, span.end)
        if covered is None:
            continue
        label = (
            ""
            if config.overlay_label is None
            else _value(span, config.overlay_label, config, ambiguous="all")
        )
        boxes.append(Box(*covered, label))
    return tuple(boxes)


def _relation_boxes(layer, words: list, config: ExtractionConfig) -> tuple[Box, ...]:
    """One box per filled named span of each relation, labelled `name (index)`.

    The index is the relation's position in the layer, as in
    `RelationLayer.display()`. `overlay_label` (a relation attribute) is shown as
    a second line, with all distinct values of an ambiguous relation.
    """
    _check_label(layer, config)
    boxes = []
    for index, relation in enumerate(layer):
        detail = (
            ""
            if config.overlay_label is None
            else _value(relation, config.overlay_label, config, ambiguous="all")
        )
        for named in relation.spans:
            covered = _covered(words, named.start, named.end)
            if covered is None:
                continue
            boxes.append(
                Box(*covered, f"{named.name} ({index})", detail, relation=index)
            )
    return tuple(boxes)


def _model(text: Text, index: _SentenceIndex, k: int, config: ExtractionConfig):
    words = index.words_of(k)
    position = {}
    for i, word in enumerate(words):
        word_id = word.annotations[0]["id"]
        if word_id in position:
            raise ValueError(f"sentence {k} has two words with id {word_id!r}")
        position[word_id] = i
    heads: list[int | None] = []
    for word in words:
        head = word.annotations[0]["head"]
        if head == 0:
            heads.append(None)
        elif head in position:
            heads.append(position[head])
        else:
            raise ValueError(
                f"head {head!r} of word {word.text!r} (sentence {k}) is not the id "
                f"of a word in the same sentence"
            )
    return SentenceModel(
        words=tuple(w.text for w in words),
        heads=tuple(heads),
        deprels=tuple(str(w.annotations[0]["deprel"]) for w in words),
        rows=tuple(_row(text, spec, words, config) for spec in config.rows),
        boxes=_boxes(text, words, config),
    )


def _highlight_words(
    highlight: Highlight, index: _SentenceIndex, sentence: int | None
) -> tuple[int, frozenset[int]]:
    """Resolve a highlight to `(sentence, word indices in that sentence)`."""
    items = [highlight] if _is_span(highlight) else list(highlight)
    if not items:
        raise ValueError("highlight is empty")
    if all(isinstance(i, int) for i in items):
        if sentence is None:
            raise ValueError("give `sentence` when the highlight is word indices")
        n = len(index.words_of(sentence))
        if any(not 0 <= i < n for i in items):
            raise ValueError(f"highlight indices must be in 0..{n - 1}")
        return sentence, frozenset(items)
    if not all(_is_span(i) for i in items):
        raise ValueError("highlight must be a span, spans or word indices")

    positions = [p for item in items for p in _positions(item)]
    found = index.sentence_of(
        min(s for s, _ in positions), max(e for _, e in positions)
    )
    if sentence is not None and sentence != found:
        raise ValueError(f"the highlight is in sentence {found}, not in {sentence}")
    words = index.words_of(found)
    chosen = frozenset(
        i
        for i, w in enumerate(words)
        if any(s <= w.start and w.end <= e for s, e in positions)
    )
    if not chosen:
        raise ValueError("the highlight covers no word of the syntax layer")
    return found, chosen


def extract(
    text: Text,
    config: ExtractionConfig,
    sentence: int | None = None,
    highlight: Highlight = None,
) -> list[tuple[int, SentenceModel]]:
    """Sentence models of `text` as `(sentence index, model)` pairs.

    Without `sentence` and `highlight` all sentences are returned; otherwise
    only the given sentence or the one that contains the highlight.
    """
    index = _SentenceIndex(text, config)
    n = len(index.sentences)
    if sentence is not None and not -n <= sentence < n:
        raise ValueError(f"sentence {sentence} is out of range (the Text has {n})")
    if sentence is not None:
        sentence %= n
    chosen: frozenset[int] = frozenset()
    if highlight is not None:
        sentence, chosen = _highlight_words(highlight, index, sentence)
    indices: Sequence[int] = range(n) if sentence is None else [sentence]
    models = []
    for k in indices:
        model = _model(text, index, k, config)
        if chosen:
            model = replace(model, highlight=chosen)
        models.append((k, model))
    return models

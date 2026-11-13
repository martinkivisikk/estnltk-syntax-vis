from estnltk_syntax_vis import SentenceModel


def make(words: str, heads: list[int], deprels: list[str] | None = None, **kw):
    """Sentence model from 1-based CoNLL-style heads (0 = root)."""
    tokens = tuple(words.split())
    return SentenceModel(
        tokens,
        tuple(None if h == 0 else h - 1 for h in heads),
        tuple(deprels or ["dep"] * len(tokens)),
        **kw,
    )


def make_text(
    raw: str,
    trees: list[tuple[list[int], list[str]]],
    layer: str = "stanza_syntax",
    extra_layers: tuple[str, ...] = (),
):
    """`Text` with words, sentences and a hand-made syntax layer.

    `trees` gives `(heads, deprels)` per sentence, heads 1-based (0 = root) as
    in CoNLL-U; the syntax layer gets `id`, `head` and `deprel`.
    """
    from estnltk import Layer, Text

    text = Text(raw).tag_layer(["words", "sentences"])
    sentences = list(text.sentences)
    assert len(sentences) == len(trees), [s.text for s in sentences]
    syntax = Layer(
        layer, attributes=("id", "head", "deprel"), text_object=text, parent="words"
    )
    for sentence, (heads, deprels) in zip(sentences, trees, strict=True):
        words = [w for w in text.words if sentence.start <= w.start < sentence.end]
        assert len(words) == len(heads) == len(deprels), [w.text for w in words]
        for i, (word, head, deprel) in enumerate(
            zip(words, heads, deprels, strict=True), 1
        ):
            syntax.add_annotation(word, id=i, head=head, deprel=deprel)
    text.add_layer(syntax)
    if extra_layers:
        text.tag_layer(list(extra_layers))
    return text


def find(raw: str, part: str, nth: int = 0) -> tuple[int, int]:
    """Position of the `nth` occurrence (0-based) of `part` in `raw`."""
    start = -1
    for _ in range(nth + 1):
        start = raw.index(part, start + 1)
    return start, start + len(part)


def add_relations(
    text,
    name: str,
    span_names: list[str],
    relations: list[dict],
    attributes: tuple[str, ...] = (),
    ambiguous: bool = False,
):
    """Add a RelationLayer to `text` and return it.

    Each relation is a dict from span names to substrings (or `(substring, nth)`)
    and from attribute names to values; for ambiguous layers an attribute value
    may be a list, which gives one annotation per value.
    """
    from estnltk_core import RelationLayer

    layer = RelationLayer(
        name,
        span_names=span_names,
        attributes=attributes,
        ambiguous=ambiguous,
        text_object=text,
    )
    for relation in relations:
        spans = {
            k: find(text.text, *(v if isinstance(v, tuple) else (v,)))
            for k, v in relation.items()
            if k in span_names
        }
        values = {k: v for k, v in relation.items() if k in attributes}
        lists = {k: v for k, v in values.items() if isinstance(v, list)}
        first = {k: (v[0] if isinstance(v, list) else v) for k, v in values.items()}
        layer.add_annotation({**spans, **first})
        for j in range(1, max((len(v) for v in lists.values()), default=0)):
            layer[-1].add_annotation(
                {k: (v[j] if isinstance(v, list) else v) for k, v in values.items()}
            )
    text.add_layer(layer)
    return layer

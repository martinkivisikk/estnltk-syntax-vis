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

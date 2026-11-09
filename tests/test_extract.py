import pytest
from estnltk import Layer
from helpers import make_text

from estnltk_syntax_vis.extract import ExtractionConfig, extract

RAW = "Alar Karis kohtus eile Tallinnas Soome peaministriga. Ta naasis Tartusse."
TREES = [
    ([3, 1, 0, 3, 3, 7, 3, 3], "nsubj flat root advmod obl nmod obl punct".split()),
    ([2, 0, 2, 2], "nsubj root obl punct".split()),
]


@pytest.fixture(scope="module")
def text():
    """Two sentences with morph_analysis and ner from EstNLTK."""
    return make_text(RAW, TREES, extra_layers=("morph_analysis", "ner"))


@pytest.fixture
def plain():
    return make_text(RAW, TREES)


def models(text, sentence=None, highlight=None, **config):
    return [
        m for _, m in extract(text, ExtractionConfig(**config), sentence, highlight)
    ]


def test_all_sentences_with_restarting_ids(plain):
    first, second = models(plain)
    assert first.words[:3] == ("Alar", "Karis", "kohtus")
    assert first.heads == (2, 0, None, 2, 2, 6, 2, 2)
    assert second.words == ("Ta", "naasis", "Tartusse", ".")
    assert second.heads == (1, None, 1, 1)
    assert second.deprels == ("nsubj", "root", "obl", "punct")


def test_non_default_layer_names():
    text = make_text(RAW, TREES, layer="v172_stanza_syntax")
    (model,) = models(text, sentence=1, syntax_layer="v172_stanza_syntax")
    assert model.words == ("Ta", "naasis", "Tartusse", ".")


def test_sentence_index_negative(plain):
    (model,) = models(plain, sentence=-1)
    assert model.words[0] == "Ta"


def test_missing_layers_and_attributes(plain):
    with pytest.raises(ValueError, match="'other_syntax' is missing"):
        models(plain, syntax_layer="other_syntax")
    with pytest.raises(ValueError, match="Sentence layer"):
        models(plain, sentence_layer="v1_sentences")
    with pytest.raises(ValueError, match="Row layer"):
        models(plain, rows=(("morph_analysis", "partofspeech"),))
    with pytest.raises(ValueError, match="lacks the attribute"):
        models(plain, syntax_layer="words")
    with pytest.raises(ValueError, match="out of range"):
        models(plain, sentence=2)


def test_head_outside_sentence():
    text = make_text("Ta laulab.", [([2, 0, 9], ["nsubj", "root", "punct"])])
    with pytest.raises(ValueError, match="head 9"):
        models(text)


def test_rows_from_ambiguous_layer(text):
    rows = (("morph_analysis", "partofspeech"), ("morph_analysis", "form"))
    (first,) = models(text, sentence=0, rows=rows)
    assert [r.label for r in first.rows] == ["partofspeech", "form"]
    assert first.rows[0].values[:3] == ("H", "H", "V")


def test_ambiguous_first_or_all(plain):
    layer = Layer(
        "amb",
        attributes=("pos", "form"),
        text_object=plain,
        parent="words",
        ambiguous=True,
    )
    word = plain.words[0].base_span
    layer.add_annotation(word, pos="S", form="sg n")
    layer.add_annotation(word, pos="V", form="sg n")
    layer.add_annotation(word, pos="S", form="pl n")
    plain.add_layer(layer)
    rows = (("amb", "pos"), ("amb", "form"))
    (first,) = models(plain, sentence=0, rows=rows)
    assert [r.values[0] for r in first.rows] == ["S", "sg n"]
    # "all" joins the distinct values in annotation order
    (every,) = models(plain, sentence=0, rows=rows, ambiguous="all")
    assert [r.values[0] for r in every.rows] == ["S|V", "sg n|pl n"]


def test_rows_from_functions_and_syntax_layer(plain):
    def length(span):
        return len(span.text)

    rows = (length, ("upper", lambda s: s.text.upper()), ("stanza_syntax", "id"))
    (model,) = models(plain, sentence=1, rows=rows)
    assert model.rows[0].label == "length"
    assert model.rows[0].values == ("2", "6", "8", "1")
    assert model.rows[1].values == ("TA", "NAASIS", "TARTUSSE", ".")
    assert model.rows[2].values == ("1", "2", "3", "4")


def test_row_missing_values(plain):
    layer = Layer("extra", attributes=("tag",), text_object=plain, parent="words")
    layer.add_annotation(plain.words[0].base_span, tag="X")
    layer.add_annotation(plain.words[1].base_span, tag=None)
    plain.add_layer(layer)
    (model,) = models(plain, sentence=0, rows=(("extra", "tag"),), missing="?")
    assert model.rows[0].values[:3] == ("X", "?", "?")


def test_invalid_row_spec(plain):
    with pytest.raises(ValueError, match="a row must be"):
        models(plain, rows=("morph_analysis",))


def test_boxes_from_span_layer(text):
    first, second = models(text, span_layer="ner", span_label="nertag")
    labels = {(b.start, b.end): b.label for b in first.boxes}
    assert labels[(0, 2)] == "PER"
    assert labels[(4, 5)] == "LOC"
    assert [(b.start, b.end, b.label) for b in second.boxes] == [(2, 3, "LOC")]
    (unlabelled,) = models(text, sentence=0, span_layer="ner")
    assert {b.label for b in unlabelled.boxes} == {""}


def test_highlight_span_finds_sentence(text):
    ((k, model),) = extract(text, ExtractionConfig(), highlight=text.ner[0])
    assert k == 0
    assert model.highlight == {0, 1}
    ((k, model),) = extract(text, ExtractionConfig(), highlight=text.ner[-1])
    assert (k, model.highlight) == (1, {2})


def test_highlight_spans_and_indices(text):
    words = list(text.words)
    (model,) = models(text, highlight=[words[0], words[2]])
    assert model.highlight == {0, 2}
    (model,) = models(text, highlight=text.words[9:11])  # a slice of a layer
    assert model.highlight == {1, 2}
    (model,) = models(text, sentence=1, highlight=[0, 3])
    assert model.highlight == {0, 3}


def test_highlight_errors(text):
    with pytest.raises(ValueError, match="give `sentence`"):
        models(text, highlight=[0])
    with pytest.raises(ValueError, match="0..3"):
        models(text, sentence=1, highlight=[4])
    with pytest.raises(ValueError, match="single sentence"):
        models(text, highlight=text.words[6:9])
    with pytest.raises(ValueError, match="not in 0"):
        models(text, sentence=0, highlight=text.ner[-1])
    with pytest.raises(ValueError, match="empty"):
        models(text, highlight=[])

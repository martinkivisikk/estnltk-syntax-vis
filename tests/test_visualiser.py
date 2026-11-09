import xml.etree.ElementTree as ET

import pytest
from helpers import make_text

import estnltk_syntax_vis.visualiser as visualiser_module
from estnltk_syntax_vis import DependencyTreeVisualiser

RAW = "Alar Karis kohtus eile Tallinnas. Ta naasis Tartusse."
TREES = [
    ([3, 1, 0, 3, 3, 3], "nsubj flat root advmod obl punct".split()),
    ([2, 0, 2, 2], "nsubj root obl punct".split()),
]


@pytest.fixture(scope="module")
def text():
    return make_text(RAW, TREES, extra_layers=("morph_analysis", "ner"))


@pytest.fixture
def vis():
    return DependencyTreeVisualiser(
        rows=[("morph_analysis", "partofspeech")], span_layer="ner", span_label="nertag"
    )


def words(svg):
    root = ET.fromstring(svg)
    return [e.text for e in root.iter() if e.get("class") == "word"]


def test_svg_of_one_sentence(text, vis):
    assert words(vis.svg(text, sentence=1)) == ["Ta", "naasis", "Tartusse", "."]


def test_svg_needs_sentence_for_multi_sentence_text(text, vis):
    with pytest.raises(ValueError, match="2 sentences"):
        vis.svg(text)
    single = make_text("Ta laulab.", [([2, 0, 2], ["nsubj", "root", "punct"])])
    assert words(DependencyTreeVisualiser().svg(single)) == ["Ta", "laulab", "."]


def test_fragment_with_window(text, vis):
    svg = vis.svg(text, highlight=text.ner[0], window=0)
    assert words(svg) == ["Alar", "Karis", "kohtus"]


def test_html_output_has_all_sentences(text, vis):
    html = vis.html_output(text)
    assert html.count("<svg") == 2
    assert vis.html_output(text, highlight=text.ner[0]).count("<svg") == 1


def test_call_displays_html(text, vis, monkeypatch):
    shown = []
    monkeypatch.setattr(
        visualiser_module, "display_html", lambda html, raw: shown.append((html, raw))
    )
    vis(text)
    assert len(shown) == 1 and shown[0][1] is True
    assert shown[0][0].count("<svg") == 2


def test_invalid_ambiguous_option():
    with pytest.raises(ValueError, match="ambiguous"):
        DependencyTreeVisualiser(ambiguous="last")

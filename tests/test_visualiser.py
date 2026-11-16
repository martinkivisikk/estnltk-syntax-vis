import base64
import re
import xml.etree.ElementTree as ET

import pytest
from helpers import add_relations, make_text

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
        rows=[("morph_analysis", "partofspeech")],
        overlay_layer="ner",
        overlay_label="nertag",
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


def test_html_output_scrolls_instead_of_shrinking(text, vis):
    # JupyterLab's `svg { max-width: 100% }` would scale wide diagrams down
    html = vis.html_output(text)
    assert html.count('<svg style="max-width:none" ') == 2
    assert html.count('<div style="overflow-x:auto') == 2
    # svg() output stays a plain SVG
    assert "max-width" not in vis.svg(text, sentence=0)


def test_render_svg_as_img(text):
    vis = DependencyTreeVisualiser(overlay_layer="ner", render_svg_as_img=True)
    html = vis.html_output(text)
    assert "<svg" not in html
    uris = re.findall(r'<img src="data:image/svg\+xml;base64,([^"]+)" ', html)
    assert len(uris) == 2
    assert html.count('style="max-width:none"') == 2
    # each data URI decodes back to exactly the plain SVG
    decoded = [base64.b64decode(u).decode("utf-8") for u in uris]
    assert decoded == vis.svgs(text)
    assert vis.svg(text, sentence=0).startswith("<svg")


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


def test_relation_layer_overlay():
    text = make_text(RAW, TREES)
    add_relations(
        text,
        "coreference",
        ["mention", "entity"],
        [
            {"mention": ("Ta", 1), "entity": "Alar Karis", "kind": "pronoun"},
            {"mention": "Tallinnas", "entity": "Tallinnas", "kind": "self"},
        ],
        attributes=("kind",),
    )
    vis = DependencyTreeVisualiser(overlay_layer="coreference", overlay_label="kind")
    first, second = (ET.fromstring(svg) for svg in vis.svgs(text))

    def texts(root, cls):
        return sorted(e.text for e in root.iter() if e.get("class") == cls)

    # the relation across sentences shows its span in each sentence, same index
    assert texts(first, "box-label") == ["entity (0)", "entity (1)", "mention (1)"]
    assert texts(second, "box-label") == ["mention (0)"]
    assert texts(first, "box-detail") == ["pronoun", "self", "self"]
    # two identical boxes over "Tallinnas" are stacked in two lanes
    lanes = [e.get("data-lane") for e in first.iter() if e.get("class") == "box"]
    assert sorted(lanes) == ["0", "0", "1"]

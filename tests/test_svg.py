import xml.etree.ElementTree as ET

from helpers import make

from estnltk_syntax_vis import Box, Row, render_svg

NS = {"svg": "http://www.w3.org/2000/svg"}


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def classes(root, name):
    return [e for e in root.iter() if name in (e.get("class") or "").split()]


def test_valid_xml_and_counts(simple):
    root = parse(render_svg(simple))
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert len(classes(root, "word")) == 4
    arcs = [e for e in classes(root, "arc") if "root" not in e.get("class")]
    assert len(arcs) == 3
    assert len(classes(root, "root")) == 1
    labels = [e.find("svg:text", NS).text for e in classes(root, "label")]
    assert sorted(labels) == ["nsubj", "obl", "punct"]


def test_text_is_escaped():
    s = make("<a> & b", [3, 3, 0], ["x<y", "&", "root"])
    root = parse(render_svg(s))
    assert [e.text for e in classes(root, "word")] == ["<a>", "&", "b"]


def test_rows_boxes_highlight():
    s = make(
        "Alar Karis elab Tallinnas",
        [3, 1, 0, 3],
        ["nsubj", "flat", "root", "obl"],
        rows=(Row("pos", ("H", "H", "V", "H")),),
        boxes=(Box(0, 2, "PER"), Box(3, 4, "LOC")),
        highlight=frozenset({0, 1}),
    )
    root = parse(render_svg(s))
    assert [e.text for e in classes(root, "row")] == ["H", "H", "V", "H"]
    assert [e.text for e in classes(root, "row-label")] == ["pos"]
    assert [e.text for e in classes(root, "box-label")] == ["PER", "LOC"]
    assert len(classes(root, "box")) == 2
    assert len(classes(root, "highlight-box")) == 1
    inner = [e for e in classes(root, "arc") if "highlight" in e.get("class")]
    context = [e for e in classes(root, "arc") if "context" in e.get("class")]
    assert [(e.get("data-head"), e.get("data-dependent")) for e in inner] == [
        ("0", "1")
    ]
    assert [(e.get("data-head"), e.get("data-dependent")) for e in context] == [
        ("2", "0")
    ]


def test_single_word():
    root = parse(render_svg(make("Tere", [0], ["root"])))
    assert len(classes(root, "root")) == 1


def test_window_draws_gaps_and_clips_boxes():
    s = make(
        "Eesti Vabariigi president Alar Karis kohtus",
        [2, 3, 6, 3, 4, 0],
        boxes=(Box(0, 2, "LOC"), Box(3, 5, "PER")),
        visible=frozenset({1, 2, 5}),
    )
    root = parse(render_svg(s))
    words = [e.text for e in classes(root, "word")]
    assert words == ["Vabariigi", "president", "kohtus"]
    assert len(classes(root, "gap")) == 2  # before Vabariigi, before kohtus
    assert [e.text for e in classes(root, "box-label")] == ["LOC"]  # PER is hidden

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


def _rect(e):
    x, y = float(e.get("x")), float(e.get("y"))
    return x, y, x + float(e.get("width")), y + float(e.get("height"))


def test_overlapping_boxes_stack_their_labels():
    words = "Tartu Ülikooli rektor Toomas Asser kohtus"
    heads = [2, 3, 6, 3, 4, 0]
    nested = (Box(0, 2, "ORG"), Box(2, 5, "PER+TITLE"), Box(3, 5, "PER"))
    root = parse(render_svg(make(words, heads, boxes=nested)))
    y = {e.text: float(e.get("y")) for e in classes(root, "box-label")}
    # the inner PER label is above the outer PER+TITLE label; ORG overlaps
    # neither, so it shares the first label line with PER
    assert y["PER"] < y["PER+TITLE"]
    assert y["ORG"] == y["PER"]
    lanes = {e.get("data-lane") for e in classes(root, "box")}
    assert lanes == {"0", "1"}
    boxes = [_rect(e) for e in classes(root, "box")]
    per_title = max(boxes, key=lambda r: r[3])  # the outer box reaches lowest
    per = [r for r in boxes if r[0] > per_title[0] and r[2] < per_title[2]]
    # exactly one box (PER) lies inside PER+TITLE, inset, and ends above it
    assert len(per) == 1 and per[0][3] < per_title[3]
    # semi-transparent fills, so overlapping regions get darker
    assert all(e.get("fill-opacity") for e in classes(root, "box"))
    # the stacked label line makes the diagram taller
    flat = parse(render_svg(make(words, heads, boxes=nested[:2])))
    assert float(root.get("height")) > float(flat.get("height"))


def test_relation_box_has_detail_line():
    box = Box(0, 2, "subject (3)", "meet", relation=3)
    root = parse(render_svg(make("Alar Karis kohtus", [3, 1, 0], boxes=(box,))))
    (label,) = classes(root, "box-label")
    (detail,) = classes(root, "box-detail")
    assert (label.text, detail.text) == ("subject (3)", "meet")
    assert float(detail.get("y")) > float(label.get("y"))
    (rect,) = classes(root, "box")
    assert rect.get("data-relation") == "3"

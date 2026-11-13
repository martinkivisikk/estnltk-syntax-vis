"""Relation model, layout and SVG on plain data."""

import xml.etree.ElementTree as ET

import pytest

from estnltk_syntax_vis import (
    Edge,
    RelationModel,
    Row,
    SpanNode,
    relation_window,
    render_relation_svg,
)
from estnltk_syntax_vis.relation_layout import node_lanes, relation_layout
from estnltk_syntax_vis.style import Style

NS = {"svg": "http://www.w3.org/2000/svg"}
WORDS = tuple("President Bush kohtus temaga Valges Majas teisipäeval .".split())


def roles(**kw) -> RelationModel:
    """Star from `kohtus` to three arguments; `Majas` nested in `Valges Majas`."""
    nodes = (
        SpanNode(2, 3, "kohtumine"),
        SpanNode(0, 2),
        SpanNode(3, 4),
        SpanNode(4, 6),
        SpanNode(5, 6),
    )
    edges = (Edge(0, 1, "arg0"), Edge(0, 2, "arg1"), Edge(0, 3, "argm_loc"))
    return RelationModel(WORDS, nodes, edges, **kw)


def classes(root, name):
    return [e for e in root.iter() if name in (e.get("class") or "").split()]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"nodes": (SpanNode(3, 9),)}, "outside the words"),
        ({"nodes": (SpanNode(2, 2),)}, "outside the words"),
        ({"nodes": (SpanNode(0, 2, anchor=3),)}, "anchor"),
        ({"nodes": (SpanNode(0, 1),), "edges": (Edge(0, 1),)}, "missing node"),
        ({"nodes": (SpanNode(0, 1),), "edges": (Edge(0, 0),)}, "itself"),
        ({"rows": (Row("pos", ("S",)),)}, "values"),
        ({"visible": frozenset()}, "at least one"),
    ],
)
def test_model_validation(kwargs, message):
    args = {"words": WORDS, "nodes": (), "edges": ()} | kwargs
    with pytest.raises(ValueError, match=message):
        RelationModel(**args)


def test_window_around_highlighted_nodes():
    model = roles()
    hl = RelationModel(
        WORDS,
        tuple(
            SpanNode(n.start, n.end, n.label, highlight=k in (0, 2))
            for k, n in enumerate(model.nodes)
        ),
        model.edges,
    )
    assert relation_window(hl, 0).visible == {2, 3}
    assert relation_window(hl, 1).visible == {1, 2, 3, 4}
    # No highlight: all nodes
    assert relation_window(model, 0).visible == {0, 1, 2, 3, 4, 5}
    # Already hidden words stay hidden
    hidden = RelationModel(
        WORDS, model.nodes, model.edges, visible=frozenset({0, 1, 2})
    )
    assert relation_window(hidden, 3).visible == {0, 1, 2}
    with pytest.raises(ValueError):
        relation_window(model, -1)


def test_lanes_put_enclosing_nodes_outside():
    lanes = node_lanes({0: (2, 2), 1: (4, 5), 2: (5, 5), 3: (0, 1), 4: (4, 6)})
    assert lanes[4] == 0  # longest of the overlapping group
    assert lanes[1] == 1
    assert lanes[2] == 2
    assert lanes[0] == lanes[3] == 0


def test_layout_star_levels_and_attachment():
    lay = relation_layout(roles(), Style())
    assert [arc.edge for arc in lay.arcs] == [0, 1, 2]
    levels = {arc.edge: arc.level for arc in lay.arcs}
    # Short arcs to both neighbours share level 1, the long arc goes above
    assert levels[0] == levels[1] == 1
    assert levels[2] == 2
    # Legs stand inside their nodes
    for arc in lay.arcs:
        edge = roles().edges[arc.edge]
        for k, x in ((edge.source, arc.x_source), (edge.target, arc.x_target)):
            box = lay.nodes[k]
            assert box.left < x < box.right
    # Nested node is in an inner lane and inside its enclosing box
    assert lay.nodes[4].lane == 1 and lay.nodes[3].lane == 0
    assert (
        lay.nodes[3].left < lay.nodes[4].left < lay.nodes[4].right < lay.nodes[3].right
    )
    assert lay.n_lanes == 2


def test_layout_anchor_attaches_to_word():
    model = RelationModel(
        WORDS,
        (SpanNode(0, 2, anchor=1), SpanNode(2, 3)),
        (Edge(1, 0, "arg0"),),
    )
    lay = relation_layout(model, Style())
    assert lay.nodes[0].x == pytest.approx(lay.column_of[1].centre)
    assert lay.arcs[0].x_target == pytest.approx(lay.column_of[1].centre)


def test_layout_widens_for_labels():
    long = "a very long relation label"
    model = RelationModel(
        ("a", "b"), (SpanNode(0, 1), SpanNode(1, 2)), (Edge(0, 1, long),)
    )
    s = Style()
    arc = relation_layout(model, s).arcs[0]
    from estnltk_syntax_vis.layout import text_width

    need = text_width(long, s.label_font_size) + 2 * s.label_padding
    assert abs(arc.x_target - arc.x_source) >= need - 1e-6


def test_hidden_nodes_and_their_edges_are_left_out():
    model = RelationModel(
        WORDS, roles().nodes, roles().edges, visible=frozenset({0, 1, 2, 3})
    )
    lay = relation_layout(model, Style())
    assert set(lay.nodes) == {0, 1, 2}
    assert [arc.edge for arc in lay.arcs] == [0, 1]
    assert [c.word for c in lay.columns][-1] is None  # trailing "…"


def test_svg_structure():
    model = roles(rows=(Row("pos", tuple("S H V P S H S Z".split())),))
    root = ET.fromstring(render_relation_svg(model))
    assert root.get("class") == "relation-diagram"
    assert len(classes(root, "word")) == len(WORDS)
    assert len(classes(root, "node")) == 5
    assert len(classes(root, "arc")) == 3
    labels = [e.find("svg:text", NS).text for e in classes(root, "label")]
    assert sorted(labels) == ["arg0", "arg1", "argm_loc"]
    assert [e.text for e in classes(root, "node-label")] == ["kohtumine"]
    assert [e.text for e in classes(root, "row-label")] == ["pos"]
    arc = classes(root, "arc")[0]
    assert (arc.get("data-source"), arc.get("data-target")) == ("0", "1")


def test_svg_highlight_and_escaping():
    model = RelationModel(
        ("<a>", "&", "b"),
        (
            SpanNode(0, 1, highlight=True),
            SpanNode(2, 3, highlight=True),
            SpanNode(1, 2),
        ),
        (Edge(0, 1, "x<y", highlight=True), Edge(2, 1)),
    )
    root = ET.fromstring(render_relation_svg(model))
    assert [e.text for e in classes(root, "word")] == ["<a>", "&", "b"]
    assert len(classes(root, "highlight")) == 3  # two nodes, one arc
    bold = [e.text for e in classes(root, "word") if e.get("font-weight") == "bold"]
    assert bold == ["<a>", "b"]
    # Unlabelled edges get no label
    assert [e.find("svg:text", NS).text for e in classes(root, "label")] == ["x<y"]


def test_svg_without_nodes():
    root = ET.fromstring(render_relation_svg(RelationModel(("a", "b"), (), ())))
    assert len(classes(root, "word")) == 2
    assert not classes(root, "arc")

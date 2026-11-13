"""Horizontal layout of a relation diagram: columns, node lanes, arc levels.

Edges are drawn like dependency arcs: a bar at a nesting level and two legs, but
the legs stand on span nodes (word ranges) instead of single words. A node's
legs are spread around its attachment point: the centre of the span, or its
anchor word. Overlapping nodes are put into separate lanes.
"""

import math
from dataclasses import dataclass

from .layout import Column, _label_x, arc_levels, column_slots, leg_offsets, text_width
from .relation_model import RelationModel
from .style import Style


@dataclass(frozen=True)
class NodeBox:
    """Placed span node: horizontal extent, lane and attachment point."""

    node: int
    left: float
    right: float
    lane: int  # 0 = outermost
    x: float  # centre of the node's legs


@dataclass(frozen=True)
class RelationArc:
    """A placed edge."""

    edge: int  # index into `RelationModel.edges`
    level: int
    x_source: float
    x_target: float  # arrow end
    x_label: float


@dataclass(frozen=True)
class RelationLayout:
    columns: tuple[Column, ...]
    column_of: dict[int, Column]  # visible word -> its column
    nodes: dict[int, NodeBox]  # visible node index -> its box
    arcs: tuple[RelationArc, ...]  # in edge order
    max_level: int
    n_lanes: int
    width: float


def node_lanes(spans: dict[int, tuple[int, int]]) -> dict[int, int]:
    """Lane of each node, given `(first, last)` column of each node.

    Longer nodes are placed first, so an enclosing node gets a lower (outer)
    lane than the nodes inside it; overlapping nodes never share a lane.
    """
    lanes: dict[int, int] = {}
    placed: list[tuple[int, int, int]] = []  # (first, last, lane)
    for k in sorted(spans, key=lambda k: (spans[k][0] - spans[k][1], spans[k][0], k)):
        first, last = spans[k]
        taken = {lane for (a, b, lane) in placed if a <= last and first <= b}
        lane = next(lane for lane in range(len(taken) + 1) if lane not in taken)
        lanes[k] = lane
        placed.append((first, last, lane))
    return lanes


def relation_layout(model: RelationModel, style: Style) -> RelationLayout:
    """Compute columns, node boxes and arc positions for `model`."""
    slots = column_slots(len(model.words), model.visible_words)
    pos = {word: p for p, word in enumerate(slots) if word is not None}
    n = len(slots)

    # Visible nodes as column ranges, and the column position their legs stand on
    spans: dict[int, tuple[int, int]] = {}
    for k, node in enumerate(model.nodes):
        cols = [pos[i] for i in range(node.start, node.end) if i in pos]
        if cols:
            spans[k] = (cols[0], cols[-1])

    def anchor_column(k: int) -> int | None:
        anchor = model.nodes[k].anchor
        return pos.get(anchor) if anchor is not None else None

    def position(k: int) -> float:
        col = anchor_column(k)
        return col if col is not None else sum(spans[k]) / 2

    edges = [
        e
        for e, edge in enumerate(model.edges)
        if edge.source in spans and edge.target in spans
    ]
    # Nodes ranked left to right by attachment point; legs are ordered on ranks
    ranked = sorted(
        spans, key=lambda k: (position(k), model.nodes[k].start, -model.nodes[k].end)
    )
    rank = {k: r for r, k in enumerate(ranked)}
    pairs = [(rank[model.edges[e].source], rank[model.edges[e].target]) for e in edges]
    levels = arc_levels(pairs)
    offsets, _, counts = leg_offsets(len(ranked), pairs, levels, set())
    lanes = node_lanes(spans)

    def inset(k: int) -> float:
        return 2 + lanes[k] * style.lane_inset

    # Column widths: the widest of the word and its rows
    bold = model.highlight_words
    widths = []
    for i in slots:
        if i is None:
            widths.append(style.gap_width)
            continue
        texts = [text_width(model.words[i], style.word_font_size, i in bold)]
        texts += [text_width(r.values[i], style.row_font_size) for r in model.rows]
        widths.append(max(texts) + style.word_padding)

    def widen(first: int, last: int, need: float) -> None:
        have = sum(widths[first : last + 1])
        if need > have:
            for p in range(first, last + 1):
                widths[p] += (need - have) / (last - first + 1)

    # Nodes must hold their legs and their label
    for k, (first, last) in spans.items():
        legs = (counts[rank[k]] - 1) * style.leg_gap + style.word_padding
        col = anchor_column(k)
        if col is not None:
            widen(col, col, legs)
        else:
            widen(first, last, legs + 2 * inset(k))
        label = model.nodes[k].label
        if label:
            need = text_width(label, style.row_font_size) + style.word_padding
            widen(first, last, need + 2 * inset(k))

    # Extra space between columns `p` and `p + 1`, so edge labels fit on bars
    gaps = [0.0] * max(n - 1, 0)

    def lefts() -> list[float]:
        xs, x = [], 0.0
        for p, w in enumerate(widths):
            xs.append(x)
            x += w + (gaps[p] if p < n - 1 else 0)
        return xs

    def node_x(xs: list[float], k: int) -> float:
        col = anchor_column(k)
        if col is not None:
            return xs[col] + widths[col] / 2
        first, last = spans[k]
        return (xs[first] + xs[last] + widths[last]) / 2

    def leg_x(xs: list[float], j: int) -> tuple[float, float]:
        s, t = pairs[j]
        edge = model.edges[edges[j]]
        return (
            node_x(xs, edge.source) + offsets[(j, s)] * style.leg_gap,
            node_x(xs, edge.target) + offsets[(j, t)] * style.leg_gap,
        )

    def label_need(j: int) -> float:
        label = model.edges[edges[j]].label
        return text_width(label, style.label_font_size) + 2 * style.label_padding

    def distance(j: int) -> float:
        edge = model.edges[edges[j]]
        return abs(position(edge.source) - position(edge.target))

    for j in sorted(range(len(pairs)), key=distance):
        x_s, x_t = leg_x(lefts(), j)
        missing = label_need(j) - abs(x_t - x_s)
        edge = model.edges[edges[j]]
        lo, hi = sorted((position(edge.source), position(edge.target)))
        between = range(math.floor(lo), math.ceil(hi))
        if missing > 0 and between:
            for p in between:
                gaps[p] += missing / len(between)

    xs = lefts()
    columns = tuple(
        Column(x, w, word) for x, w, word in zip(xs, widths, slots, strict=True)
    )
    boxes = {
        k: NodeBox(
            node=k,
            left=xs[first] + inset(k),
            right=xs[last] + widths[last] - inset(k),
            lane=lanes[k],
            x=node_x(xs, k),
        )
        for k, (first, last) in spans.items()
    }
    legs = [leg_x(xs, j) for j in range(len(pairs))]
    arcs = []
    for j, e in enumerate(edges):
        crossing = [
            x for i, leg in enumerate(legs) if levels[i] > levels[j] for x in leg
        ]
        arcs.append(
            RelationArc(
                edge=e,
                level=levels[j],
                x_source=legs[j][0],
                x_target=legs[j][1],
                x_label=_label_x(*legs[j], crossing, label_need(j)),
            )
        )
    width = columns[-1].x + columns[-1].width if columns else 0.0
    return RelationLayout(
        columns=columns,
        column_of={c.word: c for c in columns if c.word is not None},
        nodes=boxes,
        arcs=tuple(arcs),
        max_level=max(levels, default=0),
        n_lanes=max(lanes.values(), default=-1) + 1,
        width=width,
    )

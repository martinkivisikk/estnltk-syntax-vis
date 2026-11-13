"""SVG rendering of a relation model: span boxes linked by rectangular arcs."""

from html import escape

from .layout import text_width
from .relation_layout import relation_layout
from .relation_model import RelationModel
from .style import Style
from .svg import _f


def render_relation_svg(model: RelationModel, style: Style | None = None) -> str:
    """Draw `model` as an SVG relation diagram and return the SVG string."""
    s = style or Style()
    lay = relation_layout(model, s)
    bold = model.highlight_words

    row_label_w = max(
        (text_width(r.label, s.row_font_size) for r in model.rows if r.label),
        default=0.0,
    )
    x0 = s.margin + (row_label_w + 12 if row_label_w else 0)

    # Vertical positions, top to bottom
    n_lanes = max(lay.n_lanes, 1)
    y_legs = s.margin + s.label_font_size / 2 + 2 + lay.max_level * s.level_height
    y_word = y_legs + 4 + (n_lanes - 1) * s.lane_inset + s.word_font_size
    y_rows = [y_word + (k + 1) * s.row_height for k in range(len(model.rows))]
    y_text = y_rows[-1] if y_rows else y_word
    labelled = any(model.nodes[k].label for k in lay.nodes)

    def y_node_top(lane: int) -> float:
        return y_legs + 1 + lane * s.lane_inset

    def y_node_label(lane: int) -> float:
        """Label row of a lane; the outermost lane's labels are the lowest."""
        return y_text + (n_lanes - lane) * s.row_height

    def y_node_bottom(lane: int) -> float:
        if labelled:
            return y_node_label(lane) + 5
        return y_text + 5 + (n_lanes - 1 - lane) * s.lane_inset

    y_bottom = y_node_bottom(0)
    width = x0 + lay.width + s.margin
    height = y_bottom + s.margin

    def bar_y(level: int) -> float:
        return y_legs - level * s.level_height

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(width)}" '
        f'height="{_f(height)}" viewBox="0 0 {_f(width)} {_f(height)}" '
        f'font-family="{escape(s.font_family)}" class="relation-diagram">',
        f'<rect width="100%" height="100%" fill="{s.background}"/>',
        f'<g transform="translate({_f(x0)},0)">',
    ]

    # Span nodes, outer lanes first so inner boxes are drawn on top
    for box in sorted(lay.nodes.values(), key=lambda b: (b.lane, b.left)):
        node = model.nodes[box.node]
        top, bottom = y_node_top(box.lane), y_node_bottom(box.lane)
        if node.highlight:
            css, fill, stroke = "node highlight", s.highlight_fill, s.highlight_arc
        else:
            css, fill, stroke = "node", s.box_fill, s.node_stroke
        out.append(
            f'<rect class="{css}" data-node="{box.node}" x="{_f(box.left)}" '
            f'y="{_f(top)}" width="{_f(box.right - box.left)}" '
            f'height="{_f(bottom - top)}" rx="4" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1"/>'
        )
        if node.label:
            out.append(
                f'<text class="node-label" x="{_f((box.left + box.right) / 2)}" '
                f'y="{_f(y_node_label(box.lane))}" text-anchor="middle" '
                f'font-size="{_f(s.row_font_size)}" fill="{s.text}">'
                f"{escape(node.label)}</text>"
            )

    # Arcs; highlighted ones last so that they are drawn on top
    labels = []
    a = s.arrow_size
    for arc in sorted(lay.arcs, key=lambda arc: model.edges[arc.edge].highlight):
        edge = model.edges[arc.edge]
        if edge.highlight:
            colour, stroke, css = (
                s.highlight_arc,
                s.highlight_stroke_width,
                "arc highlight",
            )
        else:
            colour, stroke, css = s.arc, s.stroke_width, "arc"
        y = bar_y(arc.level)
        y_source = y_node_top(lay.nodes[edge.source].lane)
        y_tip = y_node_top(lay.nodes[edge.target].lane)
        out.append(
            f'<g class="{css}" data-source="{edge.source}" data-target="{edge.target}">'
            f'<path d="M{_f(arc.x_source)},{_f(y_source)} V{_f(y)} '
            f'H{_f(arc.x_target)} V{_f(y_tip - 1.6 * a)}" fill="none" '
            f'stroke="{colour}" stroke-width="{_f(stroke)}"/>'
            f'<polygon points="{_f(arc.x_target - a)},{_f(y_tip - 1.6 * a)} '
            f"{_f(arc.x_target + a)},{_f(y_tip - 1.6 * a)} {_f(arc.x_target)},"
            f'{_f(y_tip)}" fill="{colour}"/></g>'
        )
        if edge.label:
            labels.append((arc.x_label, y, edge.label, colour, edge.highlight))

    # Edge labels over their bars, on a background that cuts a gap in the bar
    for x, y, label, colour, highlight in labels:
        w = text_width(label, s.label_font_size) + 4
        h = s.label_font_size + 2
        weight = ' font-weight="bold"' if highlight else ""
        out.append(
            f'<g class="label">'
            f'<rect x="{_f(x - w / 2)}" y="{_f(y - h / 2)}" width="{_f(w)}" '
            f'height="{_f(h)}" fill="{s.background}"/>'
            f'<text x="{_f(x)}" y="{_f(y + 0.35 * s.label_font_size)}" '
            f'text-anchor="middle" font-size="{_f(s.label_font_size)}" '
            f'fill="{colour if highlight else s.muted}"{weight}>'
            f"{escape(label)}</text></g>"
        )

    # Words and rows; "…" for hidden words
    for col in lay.columns:
        if col.word is None:
            out.append(
                f'<text class="gap" x="{_f(col.centre)}" y="{_f(y_word)}" '
                f'text-anchor="middle" font-size="{_f(s.word_font_size)}" '
                f'fill="{s.muted}">…</text>'
            )
            continue
        i = col.word
        weight = ' font-weight="bold"' if i in bold else ""
        out.append(
            f'<text class="word" x="{_f(col.centre)}" y="{_f(y_word)}" '
            f'text-anchor="middle" font-size="{_f(s.word_font_size)}" '
            f'fill="{s.text}"{weight}>{escape(model.words[i])}</text>'
        )
        for row, y in zip(model.rows, y_rows, strict=True):
            out.append(
                f'<text class="row" x="{_f(col.centre)}" y="{_f(y)}" '
                f'text-anchor="middle" font-size="{_f(s.row_font_size)}" '
                f'fill="{s.muted}">{escape(row.values[i])}</text>'
            )
    out.append("</g>")

    for row, y in zip(model.rows, y_rows, strict=True):
        out.append(
            f'<text class="row-label" x="{_f(s.margin + row_label_w)}" y="{_f(y)}" '
            f'text-anchor="end" font-size="{_f(s.row_font_size)}" '
            f'font-style="italic" fill="{s.muted}">{escape(row.label)}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)

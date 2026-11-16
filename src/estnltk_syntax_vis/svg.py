"""SVG rendering of a sentence model with rectangular dependency arcs."""

import base64
from html import escape

from .layout import Arc, layout, text_width
from .model import SentenceModel
from .style import Style


def _f(value: float) -> str:
    """Compact number formatting for SVG coordinates."""
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _runs(indices: frozenset[int]) -> list[tuple[int, int]]:
    """Contiguous runs of word indices as `(start, end)` with exclusive ends."""
    runs: list[tuple[int, int]] = []
    for i in sorted(indices):
        if runs and runs[-1][1] == i:
            runs[-1] = (runs[-1][0], i + 1)
        else:
            runs.append((i, i + 1))
    return runs


def html_blocks(svgs: list[str], as_img: bool = False) -> str:
    """Wrap each SVG in its own horizontally scrollable `div`.

    `max-width:none` on the `<svg>` overrides notebook CSS such as JupyterLab's
    `svg { max-width: 100%; height: auto }`, which would otherwise scale wide
    diagrams down to the cell width instead of letting the `div` scroll.

    With `as_img`, each SVG is put in an `<img>` as a base64 data URI instead.
    Jupyter strips inline `<svg>` from the saved outputs of an untrusted notebook
    but keeps `<img>`, so the diagrams show without re-running the cells.
    GitHub's notebook viewer does the opposite: it keeps inline SVG and blocks
    data URIs.
    """
    blocks = []
    for svg in svgs:
        if as_img:
            data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            inner = (
                f'<img src="data:image/svg+xml;base64,{data}" style="max-width:none">'
            )
        else:
            inner = svg.replace("<svg ", '<svg style="max-width:none" ', 1)
        blocks.append(f'<div style="overflow-x:auto;margin-bottom:12px">{inner}</div>')
    return "\n".join(blocks)


def render_svg(sentence: SentenceModel, style: Style | None = None) -> str:
    """Draw `sentence` as an SVG dependency diagram and return the SVG string."""
    s = style or Style()
    lay = layout(sentence, s)
    highlight = sentence.highlight
    context_roots = sentence.highlight_roots

    # Row labels go into a column left of the words
    row_label_w = max(
        (text_width(r.label, s.row_font_size) for r in sentence.rows if r.label),
        default=0.0,
    )
    x0 = s.margin + (row_label_w + 12 if row_label_w else 0)

    # Vertical positions, top to bottom
    root_label_h = s.label_font_size + 4
    y_legs = s.margin + root_label_h + (lay.max_level + 1) * s.level_height
    y_word = y_legs + 4 + s.word_font_size  # baseline of the words
    y_rows = [y_word + (k + 1) * s.row_height for k in range(len(sentence.rows))]
    y_under = y_rows[-1] if y_rows else y_word  # last text line above box labels
    # Box label lanes, top to bottom; each is as tall as its most label lines
    shown = [
        (box, lane, inset)
        for box, lane, inset in zip(
            sentence.boxes, lay.box_lanes, lay.box_insets, strict=True
        )
        if lane is not None
    ]
    n_lanes = max((lane for _, lane, _ in shown), default=-1) + 1
    lane_lines = [0] * n_lanes
    for box, lane, _ in shown:
        lane_lines[lane] = max(lane_lines[lane], len(box.lines))
    lane_top = [y_under]
    for lines in lane_lines:
        lane_top.append(lane_top[-1] + lines * s.row_height + s.box_lane_gap)
    y_bottom = lane_top[-1] if shown else y_under + 5  # bottom of boxes
    width = x0 + lay.width + s.margin
    height = y_bottom + s.margin

    def bar_y(level: int) -> float:
        return y_legs - level * s.level_height

    def arc_style(head: int | None, dependent: int) -> tuple[str, float, str, str]:
        """Colour, stroke width, dash attribute and CSS class of an arc."""
        if head is not None and head in highlight and dependent in highlight:
            return s.highlight_arc, s.highlight_stroke_width, "", "arc highlight"
        if dependent in context_roots:
            return s.context_arc, s.highlight_stroke_width, "5,3", "arc context"
        return s.arc, s.stroke_width, "", "arc"

    def arrow(x: float, colour: str) -> str:
        a = s.arrow_size
        return (
            f'<polygon points="{_f(x - a)},{_f(y_legs - 1.6 * a)} {_f(x + a)},'
            f'{_f(y_legs - 1.6 * a)} {_f(x)},{_f(y_legs)}" fill="{colour}"/>'
        )

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(width)}" '
        f'height="{_f(height)}" viewBox="0 0 {_f(width)} {_f(height)}" '
        f'font-family="{escape(s.font_family)}" class="dependency-tree">',
        f'<rect width="100%" height="100%" fill="{s.background}"/>',
        f'<g transform="translate({_f(x0)},0)">',
    ]

    def extent(start: int, end: int) -> tuple[float, float] | None:
        """Left and right x of the visible words in `start .. end - 1`."""
        cols = [lay.column_of[i] for i in range(start, end) if i in lay.column_of]
        if not cols:
            return None
        return cols[0].x + 2, cols[-1].x + cols[-1].width - 2

    # Boxes (outer lanes first), then the highlight on top of them
    rects = []  # (box, lane, left, top, right, bottom)
    for box, lane, inset in shown:
        left, right = extent(box.start, box.end)  # type: ignore[misc]
        d = inset * s.lane_inset
        rects.append((box, lane, left + d, y_legs + 1, right - d, lane_top[lane + 1]))
    rects.sort(key=lambda r: -r[1])
    # Semi-transparent fills: where boxes overlap they add up and get darker
    fill = f'fill="{s.box_tint}" fill-opacity="{_f(s.box_tint_opacity)}"'
    for box, lane, left, top, right, bottom in rects:
        relation = "" if box.relation is None else f' data-relation="{box.relation}"'
        out.append(
            f'<rect class="box" x="{_f(left)}" y="{_f(top)}" '
            f'width="{_f(right - left)}" height="{_f(bottom - top)}" rx="4" '
            f'{fill} stroke="{s.box_stroke}" stroke-width="1" '
            f'data-lane="{lane}"{relation}/>'
        )
    for start, end in _runs(highlight & lay.column_of.keys()):
        left, right = extent(start, end)  # type: ignore[misc]
        out.append(
            f'<rect class="highlight-box" x="{_f(left)}" y="{_f(y_legs + 1)}" '
            f'width="{_f(right - left)}" height="{_f(y_bottom - y_legs - 1)}" '
            f'rx="4" fill="{s.highlight_fill}" stroke="{s.highlight_arc}" '
            f'stroke-width="1"/>'
        )

    # Arcs; highlighted ones last so that they are drawn on top
    def draw_order(arc: Arc) -> int:
        return ["arc", "arc context", "arc highlight"].index(
            arc_style(arc.head, arc.dependent)[3]
        )

    labels = []
    for arc in sorted(lay.arcs, key=draw_order):
        colour, stroke, dash, css = arc_style(arc.head, arc.dependent)
        y = bar_y(arc.level)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(
            f'<g class="{css}" data-head="{arc.head}" data-dependent="{arc.dependent}">'
            f'<path d="M{_f(arc.x_head)},{_f(y_legs)} V{_f(y)} H{_f(arc.x_dependent)} '
            f'V{_f(y_legs - 1.6 * s.arrow_size)}" fill="none" stroke="{colour}" '
            f'stroke-width="{_f(stroke)}"{dash_attr}/>'
            f"{arrow(arc.x_dependent, colour)}</g>"
        )
        labels.append((arc.x_label, y, arc.deprel, colour, css))

    # Root arrows from the top, labelled with the root's deprel
    y_top = bar_y(lay.max_level + 1)
    for root, x in sorted(lay.root_x.items()):
        colour, stroke, dash, css = arc_style(None, root)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(
            f'<g class="{css} root" data-dependent="{root}">'
            f'<path d="M{_f(x)},{_f(y_top)} V{_f(y_legs - 1.6 * s.arrow_size)}" '
            f'fill="none" stroke="{colour}" stroke-width="{_f(stroke)}"{dash_attr}/>'
            f"{arrow(x, colour)}</g>"
        )
        out.append(
            f'<text class="root-label" x="{_f(x)}" y="{_f(y_top - 4)}" '
            f'text-anchor="middle" font-size="{_f(s.label_font_size)}" '
            f'fill="{s.muted}">{escape(sentence.deprels[root])}</text>'
        )

    # Deprel labels over their bars, on a background that cuts a gap in the bar
    for x, y, deprel, colour, css in labels:
        w = text_width(deprel, s.label_font_size) + 4
        h = s.label_font_size + 2
        weight = ' font-weight="bold"' if css != "arc" else ""
        out.append(
            f'<g class="label">'
            f'<rect x="{_f(x - w / 2)}" y="{_f(y - h / 2)}" width="{_f(w)}" '
            f'height="{_f(h)}" fill="{s.background}"/>'
            f'<text x="{_f(x)}" y="{_f(y + 0.35 * s.label_font_size)}" '
            f'text-anchor="middle" font-size="{_f(s.label_font_size)}" '
            f'fill="{colour if css != "arc" else s.muted}"{weight}>'
            f"{escape(deprel)}</text></g>"
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
        i, word = col.word, sentence.words[col.word]
        weight = ' font-weight="bold"' if i in highlight else ""
        out.append(
            f'<text class="word" x="{_f(col.centre)}" y="{_f(y_word)}" '
            f'text-anchor="middle" font-size="{_f(s.word_font_size)}" '
            f'fill="{s.text}"{weight}>{escape(word)}</text>'
        )
        for row, y in zip(sentence.rows, y_rows, strict=True):
            out.append(
                f'<text class="row" x="{_f(col.centre)}" y="{_f(y)}" '
                f'text-anchor="middle" font-size="{_f(s.row_font_size)}" '
                f'fill="{s.muted}">{escape(row.values[i])}</text>'
            )
    for box, lane, left, _, right, _ in rects:
        for j, (cls, line) in enumerate(
            (c, t)
            for c, t in (("box-label", box.label), ("box-detail", box.detail))
            if t
        ):
            colour = s.text if cls == "box-label" else s.muted
            out.append(
                f'<text class="{cls}" x="{_f((left + right) / 2)}" '
                f'y="{_f(lane_top[lane] + (j + 1) * s.row_height)}" '
                f'text-anchor="middle" font-size="{_f(s.row_font_size)}" '
                f'fill="{colour}">{escape(line)}</text>'
            )
    out.append("</g>")

    # Row labels, right-aligned in their own column
    for row, y in zip(sentence.rows, y_rows, strict=True):
        out.append(
            f'<text class="row-label" x="{_f(s.margin + row_label_w)}" y="{_f(y)}" '
            f'text-anchor="end" font-size="{_f(s.row_font_size)}" '
            f'font-style="italic" fill="{s.muted}">{escape(row.label)}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)

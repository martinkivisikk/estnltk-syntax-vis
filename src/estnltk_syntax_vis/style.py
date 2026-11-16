"""Colours, fonts and sizes of the diagrams."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    """Drawing options. Sizes are in pixels.

    The SVG has its own background (`background`), so the default colours also
    work in dark notebook themes.
    """

    font_family: str = "Arial, Helvetica, 'Liberation Sans', sans-serif"
    word_font_size: float = 14
    label_font_size: float = 11  # deprel labels
    row_font_size: float = 11

    background: str = "white"
    text: str = "#222"
    muted: str = "#6b6b6b"
    arc: str = "#8a8a8a"
    box_fill: str = "#e7eef7"  # span boxes in relation diagrams
    # Overlay boxes: semi-transparent, so overlapping boxes get darker
    box_tint: str = "#8fb0dc"
    box_tint_opacity: float = 0.3
    box_stroke: str = "#9db4d4"
    box_lane_gap: float = 5  # space under each lane of overlay box labels
    node_stroke: str = "#a9bdd6"  # outline of span boxes in relation diagrams
    highlight_fill: str = "#ffe3c2"
    highlight_arc: str = "#d9480f"
    context_arc: str = "#1c7ed6"

    margin: float = 10
    word_padding: float = 16  # horizontal space added to each word's text width
    leg_gap: float = 8  # distance between arc legs on one word
    level_height: float = 22  # vertical distance between arc levels
    label_padding: float = 10  # minimal free bar on each side of a deprel label
    row_height: float = 15
    gap_width: float = 28  # width of a "…" column for hidden words
    lane_inset: float = 3  # inset per inner lane (overlays, relation diagrams)
    arrow_size: float = 5
    stroke_width: float = 1
    highlight_stroke_width: float = 2.2

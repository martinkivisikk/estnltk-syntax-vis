from helpers import make

from estnltk_syntax_vis import Style
from estnltk_syntax_vis.layout import arc_levels, layout, text_width


def test_levels_nested():
    # (head, dependent): the outer arc goes above both inner ones
    assert arc_levels([(1, 0), (1, 2), (1, 3), (0, 3)]) == [1, 1, 2, 3]


def test_levels_shared_end_word_can_share_level():
    assert arc_levels([(1, 0), (1, 2)]) == [1, 1]


def test_levels_crossing_arcs_get_different_levels():
    levels = arc_levels([(0, 2), (1, 3)])
    assert sorted(levels) == [1, 2]


def test_text_width_diacritics_and_bold():
    assert text_width("õun", 10) == text_width("oun", 10)
    assert text_width("W", 10) > text_width("i", 10)
    assert text_width("a", 10, bold=True) > text_width("a", 10)


def legs_on(lay, word):
    """(x, kind) of every leg on `word`, left to right."""
    legs = [(lay.root_x[word], "root")] if word in lay.root_x else []
    for arc in lay.arcs:
        if arc.head == word:
            legs.append((arc.x_head, arc.dependent))
        if arc.dependent == word:
            legs.append((arc.x_dependent, arc.head))
    return [kind for _, kind in sorted(legs)]


def test_leg_order_many_dependents():
    # Word 3 is the root with dependents on both sides at several distances
    s = make("a b c d e f g", [4, 4, 4, 0, 4, 4, 4])
    lay = layout(s, Style())
    # Left arcs lowest first, then the root arrow, then right arcs highest first
    assert legs_on(lay, 3) == [2, 1, 0, "root", 6, 5, 4]


def test_legs_spread_inside_column():
    s = make("a b c d e f g", [4, 4, 4, 0, 4, 4, 4])
    style = Style()
    lay = layout(s, style)
    col = lay.columns[3]
    xs = sorted([a.x_head for a in lay.arcs] + [lay.root_x[3]])
    assert col.x < xs[0] and xs[-1] < col.x + col.width
    assert all(b - a >= style.leg_gap - 1e-9 for a, b in zip(xs, xs[1:], strict=False))


def test_projective_bars_do_not_cross_legs():
    s = make("a b c d e f g", [2, 0, 4, 2, 4, 2, 6])
    lay = layout(s, Style())
    for arc in lay.arcs:
        lo, hi = sorted((arc.x_head, arc.x_dependent))
        for other in lay.arcs:
            if other.level > arc.level:
                continue
            for x in (other.x_head, other.x_dependent):
                if other is not arc:
                    assert not lo < x < hi or other.level < arc.level
        for x in lay.root_x.values():
            assert not lo < x < hi


def test_long_label_widens_columns():
    style = Style()
    short = layout(make("a b", [2, 0], ["x", "root"]), style)
    long = layout(make("a b", [2, 0], ["very:long:label", "root"]), style)
    arc = long.arcs[0]
    need = (
        text_width("very:long:label", style.label_font_size) + 2 * style.label_padding
    )
    assert abs(arc.x_dependent - arc.x_head) >= need - 1e-9
    assert long.width > short.width


def test_label_avoids_crossing_root_arrow():
    # Non-projective: the arc 1 -> 6 passes over the root arrow on word 3
    s = make("a b c d e f g", [4, 4, 4, 0, 4, 4, 2], ["d"] * 6 + ["nmod"])
    lay = layout(s, Style())
    (arc,) = [a for a in lay.arcs if a.dependent == 6]
    assert arc.x_label > lay.root_x[3]


def test_gap_columns_and_hidden_arcs():
    s = make(
        "Eesti Vabariigi president Alar Karis kohtus eile Tallinnas Soome "
        "peaministriga .",
        [2, 3, 6, 3, 4, 0, 6, 6, 10, 6, 6],
        visible=frozenset({2, 5, 7}),
    )
    lay = layout(s, Style())
    assert [c.word for c in lay.columns] == [None, 2, None, 5, None, 7, None]
    # Only arcs with both ends visible: kohtus -> president, kohtus -> Tallinnas
    assert sorted((a.head, a.dependent) for a in lay.arcs) == [(5, 2), (5, 7)]
    assert set(lay.root_x) == {5}
    xs = [c.x for c in lay.columns]
    assert xs == sorted(xs)

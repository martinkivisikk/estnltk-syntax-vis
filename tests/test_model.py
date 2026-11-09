import pytest
from helpers import make

from estnltk_syntax_vis import Box, Row, SentenceModel, window


def test_valid_model(simple):
    assert simple.heads == (1, None, 1, 1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"heads": (1, None)},  # wrong length
        {"heads": (5, None, 1)},  # head outside
        {"heads": (0, None, 1)},  # own head
        {"rows": (Row("pos", ("A",)),)},
        {"boxes": (Box(2, 4),)},
        {"boxes": (Box(1, 1),)},
        {"highlight": frozenset({3})},
    ],
)
def test_invalid_model(kwargs):
    base = {"words": ("a", "b", "c"), "heads": (1, None, 1), "deprels": ("x",) * 3}
    with pytest.raises(ValueError):
        SentenceModel(**(base | kwargs))


def test_highlight_roots():
    s = make("a b c d", [2, 0, 4, 2], highlight=frozenset({2, 3}))
    assert s.highlight_roots == {3}


SENTENCE = (
    "Eesti Vabariigi president Alar Karis kohtus eile Tallinnas Soome peaministriga .",
    [2, 3, 6, 3, 4, 0, 6, 6, 10, 6, 6],
)


def test_window_fragment_shows_head_of_root():
    s = make(*SENTENCE, highlight=frozenset({3, 4}))  # Alar Karis
    assert window(s, 0).visible_words == (2, 3, 4)  # + president


def test_window_non_contiguous_fragment_hides_words_between():
    s = make(*SENTENCE, highlight=frozenset({2, 7}))  # president, Tallinnas
    assert window(s, 0).visible_words == (2, 5, 7)  # + kohtus


def test_window_size_and_edges():
    s = make(*SENTENCE, highlight=frozenset({0}))
    assert window(s, 2).visible_words == (0, 1, 2)  # head of "Eesti" is inside


def test_window_without_highlight_is_unchanged(simple):
    assert window(simple, 0) is simple


def test_window_negative_size(simple):
    with pytest.raises(ValueError):
        window(simple, -1)


def test_visible_validation(simple):
    with pytest.raises(ValueError):
        SentenceModel(simple.words, simple.heads, simple.deprels, visible=frozenset())
    with pytest.raises(ValueError):
        SentenceModel(
            simple.words, simple.heads, simple.deprels, visible=frozenset({9})
        )

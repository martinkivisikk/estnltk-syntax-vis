"""Extraction from RelationLayers and `RelationVisualiser`.

The layers follow the examples of EstNLTK's `relation_layer.ipynb` tutorial.
"""

import xml.etree.ElementTree as ET

import pytest
from estnltk import Text
from helpers import add_relations, make_text

import estnltk_syntax_vis.relation_visualiser as relation_visualiser_module
from estnltk_syntax_vis import RelationVisualiser
from estnltk_syntax_vis.relation_extract import RelationConfig, extract_relations

COREF = (
    'Mari kirjeldas õhinal, kuidas ta väiksena "Sipsikut" luges: "Ma ei suutnud '
    'seda raamatut kohe kuidagi käest ära panna! Nii põnev oli see!"'
)
TEMPORAL = (
    "Pühapäeva varahommikul kutsuti politsei Riia mäele. Seal oli ühelt noorelt "
    "mehelt ära võetud nahktagi ja käekell. Juhtumi kohta algatati uurimine."
)
ROLES = (
    "President Bush kohtus temaga privaatselt Valges Majas teisipäeval. Aga John "
    "ja Mari kohtusid hoopis kokteilipeol. Mari ei ostnud Johnile kokteili."
)
ROLE_NAMES = ["verb", "arg0", "arg1", "arg4", "argm_mnr", "argm_tmp", "argm_loc"]


@pytest.fixture(scope="module")
def coref():
    text = Text(COREF).tag_layer(["words", "sentences"])
    return add_relations(
        text,
        "coreference",
        ["mention", "entity"],
        [
            {"mention": "ta", "entity": "Mari"},
            {"mention": ("Ma", 1), "entity": "Mari"},
            {"mention": "seda raamatut", "entity": '"Sipsikut"'},
            {"mention": "see", "entity": '"Sipsikut"'},
        ],
    )


@pytest.fixture(scope="module")
def temporal():
    text = Text(TEMPORAL).tag_layer(["words", "sentences"])
    return add_relations(
        text,
        "temporal_relations",
        ["entity_a", "entity_b"],
        [
            {"entity_a": "Pühapäeva varahommikul", "entity_b": "kutsuti"},
            {"entity_a": "ära võetud", "entity_b": "kutsuti", "rel_type": "BEFORE"},
            {"entity_a": "ära võetud", "entity_b": "Juhtumi", "rel_type": "IDENTITY"},
        ],
        attributes=("rel_type",),
    )


@pytest.fixture(scope="module")
def roles():
    text = Text(ROLES).tag_layer(["words", "sentences", "morph_analysis"])
    return add_relations(
        text,
        "semantic_roles",
        ROLE_NAMES,
        [
            {
                "verb": "kohtus",
                "arg0": "President Bush",
                "arg1": "temaga",
                "argm_mnr": "privaatselt",
                "argm_tmp": "teisipäeval",
                "argm_loc": "Valges Majas",
                "sense": ["kohtuma_1", "kohtuma_2"],
            },
            {"verb": "kohtusid", "arg0": "John", "arg1": "Mari", "sense": "kohtuma_1"},
            {"arg0": ("Mari", 1), "arg1": ("kokteili", 1), "arg4": "Johnile"},
        ],
        attributes=("sense",),
        ambiguous=True,
    )


def texts(model, node):
    return " ".join(model.words[node.start : node.end])


def edges(model):
    """Edges as (source text, target text, label)."""
    return [
        (
            texts(model, model.nodes[e.source]),
            texts(model, model.nodes[e.target]),
            e.label,
        )
        for e in model.edges
    ]


def only(layer, **kw):
    models = extract_relations(layer, RelationConfig(**kw))
    assert len(models) == 1
    return models[0][1]


# Edges and labels


def test_two_span_relations_and_shared_nodes(coref):
    ((sentences, model),) = extract_relations(coref, RelationConfig())
    assert sentences == (0, 1)  # "see" is in the second sentence
    assert edges(model) == [
        ("ta", "Mari", "entity"),
        ("Ma", "Mari", "entity"),
        ("seda raamatut", '" Sipsikut "', "entity"),
        ("see", '" Sipsikut "', "entity"),
    ]
    # Mari and "Sipsikut" are one node each
    assert len(model.nodes) == 6
    assert model.visible is None


def test_label_from_attribute_and_missing_value(temporal):
    model = only(temporal, label="rel_type")
    assert [e.label for e in model.edges] == ["", "BEFORE", "IDENTITY"]


def test_label_function_and_none(temporal):
    model = only(temporal, label=lambda rel, s, t: f"{s}>{t}")
    assert {e.label for e in model.edges} == {"entity_a>entity_b"}
    assert {e.label for e in only(temporal, label=None).edges} == {""}


def test_default_star_from_first_filled_span(roles):
    models = extract_relations(roles, RelationConfig())
    assert [s for s, _ in models] == [(0,), (1,), (2,)]
    first = models[0][1]
    assert edges(first) == [
        ("kohtus", "President Bush", "arg0"),
        ("kohtus", "temaga", "arg1"),
        ("kohtus", "privaatselt", "argm_mnr"),
        ("kohtus", "teisipäeval", "argm_tmp"),
        ("kohtus", "Valges Majas", "argm_loc"),
    ]
    # No verb span: the star starts from arg0, unfilled spans are skipped
    assert edges(models[2][1]) == [
        ("Mari", "kokteili", "arg1"),
        ("Mari", "Johnile", "arg4"),
    ]


def test_hub_and_hub_label(roles):
    models = extract_relations(
        roles, RelationConfig(hub="arg1", hub_label="sense", span_names=True)
    )
    first = models[0][1]
    assert edges(first)[0] == ("temaga", "kohtus", "verb")
    labels = {texts(first, n): n.label for n in first.nodes}
    assert labels["temaga"] == "arg1, kohtuma_1|kohtuma_2"  # ambiguous: joined
    assert labels["kohtus"] == "verb"


def test_edges_function_gives_chains(roles):
    def chain(relation):
        names = [n for n in ROLE_NAMES if n != "verb"]
        return list(zip(names, names[1:], strict=False))

    model = extract_relations(roles, RelationConfig(edges=chain), sentence=0)[0][1]
    assert edges(model) == [
        ("President Bush", "temaga", "arg1"),
        ("privaatselt", "teisipäeval", "argm_tmp"),
        ("teisipäeval", "Valges Majas", "argm_loc"),
    ]


def test_edges_function_validates_names(roles):
    config = RelationConfig(edges=lambda rel: [("verb", "nope")])
    with pytest.raises(ValueError, match="'nope' is not a span name"):
        extract_relations(roles, config)
    config = RelationConfig(edges=lambda rel: ["verb"])
    with pytest.raises(ValueError, match="edges must give"):
        extract_relations(roles, config)


def test_duplicate_edges_are_merged():
    text = Text("Mari tuli. Ta naeris.").tag_layer(["words", "sentences"])
    layer = add_relations(
        text,
        "coref",
        ["mention", "entity"],
        # Different character spans on the same words give the same edge
        [{"mention": "Ta", "entity": "Mari"}, {"mention": "T", "entity": "Mari"}],
    )
    model = only(layer)
    assert len(model.edges) == 1 and len(model.nodes) == 2


# Words, sentences and selection


def test_enveloping_layer_and_partial_words():
    from estnltk_core import RelationLayer

    text = Text(COREF).tag_layer(["words", "sentences"])
    layer = RelationLayer(
        "coref_env",
        span_names=["mention", "entity"],
        enveloping="words",
        text_object=text,
    )
    layer.add_annotation(
        mention=[(75, 79), (80, 88)], entity=[(42, 43), (43, 51), (51, 52)]
    )
    # A character span inside a word covers that word
    text.add_layer(layer)
    model = only(layer)
    assert edges(model) == [("seda raamatut", '" Sipsikut "', "entity")]

    flat = Text("Mari tuli.").tag_layer(["words", "sentences"])
    partial = add_relations(flat, "p", ["a", "b"], [{"a": "ar", "b": "ul"}])
    assert edges(only(partial)) == [("Mari", "tuli", "b")]


def test_sentence_groups_hide_sentences_between():
    text = Text("Mari tuli. Jüri läks. Ta naeris.").tag_layer(["words", "sentences"])
    layer = add_relations(
        text, "coref", ["mention", "entity"], [{"mention": "Ta", "entity": "Mari"}]
    )
    ((sentences, model),) = extract_relations(layer, RelationConfig())
    assert sentences == (0, 2)
    hidden = {i for i in range(len(model.words)) if i not in model.visible}
    assert [model.words[i] for i in sorted(hidden)] == ["Jüri", "läks", "."]


def test_without_sentence_layer():
    text = Text("Mari tuli. Ta naeris.").tag_layer(["words"])
    layer = add_relations(
        text, "coref", ["mention", "entity"], [{"mention": "Ta", "entity": "Mari"}]
    )
    ((sentences, model),) = extract_relations(layer, RelationConfig())
    assert sentences == (0,) and len(model.words) == 6


def test_select_sentence_relation_and_highlight(roles):
    config = RelationConfig()
    assert [s for s, _ in extract_relations(roles, config, sentence=-1)] == [(2,)]
    # A sentence without relations gives an empty diagram of that sentence
    plain = Text("Mari tuli. Jüri läks.").tag_layer(["words", "sentences"])
    layer = add_relations(plain, "r", ["a", "b"], [{"a": "Mari", "b": "tuli"}])
    ((sentences, model),) = extract_relations(layer, config, sentence=1)
    assert sentences == (1,) and model.edges == () and model.words[0] == "Jüri"

    models = extract_relations(roles, config, relation=[roles[2]])
    assert [s for s, _ in models] == [(2,)]
    models = extract_relations(roles, config, highlight=roles[1])
    assert [s for s, _ in models] == [(1,)]
    model = models[0][1]
    assert all(e.highlight for e in model.edges)
    assert {texts(model, n) for n in model.nodes if n.highlight} == {
        "kohtusid",
        "John",
        "Mari",
    }
    # Highlight within a sentence group marks only that relation
    _, model = extract_relations(roles, config, sentence=0, highlight=roles[0])[0]
    assert all(e.highlight for e in model.edges)


def test_attach_to_syntactic_head():
    raw = "Alar Karis kohtus eile Tallinnas."
    text = make_text(
        raw, [([3, 1, 0, 3, 3, 3], "nsubj flat root advmod obl punct".split())]
    )
    layer = add_relations(
        text, "roles", ["verb", "arg0"], [{"verb": "kohtus", "arg0": "Alar Karis"}]
    )
    model = only(layer, attach="head", syntax_layer="stanza_syntax")
    anchors = {texts(model, n): n.anchor for n in model.nodes}
    assert anchors == {"Alar Karis": 0, "kohtus": 2}
    assert only(layer).nodes[0].anchor is None


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"hub": "nope"}, "hub 'nope' is not a span name"),
        ({"label": "nope"}, "label 'nope' is not an attribute"),
        ({"hub_label": "nope"}, "hub_label 'nope'"),
        ({"attach": "left"}, "attach must be"),
        ({"attach": "head"}, "needs a syntax_layer"),
        ({"words_layer": "nope"}, "Word layer 'nope' is missing"),
        ({"attach": "head", "syntax_layer": "nope"}, "Syntax layer 'nope'"),
    ],
)
def test_config_errors(temporal, kwargs, message):
    with pytest.raises(ValueError, match=message):
        extract_relations(temporal, RelationConfig(**kwargs))


def test_selection_errors(temporal, coref):
    config = RelationConfig()
    with pytest.raises(TypeError, match="RelationLayer"):
        extract_relations(temporal.text_object.words, config)
    with pytest.raises(ValueError, match="not in 'temporal_relations'"):
        extract_relations(temporal, config, relation=coref[0])
    with pytest.raises(ValueError, match="not drawn"):
        extract_relations(temporal, config, relation=temporal[0], highlight=temporal[1])
    with pytest.raises(ValueError, match="must be a Relation"):
        extract_relations(temporal, config, relation=[0])
    with pytest.raises(ValueError, match="out of range"):
        extract_relations(temporal, config, sentence=5)


# Visualiser


def test_visualiser_outputs(coref, roles):
    vis = RelationVisualiser(
        rows=[("morph_analysis", "partofspeech")], hub_label="sense"
    )
    svgs = vis.svgs(roles)
    assert len(svgs) == 3
    root = ET.fromstring(svgs[0])
    assert [e.text for e in root.iter() if e.get("class") == "row-label"] == [
        "partofspeech"
    ]
    html = vis.html_output(roles)
    assert html.count('<div style="overflow-x:auto') == 3
    with pytest.raises(ValueError, match="gives 3 diagrams"):
        vis.svg(roles)
    svg = vis.svg(roles, highlight=roles[0], window=0)
    words = [e.text for e in ET.fromstring(svg).iter() if e.get("class") == "word"]
    assert words == [
        "President",
        "Bush",
        "kohtus",
        "temaga",
        "privaatselt",
        "Valges",
        "Majas",
        "teisipäeval",
    ]
    assert RelationVisualiser().svg(coref).startswith("<svg")


def test_visualiser_call_displays(monkeypatch, temporal):
    shown = []
    monkeypatch.setattr(
        relation_visualiser_module, "display_html", lambda html, raw: shown.append(html)
    )
    RelationVisualiser(label="rel_type")(temporal)
    assert len(shown) == 1 and "BEFORE" in shown[0]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"ambiguous": "some"}, "ambiguous must be"),
        ({"attach": "left"}, "attach must be"),
        ({"attach": "head"}, "needs a syntax_layer"),
    ],
)
def test_visualiser_errors(kwargs, message):
    with pytest.raises(ValueError, match=message):
        RelationVisualiser(**kwargs)

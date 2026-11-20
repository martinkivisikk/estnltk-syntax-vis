# estnltk-syntax-vis

Dependency tree and relation layer visualisers for [EstNLTK](https://github.com/estnltk/estnltk): SVG arc diagrams, attribute rows under words and configurable span highlighting. Work in progress.

## Setup

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # package and dev tools (pytest, ruff, JupyterLab)
uv run pytest    # tests
```

## Demo notebook

```bash
uv run jupyter lab notebooks/demo.ipynb
```

The notebook parses Estonian text with EstNLTK's MaltParser (`maltparser_syntax`), which
needs Java (e.g. OpenJDK) installed.

## Usage

```python
from estnltk import Text
from estnltk_syntax_vis import DependencyTreeVisualiser

text = Text("Eesti Vabariigi president Alar Karis kohtus eile Tallinnas Soome peaministriga.")
text.tag_layer(["maltparser_syntax", "ner"])

vis = DependencyTreeVisualiser(
    syntax_layer="maltparser_syntax",   # default: "stanza_syntax" (StanzaSyntaxTagger)
    rows=[("morph_analysis", "partofspeech"), ("morph_analysis", "form")],
    overlay_layer="ner",
    overlay_label="nertag",
)
vis(text)                                    # display in Jupyter
vis(text, highlight=text.ner[1], window=0)   # only the fragment and its head
svg = vis.svg(text, sentence=0)              # SVG string
```

For rows from ambiguous layers such as `morph_analysis`, `ambiguous="first"` (default)
shows the first annotation's value and `ambiguous="all"` the distinct values joined
with `|`. `ambiguous` applies only to `rows`: overlay labels from an ambiguous
`overlay_layer` always show all distinct values.

## Relation layers

A `RelationLayer` can be the overlay of a dependency tree. Each named span of each
relation becomes a box labelled `name (index)`, with the relation's index in the layer;
`overlay_label` names a relation attribute shown as a second line. Overlapping boxes
(also in span layers) get their own label lines, and nested boxes enclose each other.

```python
DependencyTreeVisualiser(
    syntax_layer="maltparser_syntax",
    overlay_layer="temporal_relations",
    overlay_label="rel_type",
)(text)
```

`RelationArcVisualiser` draws an EstNLTK `RelationLayer` as arcs between span boxes
(examples in `notebooks/relations.ipynb`). Each relation is a star from its first
filled span (or `hub`) to its other spans; sentences linked by relations share one
diagram.

```python
from estnltk_syntax_vis import RelationArcVisualiser

RelationArcVisualiser()(text.coreference)              # mention → entity
RelationArcVisualiser(label="rel_type")(text.temporal_relations)
vis = RelationArcVisualiser(hub="verb", hub_label="sense_id", span_names=True)
vis(layer, highlight=layer[0], window=0)               # one relation, its spans only

# Span layers as tracks of boxes under the words; highlight takes spans too
vis = RelationArcVisualiser(annotations=[("ner", "nertag")])
vis(layer, highlight=text.ner[0])
```

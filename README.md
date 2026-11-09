# estnltk-syntax-vis

Dependency tree visualiser for [EstNLTK](https://github.com/estnltk/estnltk) `Text` objects: SVG arc diagrams, attribute rows under words and configurable span highlighting. Work in progress.

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
    span_layer="ner",
    span_label="nertag",
)
vis(text)                                    # display in Jupyter
vis(text, highlight=text.ner[1], window=0)   # only the fragment and its head
svg = vis.svg(text, sentence=0)              # SVG string
```

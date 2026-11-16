"""`DependencyTreeVisualiser`: dependency trees of EstNLTK `Text` objects."""

from collections.abc import Sequence

from estnltk import Text
from IPython.display import display_html

from .extract import ExtractionConfig, Highlight, RowSpec, extract
from .model import window as apply_window
from .style import Style
from .svg import html_blocks, render_svg


class DependencyTreeVisualiser:
    """Draws the dependency trees of a `Text` as SVG arc diagrams.

    Configure once, then apply to many texts::

        vis = DependencyTreeVisualiser(
            syntax_layer="stanza_syntax",
            rows=[("morph_analysis", "partofspeech"), ("morph_analysis", "form")],
            overlay_layer="ner",
            overlay_label="nertag",
        )
        vis(text)                     # display all sentences in a notebook
        vis(text, highlight=text.ner[0], window=0)  # a fragment around an NE
        svg = vis.svg(text, sentence=0)

    Parameters
    ----------
    syntax_layer
        Layer with the attributes `id`, `head` (0 = root) and `deprel`; its spans
        are the words of the diagram.
    sentence_layer
        Layer of sentences; one diagram per sentence.
    rows
        Rows drawn under the words, each `(layer, attribute)`, `(label, function)`
        or `function`. Functions get the word's span of the syntax layer.
    overlay_layer, overlay_label
        Optional layer drawn as boxes over the words, each box covering the
        words fully inside its span. For a span layer (e.g. named entities)
        each span is a box labelled with the attribute `overlay_label`. For a
        `RelationLayer` each named span of each relation is a box labelled
        `name (index)`, with the relation's index in the layer (as in
        `RelationLayer.display()`); `overlay_label` is then a relation
        attribute, shown as a second line in the box. Overlapping boxes get
        separate label lines and semi-transparent fills, so nested boxes
        enclose each other and overlapping regions are darker. For ambiguous
        overlay layers the label always shows all distinct values joined with
        `|`; `ambiguous` does not apply to it.
    ambiguous
        For `rows` from ambiguous layers (e.g. `morph_analysis`): show the
        `"first"` annotation's value or `"all"` distinct values joined with `|`.
    missing
        Shown when a row has no span or value for a word.
    style
        Colours and sizes, see `Style`.
    render_svg_as_img
        In `html_output()` and notebook display, put each SVG in an `<img>` as a
        base64 data URI instead of inline `<svg>`. Use it for notebooks whose
        saved outputs should show the diagrams when opened without re-running
        (Jupyter strips inline SVG from untrusted outputs). Off by default:
        GitHub's notebook viewer blocks such data URIs and shows a broken image
        instead (it shows inline SVG), text in an `<img>` cannot be selected or
        searched, and page CSS cannot style it. `svg()` and `svgs()` always
        return plain SVG.
    """

    def __init__(
        self,
        syntax_layer: str = "stanza_syntax",
        rows: Sequence[RowSpec] = (),
        overlay_layer: str | None = None,
        overlay_label: str | None = None,
        sentence_layer: str = "sentences",
        ambiguous: str = "first",
        missing: str = "-",
        style: Style | None = None,
        render_svg_as_img: bool = False,
    ):
        if ambiguous not in ("first", "all"):
            raise ValueError(f"ambiguous must be 'first' or 'all', got {ambiguous!r}")
        self.config = ExtractionConfig(
            syntax_layer=syntax_layer,
            sentence_layer=sentence_layer,
            rows=tuple(rows),
            overlay_layer=overlay_layer,
            overlay_label=overlay_label,
            ambiguous=ambiguous,
            missing=missing,
        )
        self.style = style or Style()
        self.render_svg_as_img = render_svg_as_img

    def svgs(
        self,
        text: Text,
        sentence: int | None = None,
        highlight: Highlight = None,
        window: int | None = None,
    ) -> list[str]:
        """SVG strings of all sentences, or of the one selected by `sentence` or
        `highlight`.

        `highlight` is a span (e.g. `text.ner[0]`), several spans (e.g.
        `text.words[3:5]` or a list of word spans) or word indices within
        `sentence`. `window` keeps only the highlight, `window` words on each side
        of every highlighted word and the heads the highlight attaches to;
        `window=0` draws just the fragment.
        """
        svgs = []
        for _, model in extract(text, self.config, sentence, highlight):
            if window is not None:
                model = apply_window(model, window)
            svgs.append(render_svg(model, self.style))
        return svgs

    def svg(
        self,
        text: Text,
        sentence: int | None = None,
        highlight: Highlight = None,
        window: int | None = None,
    ) -> str:
        """SVG string of one sentence (see `svgs` for the arguments).

        The sentence is `sentence`, the one containing `highlight`, or the only
        sentence of a one-sentence text.
        """
        if sentence is None and highlight is None:
            n = (
                len(text[self.config.sentence_layer])
                if (self.config.sentence_layer in text.layers)
                else 0
            )
            if n != 1:
                raise ValueError(
                    f"the Text has {n} sentences; give `sentence` or `highlight`"
                )
            sentence = 0
        return self.svgs(text, sentence, highlight, window)[0]

    def html_output(
        self,
        text: Text,
        sentence: int | None = None,
        highlight: Highlight = None,
        window: int | None = None,
    ) -> str:
        """HTML with the diagrams (see `svgs` for the arguments).

        Each diagram is in its own horizontally scrollable `div`; wide diagrams
        scroll instead of being scaled down to the notebook cell width.
        """
        return html_blocks(
            self.svgs(text, sentence, highlight, window), as_img=self.render_svg_as_img
        )

    def __call__(
        self,
        text: Text,
        sentence: int | None = None,
        highlight: Highlight = None,
        window: int | None = None,
    ) -> None:
        """Display the diagrams in a notebook (see `svgs` for the arguments)."""
        display_html(self.html_output(text, sentence, highlight, window), raw=True)

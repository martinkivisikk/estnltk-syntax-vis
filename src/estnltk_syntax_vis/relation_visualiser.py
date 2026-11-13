"""`RelationVisualiser`: EstNLTK relation layers as SVG arc diagrams."""

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from estnltk_core import RelationLayer
from estnltk_core.layer.relation_layer import Relation
from IPython.display import display_html

from .extract import RowSpec
from .relation_extract import EdgeSpec, RelationConfig, extract_relations, target_name
from .relation_model import relation_window
from .relation_svg import render_relation_svg
from .style import Style

Relations = Relation | Iterable[Relation] | None


class RelationVisualiser:
    """Draws the relations of a `RelationLayer` as arcs between span boxes.

    Each relation becomes edges between its named spans. By default this is a
    star from the relation's first filled span (in the layer's `span_names`
    order) to each other filled span, so a two-span layer (`mention`, `entity`)
    gets one arc per relation and a PropBank-style layer (`verb`, `arg0`, ...)
    gets arcs from the verb to its arguments. Sentences linked by relations are
    drawn in one diagram, with "…" for the sentences between them::

        vis = RelationVisualiser(label="rel_type")
        vis(text["temporal_relations"])          # display in a notebook
        vis(layer, highlight=layer[0], window=2) # one relation, 2 words around
        svg = vis.svg(layer, relation=layer[0])

    Parameters
    ----------
    hub
        Span name of the centre of each relation's star (e.g. `"verb"`);
        relations without that span fall back to their first filled span.
    edges
        Function `relation -> [(source, target), ...]` or `(source, target,
        label)` triples of span names, replacing the star (e.g. for chains).
        Pairs with an unfilled span are skipped.
    label
        Edge label: the target span's name (default), the name of a relation
        attribute (distinct values of ambiguous relations joined with `|`), a
        function `(relation, source, target) -> str`, or `None` for no labels.
    span_names
        Show the span names in the labels under the span boxes.
    hub_label
        A relation attribute (e.g. `"sense_id"`) shown under the hub span.
    attach
        Where arcs attach to multi-word spans: `"centre"` of the span or the
        span's syntactic `"head"` word (needs `syntax_layer`).
    words_layer
        Layer whose spans are the words (columns) of the diagram.
    sentence_layer
        Layer of sentences; without it, the whole text is one diagram.
    syntax_layer
        Layer with the attributes `id` and `head`, used by `attach="head"`.
    rows, ambiguous, missing
        Rows drawn under the words, as in `DependencyTreeVisualiser`; functions
        get the word's span of `words_layer`.
    style
        Colours and sizes, see `Style`.
    """

    def __init__(
        self,
        hub: str | None = None,
        edges: Callable[[Relation], Iterable[EdgeSpec]] | None = None,
        label: str | Callable[[Relation, str, str], Any] | None = target_name,
        span_names: bool = False,
        hub_label: str | None = None,
        attach: str = "centre",
        words_layer: str = "words",
        sentence_layer: str = "sentences",
        syntax_layer: str | None = None,
        rows: Sequence[RowSpec] = (),
        ambiguous: str = "first",
        missing: str = "-",
        style: Style | None = None,
    ):
        if ambiguous not in ("first", "all"):
            raise ValueError(f"ambiguous must be 'first' or 'all', got {ambiguous!r}")
        if attach not in ("centre", "head"):
            raise ValueError(f"attach must be 'centre' or 'head', got {attach!r}")
        if attach == "head" and syntax_layer is None:
            raise ValueError("attach='head' needs a syntax_layer")
        self.config = RelationConfig(
            hub=hub,
            edges=edges,
            label=label,
            span_names=span_names,
            hub_label=hub_label,
            attach=attach,
            words_layer=words_layer,
            sentence_layer=sentence_layer,
            syntax_layer=syntax_layer,
            rows=tuple(rows),
            ambiguous=ambiguous,
            missing=missing,
        )
        self.style = style or Style()

    def svgs(
        self,
        layer: RelationLayer,
        sentence: int | None = None,
        relation: Relations = None,
        highlight: Relations = None,
        window: int | None = None,
    ) -> list[str]:
        """SVG strings of all sentence groups, or of those selected.

        `relation` (a Relation or several) draws only those relations.
        `sentence` keeps the group that contains that sentence. `highlight`
        (Relations) emphasises relations and, without `sentence`, keeps only the
        groups that contain them. `window` keeps only the spans of the
        highlighted relations (or of all drawn ones) and `window` words on each
        side; `window=0` draws just the spans.
        """
        svgs = []
        for _, model in extract_relations(
            layer, self.config, sentence, relation, highlight
        ):
            if window is not None:
                model = relation_window(model, window)
            svgs.append(render_relation_svg(model, self.style))
        return svgs

    def svg(
        self,
        layer: RelationLayer,
        sentence: int | None = None,
        relation: Relations = None,
        highlight: Relations = None,
        window: int | None = None,
    ) -> str:
        """SVG string of one diagram (see `svgs` for the arguments).

        Raises `ValueError` when the selection gives more than one diagram.
        """
        svgs = self.svgs(layer, sentence, relation, highlight, window)
        if len(svgs) != 1:
            raise ValueError(
                f"the selection gives {len(svgs)} diagrams; give `sentence`, "
                f"`relation` or `highlight`, or use `svgs`"
            )
        return svgs[0]

    def html_output(
        self,
        layer: RelationLayer,
        sentence: int | None = None,
        relation: Relations = None,
        highlight: Relations = None,
        window: int | None = None,
    ) -> str:
        """HTML with the diagrams (see `svgs` for the arguments).

        Each diagram is in its own horizontally scrollable `div`.
        """
        return "\n".join(
            f'<div style="overflow-x:auto;margin-bottom:12px">{svg}</div>'
            for svg in self.svgs(layer, sentence, relation, highlight, window)
        )

    def __call__(
        self,
        layer: RelationLayer,
        sentence: int | None = None,
        relation: Relations = None,
        highlight: Relations = None,
        window: int | None = None,
    ) -> None:
        """Display the diagrams in a notebook (see `svgs` for the arguments)."""
        display_html(
            self.html_output(layer, sentence, relation, highlight, window), raw=True
        )

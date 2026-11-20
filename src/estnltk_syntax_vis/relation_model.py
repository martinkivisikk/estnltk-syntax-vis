"""Plain model of a relation diagram: words, span nodes and labelled edges.

The model does not depend on EstNLTK: `relation_extract.py` builds it from a
`RelationLayer`, tests and other callers can build it directly.
"""

from dataclasses import dataclass, field, replace

from .model import Row


@dataclass(frozen=True)
class SpanNode:
    """A span over the words `start .. end - 1` that edges connect.

    Edges attach at the span's centre, or at the word `anchor` when it is set
    (e.g. the span's syntactic head). `label` is drawn under the span.
    """

    start: int
    end: int
    label: str = ""
    anchor: int | None = None
    highlight: bool = False


@dataclass(frozen=True)
class Edge:
    """A directed edge from node `source` to node `target` (node indices)."""

    source: int
    target: int
    label: str = ""
    highlight: bool = False


@dataclass(frozen=True)
class Annotation:
    """A span of an annotation layer over the words `start .. end - 1`."""

    start: int
    end: int
    label: str = ""
    highlight: bool = False


@dataclass(frozen=True)
class Track:
    """An annotation layer drawn as boxes under the rows; `label` names it."""

    label: str
    annotations: tuple[Annotation, ...]


@dataclass(frozen=True)
class RelationModel:
    """Words, span nodes, edges, rows and annotation tracks of one diagram.

    `highlight` holds word indices to emphasise besides the words of
    highlighted nodes (e.g. the words of a highlighted annotation span).
    `visible` limits the drawing to some words (`None` = all); hidden stretches
    are drawn as "…" and edges to nodes without visible words are left out.
    """

    words: tuple[str, ...]
    nodes: tuple[SpanNode, ...]
    edges: tuple[Edge, ...]
    rows: tuple[Row, ...] = ()
    tracks: tuple[Track, ...] = ()
    highlight: frozenset[int] = field(default_factory=frozenset)
    visible: frozenset[int] | None = None

    def __post_init__(self) -> None:
        n = len(self.words)
        for node in self.nodes:
            if not 0 <= node.start < node.end <= n:
                raise ValueError(f"node {node} is outside the words")
            if node.anchor is not None and not node.start <= node.anchor < node.end:
                raise ValueError(f"anchor of node {node} is outside the node")
        for edge in self.edges:
            ends = (edge.source, edge.target)
            if any(not 0 <= k < len(self.nodes) for k in ends):
                raise ValueError(f"edge {edge} refers to a missing node")
            if edge.source == edge.target:
                raise ValueError(f"edge {edge} connects a node to itself")
        for row in self.rows:
            if len(row.values) != n:
                raise ValueError(
                    f"row {row.label!r} has {len(row.values)} values for {n} words"
                )
        for track in self.tracks:
            for annotation in track.annotations:
                if not 0 <= annotation.start < annotation.end <= n:
                    raise ValueError(
                        f"annotation {annotation} of track {track.label!r} is "
                        f"outside the words"
                    )
        if any(not 0 <= i < n for i in self.highlight):
            raise ValueError("highlight contains word indices outside the words")
        if self.visible is not None:
            if not self.visible:
                raise ValueError("visible must contain at least one word")
            if any(not 0 <= i < n for i in self.visible):
                raise ValueError("visible contains word indices outside the words")

    @property
    def visible_words(self) -> tuple[int, ...]:
        """Indices of the words to draw, in order."""
        if self.visible is None:
            return tuple(range(len(self.words)))
        return tuple(sorted(self.visible))

    @property
    def highlight_words(self) -> frozenset[int]:
        """Words of the highlighted nodes and the `highlight` words."""
        return self.highlight | frozenset(
            i
            for node in self.nodes
            if node.highlight
            for i in range(node.start, node.end)
        )


def relation_window(model: RelationModel, size: int) -> RelationModel:
    """Show only the focus words and `size` words on each side of them.

    The focus is the highlighted words (of nodes and `highlight`), or the words
    of all nodes when nothing is highlighted. Words that are already hidden stay
    hidden. Without a focus the model is returned unchanged.
    """
    if size < 0:
        raise ValueError(f"window size must be >= 0, got {size}")
    focus = model.highlight_words or {
        i for node in model.nodes for i in range(node.start, node.end)
    }
    if not focus:
        return model
    n = len(model.words)
    keep = {j for i in focus for j in range(max(i - size, 0), min(i + size + 1, n))}
    if model.visible is not None:
        keep &= model.visible
    if not keep:
        return model
    return replace(model, visible=frozenset(keep))

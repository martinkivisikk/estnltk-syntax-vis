"""Plain model of a relation diagram: words, span nodes and labelled edges.

The model does not depend on EstNLTK: `relation_extract.py` builds it from a
`RelationLayer`, tests and other callers can build it directly.
"""

from dataclasses import dataclass, replace

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
class RelationModel:
    """Words, span nodes, edges and rows of one relation diagram.

    `visible` limits the drawing to some words (`None` = all); hidden stretches
    are drawn as "…" and edges to nodes without visible words are left out.
    """

    words: tuple[str, ...]
    nodes: tuple[SpanNode, ...]
    edges: tuple[Edge, ...]
    rows: tuple[Row, ...] = ()
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
        """Words of the highlighted nodes."""
        return frozenset(
            i
            for node in self.nodes
            if node.highlight
            for i in range(node.start, node.end)
        )


def relation_window(model: RelationModel, size: int) -> RelationModel:
    """Show only the nodes' words and `size` words on each side of them.

    The nodes are the highlighted ones, or all nodes when none is highlighted.
    Words that are already hidden stay hidden. Without nodes the model is
    returned unchanged.
    """
    if size < 0:
        raise ValueError(f"window size must be >= 0, got {size}")
    focus = [node for node in model.nodes if node.highlight] or list(model.nodes)
    if not focus:
        return model
    n = len(model.words)
    keep = {
        j
        for node in focus
        for j in range(max(node.start - size, 0), min(node.end + size, n))
    }
    if model.visible is not None:
        keep &= model.visible
    if not keep:
        return model
    return replace(model, visible=frozenset(keep))

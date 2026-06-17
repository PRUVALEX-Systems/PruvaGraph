"""
Graph builder -- Stage 3 of the pipeline.

Takes the flat list of per-file extraction dicts (from tree-sitter/regex
code extraction + LLM doc extraction + cache hits + dedup projections) and
merges them into a single :class:`networkx.MultiDiGraph`.

- Nodes are deduplicated by ``id``. If the same id appears in multiple
  extractions (e.g. an external package imported by many files), the first
  non-empty value for each attribute wins.
- Edges reference nodes by id. If an edge points at a node we haven't seen
  yet (e.g. an external package, or a cross-file symbol), a minimal stub
  node is created so the graph stays well-formed.
"""
from __future__ import annotations

from typing import Any

import networkx as nx

_NODE_DEFAULTS: dict[str, Any] = {
    "label": None,
    "type": "unknown",
    "file": None,
    "lang": None,
    "summary": None,
    "community": None,
}


def build_nx_graph(extractions: list[dict[str, Any]]) -> nx.MultiDiGraph:
    """
    Merge per-file extraction results into one knowledge graph.

    Args:
        extractions: List of ``{"nodes": [...], "edges": [...], ...}`` dicts,
                      one per processed file (code, doc, cache hit, or dedup
                      projection).

    Returns:
        A :class:`networkx.MultiDiGraph` with every node carrying at least
        ``label``, ``type``, ``file``, ``lang``, ``summary``, ``community``.
    """
    G = nx.MultiDiGraph()

    # Single-pass loop (B1 fix — avoids iterating extractions twice)
    all_edges: list[dict[str, Any]] = []
    for extraction in extractions:
        for node in extraction.get("nodes", []) or []:
            _add_or_merge_node(G, node)
        all_edges.extend(extraction.get("edges", []) or [])

    for edge in all_edges:
        _add_edge(G, edge)

    _dedupe_parallel_edges(G)
    return G


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _add_or_merge_node(G: nx.MultiDiGraph, node: dict[str, Any]) -> None:
    node_id = node.get("id")
    if not node_id:
        return

    attrs = {**_NODE_DEFAULTS, **{k: v for k, v in node.items() if k != "id"}}
    if attrs.get("label") is None:
        attrs["label"] = node_id

    if not G.has_node(node_id):
        G.add_node(node_id, **attrs)
        return

    # Merge: fill in any attribute that's currently empty/None/unknown.
    existing = G.nodes[node_id]
    for key, value in attrs.items():
        if value in (None, ""):
            continue
        if existing.get(key) in (None, "", "unknown"):
            existing[key] = value


def _add_edge(G: nx.MultiDiGraph, edge: dict[str, Any]) -> None:
    src, tgt = edge.get("source"), edge.get("target")
    if not src or not tgt or src == tgt:
        return
    relation = edge.get("relation", "related")

    for node_id in (src, tgt):
        if not G.has_node(node_id):
            stub = {**_NODE_DEFAULTS, "label": node_id, "type": "external"}
            G.add_node(node_id, **stub)

    G.add_edge(src, tgt, relation=relation)


def _dedupe_parallel_edges(G: nx.MultiDiGraph) -> None:
    """Collapse exact-duplicate (source, target, relation) edges."""
    seen: set[tuple[str, str, str]] = set()
    to_remove: list[tuple[str, str, int]] = []

    for u, v, key, data in G.edges(keys=True, data=True):
        sig = (u, v, data.get("relation", ""))
        if sig in seen:
            to_remove.append((u, v, key))
        else:
            seen.add(sig)

    for u, v, key in to_remove:
        if G.has_edge(u, v, key):
            G.remove_edge(u, v, key)

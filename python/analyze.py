"""
Graph analysis -- Stage 5a of the pipeline.

Computes the numbers that ``report.py`` turns into ``GRAPH_REPORT.md``:
  - Overall stats (node/edge counts, breakdown by type and language)
  - "God nodes" -- highly-connected hubs, often refactor candidates
  - Isolated nodes -- dead code / orphaned files
  - Most-used external dependencies
  - Cross-community edges -- "surprising connections" between otherwise
    separate parts of the architecture
  - Per-community summaries
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import networkx as nx

GOD_NODE_LIMIT = 15
TOP_EXTERNAL_LIMIT = 10
SURPRISING_EDGE_LIMIT = 15


def analyze(G: nx.MultiDiGraph) -> dict[str, Any]:
    """Compute summary analytics for *G*. Safe to call on an empty graph."""
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    by_type = Counter(d.get("type", "unknown") for _, d in G.nodes(data=True))
    by_lang = Counter(d.get("lang") for _, d in G.nodes(data=True) if d.get("lang"))

    god_nodes = _god_nodes(G)
    isolated = _isolated_nodes(G)
    external = _top_external(G)
    communities = _community_summaries(G)
    surprising = _cross_community_edges(G)

    return {
        "total_nodes": n_nodes,
        "total_edges": n_edges,
        "by_type": dict(by_type),
        "by_lang": dict(by_lang),
        "god_nodes": god_nodes,
        "isolated_nodes": isolated,
        "external_deps": external,
        "communities": communities,
        "surprising_connections": surprising,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _god_nodes(G: nx.MultiDiGraph) -> list[dict[str, Any]]:
    """Top nodes by total degree -- heavily depended-on or heavily-coupled."""
    scored = []
    for node_id, data in G.nodes(data=True):
        in_deg = G.in_degree(node_id)
        out_deg = G.out_degree(node_id)
        total = in_deg + out_deg
        if total == 0:
            continue
        scored.append({
            "id": node_id,
            "label": data.get("label", node_id),
            "type": data.get("type"),
            "file": data.get("file"),
            "in_degree": in_deg,
            "out_degree": out_deg,
            "total_degree": total,
        })
    scored.sort(key=lambda n: n["total_degree"], reverse=True)
    return scored[:GOD_NODE_LIMIT]


def _isolated_nodes(G: nx.MultiDiGraph) -> list[dict[str, Any]]:
    """Nodes with zero edges -- candidates for dead-code review."""
    out = []
    for node_id, data in G.nodes(data=True):
        if G.degree(node_id) == 0:
            out.append({
                "id": node_id,
                "label": data.get("label", node_id),
                "type": data.get("type"),
                "file": data.get("file"),
            })
    return out


def _top_external(G: nx.MultiDiGraph) -> list[dict[str, Any]]:
    """Most-imported external packages, by in-degree."""
    out = []
    for node_id, data in G.nodes(data=True):
        if data.get("type") != "external":
            continue
        out.append({
            "id": node_id,
            "label": data.get("label", node_id),
            "used_by": G.in_degree(node_id),
        })
    out.sort(key=lambda n: n["used_by"], reverse=True)
    return out[:TOP_EXTERNAL_LIMIT]


def _community_summaries(G: nx.MultiDiGraph) -> dict[int, dict[str, Any]]:
    groups: dict[int, list[tuple[str, dict[str, Any]]]] = {}
    for node_id, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is None:
            continue
        groups.setdefault(cid, []).append((node_id, data))

    summaries: dict[int, dict[str, Any]] = {}
    for cid, members in groups.items():
        type_counts = Counter(d.get("type", "unknown") for _, d in members)
        files = {d.get("file") for _, d in members if d.get("file")}
        sample_labels = [d.get("label", n) for n, d in members[:8]]
        summaries[cid] = {
            "size": len(members),
            "by_type": dict(type_counts),
            "file_count": len(files),
            "sample_labels": sample_labels,
        }
    return summaries


def _cross_community_edges(G: nx.MultiDiGraph) -> list[dict[str, Any]]:
    """
    Edges that cross between two different communities -- often the most
    "surprising" architectural connections (e.g. a UI component importing
    a database driver directly).
    """
    out = []
    for u, v, data in G.edges(data=True):
        cu = G.nodes[u].get("community")
        cv = G.nodes[v].get("community")
        if cu is None or cv is None or cu == cv:
            continue
        relation = data.get("relation", "related")
        if relation in ("imports",) and G.nodes[v].get("type") == "external":
            continue  # external package usage isn't "surprising"
        out.append({
            "source": u,
            "source_label": G.nodes[u].get("label", u),
            "target": v,
            "target_label": G.nodes[v].get("label", v),
            "relation": relation,
            "source_community": cu,
            "target_community": cv,
        })

    out.sort(key=lambda e: (e["source_community"], e["target_community"]))
    return out[:SURPRISING_EDGE_LIMIT]

"""
N8 — Community Meta-Summary Generator

After Leiden/Louvain community detection, generates one summary per community
using free statistical aggregation (no LLM) or one LLM call per community
(amortized across all future queries).

Without this: every query sends full graph → expensive
With this: query answered using pre-computed community summaries → cheap
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import networkx as nx


def generate_community_summaries(
    G: nx.MultiDiGraph,
    out_dir: Path,
    backend: str = "none",
) -> dict[int, str]:
    """
    Generate text summaries for each community.
    Adds a virtual __community__N node to the graph for fast querying.

    backend="none"  → free statistical summaries only
    backend=*       → one LLM call per community (still 100x cheaper than per-file)
    """
    communities: dict[int, list[tuple[str, dict]]] = {}
    for node_id, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is None:
            continue
        communities.setdefault(int(cid), []).append((node_id, data))

    summaries: dict[int, str] = {}

    for cid, members in sorted(communities.items()):
        # Free statistical summary
        free_summary = _stat_summary(cid, members)
        summaries[cid] = free_summary

        # Add virtual community node to graph
        comm_node_id = f"__community__{cid}"
        G.add_node(
            comm_node_id,
            label=f"Community {cid}",
            type="community",
            summary=free_summary,
            size=len(members),
            file=None,
        )
        # Link community node to its top members
        top_members = _top_nodes_by_degree(G, [n for n, _ in members], k=5)
        for m in top_members:
            G.add_edge(comm_node_id, m, relation="contains")

        # Optional: LLM-enhanced summary (1 call per community)
        if backend != "none" and len(members) >= 3:
            try:
                enhanced = _llm_summarise_community(cid, members[:12], backend)
                if enhanced:
                    summaries[cid] = enhanced
                    G.nodes[comm_node_id]["summary"] = enhanced
            except Exception:
                pass  # keep free summary

    # Persist
    out_file = out_dir / "community_summaries.json"
    out_file.write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summaries


def load_community_summaries(out_dir: Path) -> dict[int, str]:
    """Load previously generated community summaries."""
    path = out_dir / "community_summaries.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {int(k): v for k, v in raw.items()}
    except Exception:
        return {}


# ── Free statistical summary ───────────────────────────────────────────────────

def _stat_summary(cid: int, members: list[tuple[str, dict]]) -> str:
    """Build a descriptive summary using only statistics — zero LLM."""
    type_counts = Counter(d.get("type", "?") for _, d in members)
    dominant_type, _ = type_counts.most_common(1)[0]

    # Collect representative labels (non-external, non-concept)
    labels = [
        d.get("label", n)
        for n, d in members
        if d.get("type") not in ("external", "community")
    ][:8]

    files = {
        d.get("file", "").split("/")[-1].split("\\")[-1]
        for _, d in members
        if d.get("file")
    }
    file_str = ", ".join(sorted(files)[:4])

    sample_labels = ", ".join(labels[:5])
    more = f" (+{len(members) - 5} more)" if len(members) > 5 else ""

    return (
        f"Community {cid}: {len(members)} nodes, "
        f"primarily {dominant_type}s. "
        f"Members: {sample_labels}{more}. "
        + (f"Files: {file_str}." if file_str else "")
    )


def _top_nodes_by_degree(
    G: nx.MultiDiGraph,
    node_ids: list[str],
    k: int = 5,
) -> list[str]:
    """Return top-k nodes by degree from a list."""
    valid = [n for n in node_ids if n in G]
    return sorted(valid, key=lambda n: -G.degree(n))[:k]


# ── Optional LLM summary ───────────────────────────────────────────────────────

def _llm_summarise_community(
    cid: int,
    members: list[tuple[str, dict]],
    backend: str,
) -> str | None:
    """
    Single LLM call to summarize a community.
    Returns None if LLM is unavailable.
    """
    context_lines = []
    for node_id, data in members:
        label   = data.get("label", "?")
        ntype   = data.get("type", "?")
        summary = (data.get("summary") or "")[:80]
        context_lines.append(f"- [{ntype}] {label}: {summary}")

    context = "\n".join(context_lines)
    prompt  = (
        f"In 1-2 sentences, describe what this software module group does "
        f"based on these {len(members)} components:\n{context}\n\n"
        f"Write only the description, no preamble."
    )

    try:
        from pruvagraph.router import route_request
        return route_request(prompt, backend=backend, max_tokens=120)
    except Exception:
        return None


# ── Community context builder for queries ─────────────────────────────────────

def build_community_context(
    G: nx.MultiDiGraph,
    summaries: dict[int, str],
    relevant_communities: list[int] | None = None,
) -> str:
    """
    Build a compact community-level context for LLM queries.
    Uses pre-computed summaries — no new LLM calls.

    Token cost: ~50 tokens per community vs ~5000 per raw subgraph
    """
    lines = [f"Architecture: {len(summaries)} detected modules\n"]

    for cid, summary in sorted(summaries.items()):
        if relevant_communities and cid not in relevant_communities:
            continue
        lines.append(f"Module {cid}: {summary}")

    return "\n".join(lines)

"""
A3 — Hierarchical Summary Chain

Builds a 4-level pyramid of summaries at build time:
  Level 1 — Symbol    (individual node summaries)
  Level 2 — Module    (per-file aggregation, free)
  Level 3 — Community (per-cluster, free or 1 LLM call)
  Level 4 — Repo      (1 LLM call ever, cached forever)

Benefit: query routing picks correct level → 90–99% token reduction.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import networkx as nx

# ── Build the hierarchy ───────────────────────────────────────────────────────

def build_summary_hierarchy(
    G: nx.MultiDiGraph,
    out_dir: Path,
    backend: str = "none",
) -> dict:
    """
    Build and persist the 4-level summary hierarchy.
    Returns the hierarchy dict.
    """
    # Level 2: Module summaries (per-file, free)
    module_summaries = _aggregate_by_file(G)

    # Level 3: Community summaries (free statistical)
    community_summaries = _aggregate_communities(G, module_summaries)

    # Level 4: Repo summary
    repo_summary = _aggregate_repo(community_summaries, G, backend)

    hierarchy = {
        "repo":        repo_summary,
        "communities": community_summaries,
        "modules":     module_summaries,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "hierarchy.json").write_text(
        json.dumps(hierarchy, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return hierarchy


def load_hierarchy(out_dir: Path) -> dict:
    """Load previously built hierarchy."""
    path = out_dir / "hierarchy.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ── Level 2: Module (per-file) ────────────────────────────────────────────────

def _aggregate_by_file(G: nx.MultiDiGraph) -> dict[str, str]:
    """
    Group node summaries by source file → module-level summaries.
    Zero LLM — pure aggregation.
    """
    file_nodes: dict[str, list[tuple[str, dict]]] = defaultdict(list)

    for node_id, data in G.nodes(data=True):
        f = data.get("file")
        if f:
            file_nodes[f].append((node_id, data))

    result: dict[str, str] = {}
    for filepath, nodes in file_nodes.items():
        filename = Path(filepath).name
        types    = [d.get("type", "?") for _, d in nodes]
        labels   = [d.get("label", n) for n, d in nodes if d.get("type") not in ("external",)][:6]

        from collections import Counter
        type_counts = Counter(types)
        dominant    = type_counts.most_common(1)[0][0]

        result[filepath] = (
            f"{filename}: {len(nodes)} {dominant}s — "
            + ", ".join(labels[:5])
            + (f" (+{len(nodes)-5} more)" if len(nodes) > 5 else "")
        )

    return result


# ── Level 3: Community ────────────────────────────────────────────────────────

def _aggregate_communities(
    G: nx.MultiDiGraph,
    module_summaries: dict[str, str],
) -> dict[int, str]:
    """
    Aggregate module summaries into community summaries.
    Zero LLM — finds which modules belong to which community.
    """
    comm_files: dict[int, set[str]] = defaultdict(set)
    comm_types: dict[int, list[str]] = defaultdict(list)
    comm_labels: dict[int, list[str]] = defaultdict(list)

    for node_id, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is None:
            continue
        cid = int(cid)
        if data.get("file"):
            comm_files[cid].add(data["file"])
        if data.get("type"):
            comm_types[cid].append(data["type"])
        if data.get("label"):
            comm_labels[cid].append(data["label"])

    from collections import Counter
    result: dict[int, str] = {}

    for cid in sorted(comm_files.keys()):
        files    = sorted(comm_files[cid])
        filenames = [Path(f).name for f in files[:4]]
        types    = Counter(comm_types[cid])
        dominant = types.most_common(1)[0][0] if types else "node"
        labels   = comm_labels[cid][:5]

        result[cid] = (
            f"Community {cid} ({len(comm_labels[cid])} nodes, "
            f"{len(files)} files): "
            f"primarily {dominant}s. "
            f"Key members: {', '.join(labels[:4])}. "
            f"Files: {', '.join(filenames)}"
        )

    return result


# ── Level 4: Repo ─────────────────────────────────────────────────────────────

def _aggregate_repo(
    community_summaries: dict[int, str],
    G: nx.MultiDiGraph,
    backend: str = "none",
) -> str:
    """
    Generate one repo-level summary.
    Free: statistical summary.
    With backend: 1 LLM call, result cached forever.
    """
    n_nodes  = G.number_of_nodes()
    n_edges  = G.number_of_edges()
    n_comm   = len(community_summaries)

    from collections import Counter
    type_counts = Counter(
        data.get("type", "?")
        for _, data in G.nodes(data=True)
        if data.get("type") != "external"
    )

    dominant_types = ", ".join(
        f"{cnt} {t}s" for t, cnt in type_counts.most_common(3)
    )

    free_summary = (
        f"Codebase: {n_nodes:,} nodes, {n_edges:,} edges, "
        f"{n_comm} architectural modules. "
        f"Composition: {dominant_types}."
    )

    if backend == "none" or n_nodes < 10:
        return free_summary

    # Optional: 1 LLM call for natural language repo summary
    # Use top community summaries as context
    top_comms = list(community_summaries.values())[:5]
    context   = "\n".join(f"- {s}" for s in top_comms)
    prompt    = (
        f"In 2-3 sentences, describe what this software project does "
        f"based on its {n_comm} architectural modules:\n{context}\n\n"
        f"Reply with only the description."
    )

    try:
        from pruvagraph.router import route_request
        llm_summary = route_request(prompt, backend=backend, max_tokens=150)
        if llm_summary and len(llm_summary) > 20:
            return llm_summary
    except Exception:
        pass

    return free_summary


# ── Query routing by level ────────────────────────────────────────────────────

def route_query_to_level(question: str) -> str:
    """
    Determine appropriate hierarchy level for a question.
    Returns: "repo" | "community" | "module" | "symbol"
    """
    q_lower = question.lower()

    # Repo-level questions
    if any(kw in q_lower for kw in (
        "overview", "what does this project", "architecture", "high level",
        "overall", "what is this", "kya hai ye project", "repo ke baare"
    )):
        return "repo"

    # Community/module-level questions
    if any(kw in q_lower for kw in (
        "module", "community", "cluster", "layer", "service", "package",
        "component", "subsystem", "how are", "organized"
    )):
        return "community"

    # Module/file-level questions
    if any(kw in q_lower for kw in (
        ".py", ".ts", ".js", ".go", ".rs", "file", "class",
        "interface", "import", "depend"
    )):
        return "module"

    # Default: symbol level (most specific)
    return "symbol"


def get_level_context(hierarchy: dict, level: str) -> str:
    """Get the appropriate context string for a hierarchy level."""
    if level == "repo":
        return hierarchy.get("repo", "")

    if level == "community":
        comms = hierarchy.get("communities", {})
        lines = [f"Module {cid}: {summary}" for cid, summary in list(comms.items())[:10]]
        return "\n".join(lines)

    if level == "module":
        mods = hierarchy.get("modules", {})
        lines = list(mods.values())[:20]
        return "\n".join(lines)

    return ""  # symbol level → use subgraph extractor

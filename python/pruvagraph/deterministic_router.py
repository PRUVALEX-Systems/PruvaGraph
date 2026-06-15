"""
A2 — Deterministic Query Router

Pattern-matches questions to free graph algorithm answers.
60–70% of common dev queries are answerable without ANY LLM call.

Examples answered for FREE:
  "who calls build_graph?"         → BFS in-edges traversal
  "what does pipeline.py depend on?" → BFS out-edges traversal
  "list all communities"           → iterate node communities
  "god nodes" / "most connected"   → degree sorting
  "how many functions?"            → node type count
  "summary of SessionManager"      → direct node lookup
"""
from __future__ import annotations

import re
from typing import Callable

import networkx as nx

# ── Pattern registry ──────────────────────────────────────────────────────────
# Each entry: (compiled_pattern, handler_function)

_PATTERN_HANDLERS: list[tuple[re.Pattern, Callable]] = []


def _register(pattern: str):
    """Decorator to register a pattern handler."""
    def decorator(fn: Callable):
        _PATTERN_HANDLERS.append((re.compile(pattern, re.I), fn))
        return fn
    return decorator


# ── Handlers ──────────────────────────────────────────────────────────────────

@_register(r"(?:who|what)\s+calls?\s+[`\"']?(\w+)[`\"']?")
def _find_callers(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    symbol = m.group(1)
    targets = _find_nodes_by_label(G, symbol)
    if not targets:
        return f"Node `{symbol}` not found in the graph."

    callers: list[str] = []
    for node_id in targets:
        for pred in G.predecessors(node_id):
            d = G.nodes[pred]
            callers.append(
                f"- **{d.get('label', pred)}** "
                f"[{d.get('type','?')}] "
                f"({(d.get('file') or '').split('/')[-1]})"
            )
    if not callers:
        return f"No callers found for `{symbol}` in the graph."
    return f"**Callers of `{symbol}`:**\n" + "\n".join(callers[:20])


@_register(
    r"(?:what does\s+)?[`\"']?(\w[\w./]+)[`\"']?\s+"
    r"(?:depend(?:s)? on|import|use|need)"
    r"|depend(?:encies|s)? of\s+[`\"']?(\w[\w./]+)[`\"']?"
)
def _get_dependencies(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    symbol = (m.group(1) or m.group(2) or "").strip("./")
    targets = _find_nodes_by_label(G, symbol) or _find_nodes_by_file(G, symbol)
    if not targets:
        return None  # Not found → let LLM try

    node_id = targets[0]
    deps: list[str] = []
    for _, succ, edata in G.out_edges(node_id, data=True):
        d   = G.nodes[succ]
        rel = edata.get("relation", "→")
        deps.append(
            f"- `{d.get('label', succ)}` ({rel}) — "
            f"{(d.get('summary') or '')[:70]}"
        )
    if not deps:
        return f"`{symbol}` has no outbound dependencies in the graph."
    return f"**Dependencies of `{symbol}`:**\n" + "\n".join(deps[:25])


@_register(
    r"(?:list|show|what)\s+(?:are\s+(?:the\s+))?"
    r"(?:all\s+)?(?:modules?|communities?|clusters?|packages?|groups?)"
)
def _list_communities(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    communities: dict[int, list[str]] = {}
    for node_id, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is None:
            continue
        communities.setdefault(int(cid), []).append(data.get("label", node_id))

    if not communities:
        return "No communities detected. Run `pruvagraph .` first."

    lines: list[str] = [f"**{len(communities)} Architectural Modules:**\n"]
    for cid, members in sorted(communities.items()):
        sample = ", ".join(members[:5])
        more   = f" (+{len(members) - 5} more)" if len(members) > 5 else ""
        lines.append(f"- **Module {cid}** ({len(members)} nodes): {sample}{more}")
    return "\n".join(lines)


@_register(r"god nodes?|most connected|highest degree|top \d+ connected|most coupled")
def _find_god_nodes(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    # Extract N from "top N ..."
    n_match = re.search(r"top (\d+)", m.string, re.I)
    top_n   = int(n_match.group(1)) if n_match else 10

    degrees = dict(G.degree())
    top     = sorted(degrees, key=lambda n: -degrees[n])[:top_n]

    lines = [f"**Top {top_n} most-connected nodes (god nodes):**\n"]
    for node_id in top:
        d = G.nodes[node_id]
        lines.append(
            f"- **{d.get('label', node_id)}** — "
            f"{degrees[node_id]} connections "
            f"[{d.get('type','?')}] "
            f"({(d.get('summary') or '')[:60]})"
        )
    return "\n".join(lines)


@_register(
    r"(?:summary|describe|what is|explain)\s+[`\"']?(\w+)[`\"']?"
    r"|[`\"']?(\w+)[`\"']?\s+(?:summary|kya hai|kya karta hai)"
)
def _get_node_summary(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    symbol = (m.group(1) or m.group(2) or "").strip()
    targets = _find_nodes_by_label(G, symbol)
    if not targets:
        return None  # Not found → LLM

    node_id = targets[0]
    d       = G.nodes[node_id]
    return (
        f"**{d.get('label', node_id)}** `[{d.get('type','?')}]`\n"
        f"{d.get('summary', 'No summary available.')}\n"
        f"File: `{d.get('file', 'N/A')}`"
    )


@_register(
    r"how many\s+(?:files?|nodes?|functions?|classes?|modules?|"
    r"edges?|connections?|communities?)"
    r"|(?:stats?|statistics|count|total)"
)
def _count_stats(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    type_counts: dict[str, int] = {}
    file_set: set[str] = set()
    for _, data in G.nodes(data=True):
        t = data.get("type", "?")
        type_counts[t] = type_counts.get(t, 0) + 1
        if data.get("file"):
            file_set.add(data["file"])

    lines = [
        "**Graph Statistics:**",
        f"- Total nodes: **{G.number_of_nodes():,}**",
        f"- Total edges: **{G.number_of_edges():,}**",
        f"- Source files: **{len(file_set):,}**",
    ]
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {t.title()}s: **{cnt:,}**")
    return "\n".join(lines)


@_register(
    r"isolated nodes?|dead code|unused|orphan(?:ed)? nodes?"
    r"|no connections?|disconnected"
)
def _find_isolated(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    isolated = [
        (node_id, data)
        for node_id, data in G.nodes(data=True)
        if G.degree(node_id) == 0
        and data.get("type") not in ("external", "community")
    ]
    if not isolated:
        return "No isolated nodes found — all nodes have at least one connection."

    lines = [f"**{len(isolated)} Isolated Nodes (possible dead code):**\n"]
    for node_id, d in isolated[:20]:
        lines.append(
            f"- `{d.get('label', node_id)}` "
            f"({(d.get('file') or '').split('/')[-1]})"
        )
    return "\n".join(lines)


@_register(
    r"path (?:from|between)\s+[`\"']?(\w+)[`\"']?\s+"
    r"(?:to|and)\s+[`\"']?(\w+)[`\"']?"
    r"|how does\s+[`\"']?(\w+)[`\"']?\s+connect to\s+[`\"']?(\w+)[`\"']?"
)
def _find_path(G: nx.MultiDiGraph, m: re.Match) -> str | None:
    src_name = m.group(1) or m.group(3)
    tgt_name = m.group(2) or m.group(4)

    src_nodes = _find_nodes_by_label(G, src_name)
    tgt_nodes = _find_nodes_by_label(G, tgt_name)

    if not src_nodes or not tgt_nodes:
        return None

    simple_G = nx.DiGraph(G)  # MultiDiGraph → DiGraph for path finding
    try:
        path = nx.shortest_path(simple_G, src_nodes[0], tgt_nodes[0])
    except nx.NetworkXNoPath:
        return f"No path found from `{src_name}` to `{tgt_name}` in the graph."
    except nx.NodeNotFound:
        return None

    labels = [G.nodes[n].get("label", n) for n in path]
    return (
        f"**Shortest path from `{src_name}` to `{tgt_name}`:**\n"
        f"`{'` → `'.join(labels)}`\n"
        f"({len(path) - 1} hops)"
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def try_deterministic_answer(question: str, G: nx.MultiDiGraph) -> str | None:
    """
    Try to answer the question using pure graph algorithms.
    Returns the answer string, or None if LLM reasoning is needed.
    """
    for pattern, handler in _PATTERN_HANDLERS:
        match = pattern.search(question)
        if match:
            try:
                result = handler(G, match)
                if result:
                    return result
            except Exception:
                continue
    return None  # Needs LLM


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_nodes_by_label(G: nx.MultiDiGraph, symbol: str) -> list[str]:
    """Find node IDs whose label fuzzy-matches symbol."""
    sym_lower = symbol.lower()
    exact, partial = [], []
    for node_id, data in G.nodes(data=True):
        label = str(data.get("label", "")).lower()
        if label == sym_lower:
            exact.append(node_id)
        elif sym_lower in label:
            partial.append(node_id)
    return exact or partial


def _find_nodes_by_file(G: nx.MultiDiGraph, filename: str) -> list[str]:
    """Find node IDs whose file path contains filename."""
    fn_lower = filename.lower()
    return [
        node_id for node_id, data in G.nodes(data=True)
        if fn_lower in str(data.get("file", "")).lower()
    ]

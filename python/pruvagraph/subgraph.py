"""
N7 — Query-time Subgraph Extractor

Instead of sending the FULL graph to LLM queries, extract only the
k-hop neighborhood of semantically matched nodes.

Example:
  10,000 node graph → query about "auth" → 2-hop subgraph → ~40 nodes
  Token reduction: 98% → query cost drops from $0.05 → $0.001
"""
from __future__ import annotations

import networkx as nx


def extract_query_subgraph(
    G: nx.MultiDiGraph,
    seed_nodes: list[str],
    k_hops: int = 2,
    max_nodes: int = 60,
) -> nx.MultiDiGraph:
    """
    BFS expansion from seed_nodes up to k_hops.
    Prefers high-degree nodes when capping at max_nodes.
    """
    if not seed_nodes:
        return G

    # Filter seed_nodes to those actually in graph
    seeds = [n for n in seed_nodes if n in G]
    if not seeds:
        return G.subgraph([]).copy()

    visited: set[str] = set(seeds)
    frontier: set[str] = set(seeds)

    for _ in range(k_hops):
        next_frontier: set[str] = set()
        for node in frontier:
            if node not in G:
                continue
            next_frontier.update(G.successors(node))
            next_frontier.update(G.predecessors(node))
        frontier = next_frontier - visited
        visited.update(frontier)
        if len(visited) >= max_nodes:
            break

    # Cap: prefer high-degree nodes
    if len(visited) > max_nodes:
        degrees = {n: G.degree(n) for n in visited}
        visited = set(
            sorted(visited, key=lambda n: -degrees.get(n, 0))[:max_nodes]
        )

    return G.subgraph(visited).copy()


def find_seed_nodes(G: nx.MultiDiGraph, keywords: list[str]) -> list[str]:
    """
    Keyword-based seed node finding (no embeddings needed).
    Matches against node labels and summaries.
    """
    seeds: list[str] = []
    lower_kws = [k.lower() for k in keywords]

    for node_id, data in G.nodes(data=True):
        label   = str(data.get("label", "")).lower()
        summary = str(data.get("summary", "")).lower()
        file    = str(data.get("file", "")).lower()

        score = sum(
            3 if kw in label else (2 if kw in file else (1 if kw in summary else 0))
            for kw in lower_kws
        )
        if score > 0:
            seeds.append((score, node_id))

    seeds.sort(key=lambda x: -x[0])
    return [n for _, n in seeds[:20]]


def build_query_context(
    G: nx.MultiDiGraph,
    seed_nodes: list[str],
    k_hops: int = 2,
    max_tokens: int = 6000,
) -> str:
    """
    Build a compact text context from a subgraph for LLM queries.
    Keeps token count under max_tokens by truncating summaries.

    Full graph: 50,000+ tokens
    Subgraph context: 500–3,000 tokens  (96–99% reduction)
    """
    sub = extract_query_subgraph(G, seed_nodes, k_hops)

    lines: list[str] = [
        f"Codebase subgraph ({sub.number_of_nodes()} nodes, "
        f"{sub.number_of_edges()} edges):\n"
    ]
    estimated_tokens = 20
    max_summary_len  = 100

    for node_id, data in sub.nodes(data=True):
        label   = data.get("label", node_id)
        ntype   = data.get("type", "?")
        summary = (data.get("summary") or "")[:max_summary_len]
        file_   = data.get("file", "")

        node_line = f"[{ntype}] {label}: {summary}"
        if file_:
            node_line += f"  ({file_.split('/')[-1]})"

        lines.append(node_line)
        estimated_tokens += len(node_line.split()) + 2

        # Add outgoing edges (concise)
        for _, target, edata in sub.out_edges(node_id, data=True):
            if target not in sub:
                continue
            tgt_label = sub.nodes[target].get("label", target)
            rel       = edata.get("relation", "→")
            edge_line = f"  └─ {rel} → {tgt_label}"
            lines.append(edge_line)
            estimated_tokens += 8

        if estimated_tokens > max_tokens:
            lines.append(f"\n... (truncated at {max_tokens} tokens)")
            break

    return "\n".join(lines)


def extract_keywords(question: str) -> list[str]:
    """
    Extract meaningful keywords from a question for seed node finding.
    Removes stopwords and short tokens.
    """
    STOPWORDS = frozenset({
        "what", "who", "where", "when", "how", "why", "which",
        "does", "do", "is", "are", "was", "were", "the", "a", "an",
        "in", "on", "at", "to", "for", "of", "with", "that", "this",
        "it", "its", "and", "or", "not", "can", "could", "would",
        "should", "all", "any", "there", "their", "they", "from",
        "about", "into", "through", "between", "being", "been",
    })

    import re
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", question)
    return [
        t.lower() for t in tokens
        if len(t) >= 3 and t.lower() not in STOPWORDS
    ]

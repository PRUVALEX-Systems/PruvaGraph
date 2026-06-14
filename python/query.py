"""
Query engine — natural language search over the knowledge graph.

Two modes:
  1. LOCAL (default / free): keyword + BM25-style scoring over node labels
     and summaries. Zero LLM cost, sub-millisecond latency.
  2. LLM-assisted (opt-in): sends compressed graph context to an LLM for
     richer answers. Costs tokens but gives prose explanations.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import networkx as nx


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def query(
    G: nx.MultiDiGraph,
    question: str,
    backend: str = "none",
    top_k: int = 10,
) -> str:
    """
    Answer *question* about the graph.

    Args:
        G:        The knowledge graph.
        question: Natural language question.
        backend:  "none" (free keyword search) or any LLM backend name.
        top_k:    Max number of nodes to include in the answer.

    Returns:
        A formatted string answer.
    """
    matches = _keyword_search(G, question, top_k=top_k)

    if not matches:
        return f"No nodes found matching: {question!r}"

    if backend == "none":
        return _format_local_answer(question, matches, G)

    # LLM-assisted: build context from matches and call backend
    context = _build_context(matches, G)
    return _llm_answer(question, context, backend)


async def query_async(G: nx.MultiDiGraph, question: str, **kwargs: Any) -> str:
    """Async wrapper for query."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: query(G, question, **kwargs))


# ──────────────────────────────────────────────────────────────────────────────
# Keyword search (BM25-inspired, zero cost)
# ──────────────────────────────────────────────────────────────────────────────

_STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
              "to", "of", "and", "or", "how", "does", "what", "where", "which",
              "do", "does", "connect", "connects", "use", "uses", "with"}


def _tokenise(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _keyword_search(
    G: nx.MultiDiGraph,
    question: str,
    top_k: int = 10,
) -> list[tuple[float, str, dict[str, Any]]]:
    """
    BM25-lite: score nodes by term frequency in label + summary + file.

    Returns sorted list of (score, node_id, node_data).
    """
    query_tokens = set(_tokenise(question))
    if not query_tokens:
        return []

    # Count document frequency for IDF
    df: dict[str, int] = {}
    N = G.number_of_nodes() or 1
    for _, data in G.nodes(data=True):
        field = " ".join(filter(None, [
            data.get("label", ""),
            data.get("summary", ""),
            data.get("file", ""),
            data.get("type", ""),
        ]))
        seen = set(_tokenise(field))
        for t in seen:
            df[t] = df.get(t, 0) + 1

    scored: list[tuple[float, str, dict[str, Any]]] = []

    for node_id, data in G.nodes(data=True):
        label   = data.get("label", "")
        summary = data.get("summary", "") or ""
        file_   = data.get("file", "") or ""
        ntype   = data.get("type", "") or ""

        # Weighted field combination (label weighted 3×, summary 2×)
        text = (label + " ") * 3 + (summary + " ") * 2 + file_ + " " + ntype
        tokens = _tokenise(text)

        if not tokens:
            continue

        score = 0.0
        tf_map: dict[str, float] = {}
        for t in tokens:
            tf_map[t] = tf_map.get(t, 0) + 1
        doc_len = len(tokens)

        k1, b, avg_len = 1.5, 0.75, 20.0
        for qt in query_tokens:
            if qt not in tf_map:
                continue
            tf = tf_map[qt]
            idf = math.log((N - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5) + 1)
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_len))
            score += idf * tf_norm

        # Boost: if all query tokens found
        if query_tokens <= set(tf_map.keys()):
            score *= 1.5

        if score > 0:
            scored.append((score, node_id, data))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]


# ──────────────────────────────────────────────────────────────────────────────
# Local answer formatter
# ──────────────────────────────────────────────────────────────────────────────


def _format_local_answer(
    question: str,
    matches: list[tuple[float, str, dict[str, Any]]],
    G: nx.MultiDiGraph,
) -> str:
    lines = [f"🔍 Results for: {question!r}", ""]

    for score, node_id, data in matches:
        label   = data.get("label", node_id)
        ntype   = data.get("type", "?")
        summary = data.get("summary", "No summary.")
        file_   = data.get("file") or ""
        community = data.get("community")

        in_deg  = G.in_degree(node_id)
        out_deg = G.out_degree(node_id)

        lines.append(f"• [{ntype}] **{label}**")
        if summary:
            lines.append(f"  {summary}")
        if file_:
            lines.append(f"  📄 {file_}")
        if community is not None:
            lines.append(f"  🏘 Community {community} · {in_deg} in / {out_deg} out")

        # Show top neighbours
        neighbors = []
        for _, tgt, edata in G.out_edges(node_id, data=True):
            tgt_label = G.nodes[tgt].get("label", tgt)
            neighbors.append(f"{edata.get('relation','→')} {tgt_label}")
        if neighbors:
            lines.append(f"  🔗 {', '.join(neighbors[:4])}")

        lines.append("")

    lines.append(f"Found {len(matches)} matching nodes.")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# LLM-assisted answer
# ──────────────────────────────────────────────────────────────────────────────


def _build_context(
    matches: list[tuple[float, str, dict[str, Any]]],
    G: nx.MultiDiGraph,
) -> str:
    """Build a compact context string from graph matches for LLM input."""
    parts = []
    for _, node_id, data in matches:
        label   = data.get("label", node_id)
        ntype   = data.get("type", "?")
        summary = data.get("summary", "")
        file_   = data.get("file") or ""
        deps    = [G.nodes[t].get("label", t) for _, t, _ in G.out_edges(node_id, data=True)][:5]
        callers = [G.nodes[s].get("label", s) for s, _, _ in G.in_edges(node_id, data=True)][:5]

        part = f"Node: {label} ({ntype})"
        if summary:
            part += f"\nSummary: {summary}"
        if file_:
            part += f"\nFile: {file_}"
        if deps:
            part += f"\nDependencies: {', '.join(deps)}"
        if callers:
            part += f"\nUsed by: {', '.join(callers)}"
        parts.append(part)

    return "\n\n".join(parts)


def _llm_answer(question: str, context: str, backend: str) -> str:
    """Call an LLM to answer the question given the graph context."""
    system = (
        "You are a codebase expert. Answer the question based ONLY on the "
        "knowledge graph context provided. Be concise (3-5 sentences max). "
        "If you cannot answer from the context, say so."
    )
    prompt = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        if backend == "claude":
            return _call_anthropic(system, prompt)
        if backend == "gemini":
            return _call_gemini(system, prompt)
        if backend in ("openai", "gpt"):
            return _call_openai(system, prompt)
        if backend == "ollama":
            return _call_ollama(system, prompt)
    except Exception as e:
        return f"LLM error ({backend}): {e}\n\nFallback results:\n{context}"

    return f"Unknown backend: {backend!r}"


def _call_anthropic(system: str, prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _call_gemini(system: str, prompt: str) -> str:
    import httpx, os, json
    key = os.environ.get("GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": f"{system}\n\n{prompt}"}]}]}
    resp = httpx.post(url, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai(system: str, prompt: str) -> str:
    import httpx, os, json
    key = os.environ.get("OPENAI_API_KEY", "")
    url = "https://api.openai.com/v1/chat/completions"
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 512,
    }
    resp = httpx.post(url, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_ollama(system: str, prompt: str) -> str:
    import httpx, json
    url = "http://localhost:11434/api/generate"
    body = {"model": "llama3.2", "prompt": f"{system}\n\n{prompt}", "stream": False}
    resp = httpx.post(url, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["response"]

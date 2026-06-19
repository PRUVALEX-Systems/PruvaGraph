"""
Query engine — natural language search over the knowledge graph.

5-tier cost reduction pipeline:
  Tier 0: QueryCache          → instant answer if seen before  (free)
  Tier 1: DeterministicRouter → 60–70% answered algorithmically (free)
  Tier 2: LocalEmbeddings     → semantic seed finding           (free)
  Tier 3: SubgraphExtractor   → 98% token reduction for LLM    (free)
  Tier 4: HierarchyRouter     → right context level for LLM    (free)
  Tier 5: LLM call            → last resort, tiny subgraph only (cost)
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
    out_dir: Path | None = None,
    token_budget: int = 6000,
    benchmark_mode: bool = False,
) -> str:
    """
    Answer *question* about the graph using a 5-tier cost pipeline.

    Tier 0: Cache            — free, instant
    Tier 1: Deterministic    — free, algorithmic (callers, deps, stats…)
    Tier 2: Keyword + Embed  — free, BM25 + vector seeds
    Tier 3: Subgraph extract — free, 98% token reduction
    Tier 4: Hierarchy level  — free, picks right context scope
    Tier 5: LLM call         — only if all above fail, tiny context

    Args:
        token_budget:    Max tokens allowed in context sent to LLM (default 6000).
        benchmark_mode:  If True, compute and log raw-file tokens vs graph tokens
                         to cost_report.json for independent verification.
    """
    # ── Tier 0: Query Cache ────────────────────────────────────────────────────
    if out_dir:
        try:
            from pruvagraph.query_cache import QueryCache
            cache = QueryCache(out_dir)
            cached = cache.get(question)
            if cached:
                return f"💾 [cached]\n{cached}"
        except Exception:
            cache = None
    else:
        cache = None

    # ── Tier 1: Deterministic Router ──────────────────────────────────────────
    try:
        from pruvagraph.deterministic_router import try_deterministic_answer
        det_answer = try_deterministic_answer(question, G)
        if det_answer:
            if cache:
                cache.save(question, det_answer)
            return f"⚡ [free]\n{det_answer}"
    except Exception:
        pass

    # ── Tier 2: Seed node finding (embedding > keyword fallback) ──────────────
    seed_nodes: list[str] = []
    embedding_scores: dict[str, float] = {}
    if out_dir:
        try:
            from pruvagraph.embedder import semantic_search_with_scores
            scored = semantic_search_with_scores(question, out_dir, top_k=15)
            seed_nodes = [node_id for node_id, _ in scored]
            embedding_scores = {node_id: score for node_id, score in scored}
        except Exception:
            pass

    if not seed_nodes:
        # Keyword fallback
        from pruvagraph.subgraph import extract_keywords, find_seed_nodes
        kws        = extract_keywords(question)
        seed_nodes = find_seed_nodes(G, kws)

    # ── Local answer (backend=none) ────────────────────────────────────────────
    if backend == "none":
        if seed_nodes:
            from pruvagraph.subgraph import extract_query_subgraph
            sub     = extract_query_subgraph(
                G,
                seed_nodes,
                k_hops=1,
                max_nodes=20,
                token_budget=token_budget,
                embedding_scores=embedding_scores,
            )
            matches = _score_subgraph(sub, question, top_k)
        else:
            matches = _keyword_search(G, question, top_k=top_k)

        if not matches:
            return f"No nodes found matching: {question!r}"

        # Token count is a free byproduct of the packing pass — include on every call.
        result_str = _format_local_answer(question, matches, G)
        context_tokens_used = len(result_str) // 4  # chars / 4 — standard approximation
        answer = f"{result_str}\n\n📊 context_tokens_used: {context_tokens_used:,}"

        if benchmark_mode and out_dir:
            _log_benchmark(question, G, matches, context_tokens_used, out_dir)
        return answer

    # ── Tier 3 + 4: Subgraph + Hierarchy context for LLM ─────────────────────
    context: str
    context_tokens: int = 0
    try:
        from pruvagraph.hierarchy import get_level_context, load_hierarchy, route_query_to_level
        from pruvagraph.subgraph import build_query_context, prune_context

        level = route_query_to_level(question)

        if level in ("repo", "community") and out_dir:
            hierarchy = load_hierarchy(out_dir)
            context   = get_level_context(hierarchy, level)
            context_tokens = len(context) // 4 if context else 0
            if not context:
                if out_dir:
                    context, context_tokens = prune_context(
                        G,
                        question,
                        out_dir,
                        k_hops=2,
                        max_tokens=token_budget,
                    )
                else:
                    context, context_tokens = build_query_context(
                        G,
                        seed_nodes,
                        k_hops=2,
                        max_tokens=token_budget,
                        embedding_scores=embedding_scores,
                    )
        else:
            if out_dir:
                context, context_tokens = prune_context(
                    G,
                    question,
                    out_dir,
                    k_hops=1,
                    max_tokens=token_budget,
                )
            else:
                context, context_tokens = build_query_context(
                    G,
                    seed_nodes,
                    k_hops=1,
                    max_tokens=token_budget,
                    embedding_scores=embedding_scores,
                )
    except Exception:
        # Pure fallback: BM25 matches
        matches = _keyword_search(G, question, top_k=top_k)
        context = _build_context(matches, G)
        context_tokens = len(context) // 4  # chars / 4 — standard approximation (C2 fix)

    # ── Tier 5: LLM call ──────────────────────────────────────────────────────
    answer = _llm_answer(question, context, backend)
    # Token count is a free byproduct of the packing pass — include on every call.
    token_line = f"\n\n📊 context_tokens_used: {context_tokens}"
    if cache:
        cache.save(question, answer)
    # Benchmark: only log the naive-file counterfactual when explicitly requested.
    if benchmark_mode and out_dir:
        _log_benchmark(question, G, [], context_tokens, out_dir)
    return answer + token_line


async def query_async(G: nx.MultiDiGraph, question: str, **kwargs: Any) -> str:
    """Async wrapper for query."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: query(G, question, **kwargs))


def _log_benchmark(
    question: str,
    G: nx.MultiDiGraph,
    matches: list,
    graph_tokens: int,
    out_dir: Path,
) -> None:
    """
    Part D — Benchmark mode: compute raw-file tokens vs graph tokens and append
    to cost_report.json so savings are independently checkable.

    Raw token estimate: average 800 tokens per source file × files in graph.
    This is conservative (many files are larger), so the actual saving is likely
    higher.
    """
    import json
    import time

    # Count unique source files referenced in graph
    unique_files = {
        data.get("file") for _, data in G.nodes(data=True) if data.get("file")
    }
    # Estimate: ~800 tokens/file for average source file
    raw_estimate = len(unique_files) * 800
    saving_pct = max(0.0, (1 - graph_tokens / raw_estimate) * 100) if raw_estimate else 0.0

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "question": question[:120],
        "tokens_via_graph": graph_tokens,
        "tokens_raw_files_estimate": raw_estimate,
        "files_in_graph": len(unique_files),
        "token_savings_pct": round(saving_pct, 1),
        "note": "Raw estimate = 800 tokens × unique_files. Actual saving likely higher.",
    }

    cost_report = out_dir / "cost_report.json"
    try:
        data: dict = {}
        if cost_report.exists():
            data = json.loads(cost_report.read_text(encoding="utf-8"))
        benchmarks = data.get("query_benchmarks", [])
        benchmarks.append(entry)
        data["query_benchmarks"] = benchmarks[-50:]  # keep last 50
        cost_report.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass  # benchmark logging is best-effort


_STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
              "to", "of", "and", "or", "how", "does", "what", "where", "which",
              "do", "does", "connect", "connects", "use", "uses", "with"}


def _tokenise(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _score_subgraph(
    sub: nx.MultiDiGraph,
    question: str,
    top_k: int,
) -> list[tuple[float, str, dict]]:
    """Run BM25 keyword search restricted to a subgraph."""
    return _keyword_search(sub, question, top_k=top_k)


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
        "You are a codebase expert. Answer the question using only the provided "
        "knowledge graph context. Output MUST be valid JSON only and must follow "
        "this schema exactly: {\"answer\":\"string\",\"sources\":[\"string\"]}. "
        "Do not include markdown fences, analysis, reasoning, or any text outside "
        "the JSON object. If you cannot answer, return answer as an empty string "
        "and sources as an empty array."
    )
    prompt = (
        f"CONTEXT:\n{context}\n\nQUESTION:\n{question}\n\n"
        "Return exactly one JSON object with keys answer and sources."
    )

    try:
        if backend == "claude":
            raw = _call_anthropic(system, prompt)
        elif backend == "gemini":
            raw = _call_gemini(system, prompt)
        elif backend in ("openai", "gpt"):
            raw = _call_openai(system, prompt)
        elif backend == "ollama":
            raw = _call_ollama(system, prompt)
        else:
            return f"Unknown backend: {backend!r}"

        parsed = _parse_llm_json(raw)
        if parsed is not None:
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        return f"LLM output was not valid JSON. Raw output:\n{raw}"
    except Exception as e:
        return f"LLM error ({backend}): {e}\n\nFallback results:\n{context}"


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if isinstance(data, dict):
        if "answer" in data:
            sources = data.get("sources", [])
            if not isinstance(sources, list):
                sources = [str(sources)]
            return {
                "answer": str(data["answer"]),
                "sources": [str(item) for item in sources],
            }
        return {"answer": str(data), "sources": []}

    return None


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
    import os

    import httpx
    key = os.environ.get("GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": f"{system}\n\n{prompt}"}]}]}
    resp = httpx.post(url, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai(system: str, prompt: str) -> str:
    import os

    import httpx
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
    import httpx
    url = "http://localhost:11434/api/generate"
    body = {"model": "llama3.2", "prompt": f"{system}\n\n{prompt}", "stream": False}
    resp = httpx.post(url, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["response"]

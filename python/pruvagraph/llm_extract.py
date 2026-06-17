"""
LLM extraction -- Stage 2 of the pipeline.

Turns a batch of doc/PDF/image files into ``{"nodes": [...], "edges": [...]}``
extraction dicts using the cheapest capable backend.

Code files NEVER reach this module -- they go through ``extract.py``
(tree-sitter / regex, zero LLM cost). Only DOCUMENT / PAPER / IMAGE files
are routed here, and even then only after dedup + batching have already
shrunk the file list as much as possible.

  L5:  Token compression     -> compress() called before every LLM batch
                               strips license headers, badges, redundant imports
                               Result: 50-80% token reduction

Backends supported:
  - "none"   -> no LLM call. Returns a minimal stub node per file (free).
  - "claude" -> Anthropic API (ANTHROPIC_API_KEY)
  - "gemini" -> Google Gemini Flash (GEMINI_API_KEY)
  - "openai" -> OpenAI GPT-4o-mini (OPENAI_API_KEY)
  - "ollama" -> local Ollama model (free, no key)

If ``cascade=True``, delegates to ``router.extract_with_fallback`` which
tries LOCAL -> CHEAP -> CLOUD in order.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_SYSTEM_PROMPT = """\
You are a code/documentation knowledge-graph extractor. Read the file(s) below \
and output ONLY valid JSON (no markdown fences, no prose) with this shape:

{"nodes": [{"id": "<unique-id>", "label": "<short name>", "type": "<doc|concept|api|config>", \
"summary": "<one sentence>", "file": "<source path>"}],
 "edges": [{"source": "<node id>", "target": "<node id>", "relation": "<references|defines|describes>"}]}

Keep summaries under 25 words. Extract 1-5 nodes per file. If a file has no \
meaningful content, return an empty nodes/edges list for it.
"""


def extract_doc_batch(
    paths: list[Path],
    backend: str = "claude",
    cascade: bool = False,
    max_chars_per_file: int = 20_000,
) -> list[dict[str, Any]]:
    """
    Extract a knowledge-graph fragment for each file in *paths*.

    Returns one extraction dict per path (same order as input), each with
    ``"nodes"``, ``"edges"``, ``"source_file"``, and internal bookkeeping
    keys ``_input_tokens`` / ``_output_tokens`` / ``_backend`` that
    ``pipeline.py`` pops off before caching.
    """
    if not paths:
        return []

    from pruvagraph.compress import compress

    file_contents: list[tuple[str, str]] = []
    for p in paths:
        try:
            raw_text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw_text = ""
        
        # L5: Token compression — strip license headers, badge noise,
        # redundant imports, boilerplate before sending to LLM
        try:
            compression_result = compress(raw_text, path=p)
            text = compression_result.compressed_content
            # Log compression ratio if significant
            if compression_result.ratio < 0.7:  # saved >30%
                pass  # pipeline will log cost savings
        except Exception:
            # Never let compression failure break the build
            text = raw_text
        
        file_contents.append((str(p), text[:max_chars_per_file]))

    if backend == "none" or not _has_credentials(backend):
        return _stub_extractions(paths)

    if cascade:
        from pruvagraph.router import extract_with_fallback
        result, used_backend = extract_with_fallback(file_contents)
        return _split_result(result, paths, used_backend)

    try:
        if backend == "claude":
            result = _call_claude(file_contents)
        elif backend == "gemini":
            result = _call_gemini(file_contents)
        elif backend == "openai":
            result = _call_openai(file_contents)
        elif backend == "ollama":
            result = _call_ollama(file_contents)
        else:
            result = {"nodes": [], "edges": []}
    except Exception:
        # Never let an LLM/network error crash the whole build.
        return _stub_extractions(paths)

    return _split_result(result, paths, backend)


# ---------------------------------------------------------------------------
# Backend calls -- each returns {"nodes":[...], "edges":[...],
#                                 "_input_tokens": int, "_output_tokens": int}
# ---------------------------------------------------------------------------

def _call_claude(file_contents: list[tuple[str, str]]) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = _build_prompt(file_contents)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    parsed = _safe_json(text)
    parsed["_input_tokens"] = resp.usage.input_tokens
    parsed["_output_tokens"] = resp.usage.output_tokens
    return parsed


def _call_gemini(file_contents: list[tuple[str, str]]) -> dict[str, Any]:
    import httpx

    key = os.environ.get("GEMINI_API_KEY")
    prompt = _build_prompt(file_contents)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={key}"
    )
    body = {
        "contents": [{"parts": [{"text": _SYSTEM_PROMPT + "\n\n" + prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    r = httpx.post(url, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = _safe_json(text)
    usage = data.get("usageMetadata", {})
    parsed["_input_tokens"] = usage.get("promptTokenCount", 0)
    parsed["_output_tokens"] = usage.get("candidatesTokenCount", 0)
    return parsed


def _call_openai(file_contents: list[tuple[str, str]]) -> dict[str, Any]:
    import httpx

    key = os.environ.get("OPENAI_API_KEY")
    prompt = _build_prompt(file_contents)
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    parsed = _safe_json(text)
    usage = data.get("usage", {})
    parsed["_input_tokens"] = usage.get("prompt_tokens", 0)
    parsed["_output_tokens"] = usage.get("completion_tokens", 0)
    return parsed


def _call_ollama(file_contents: list[tuple[str, str]]) -> dict[str, Any]:
    import httpx

    prompt = _build_prompt(file_contents)
    r = httpx.post(
        "http://localhost:11434/api/generate",
        json={
            "model": os.environ.get("PRUVAGRAPH_OLLAMA_MODEL", "qwen2.5-coder:3b"),
            "prompt": _SYSTEM_PROMPT + "\n\n" + prompt,
            "format": "json",
            "stream": False,
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    parsed = _safe_json(data.get("response", "{}"))
    parsed["_input_tokens"] = data.get("prompt_eval_count", 0)
    parsed["_output_tokens"] = data.get("eval_count", 0)
    return parsed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_credentials(backend: str) -> bool:
    return {
        "claude": "ANTHROPIC_API_KEY" in os.environ,
        "gemini": "GEMINI_API_KEY" in os.environ,
        "openai": "OPENAI_API_KEY" in os.environ,
        "ollama": True,  # checked at call time; falls back to stub on error
        "none": False,
    }.get(backend, False)


def _build_prompt(file_contents: list[tuple[str, str]]) -> str:
    parts = []
    for path, content in file_contents:
        parts.append(f'<file path="{path}">\n{content}\n</file>')
    return "\n\n".join(parts)


def _safe_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        return {"nodes": data.get("nodes", []), "edges": data.get("edges", [])}
    except (json.JSONDecodeError, AttributeError):
        return {"nodes": [], "edges": []}


def _stub_extractions(paths: list[Path]) -> list[dict[str, Any]]:
    """Zero-cost fallback: one minimal node per file, no LLM call."""
    out = []
    for p in paths:
        node_id = f"doc::{p}"
        out.append({
            "nodes": [{
                "id": node_id,
                "label": p.name,
                "type": "doc",
                "summary": f"Document file: {p.name}",
                "file": str(p),
                "lang": None,
            }],
            "edges": [],
            "source_file": str(p),
            "_input_tokens": 0,
            "_output_tokens": 0,
            "_backend": "none",
        })
    return out


def _split_result(
    result: dict[str, Any], paths: list[Path], backend: str
) -> list[dict[str, Any]]:
    """
    Distribute a single batch-level extraction result across the input
    files, grouping nodes/edges by their declared ``file`` field. Any
    nodes that don't reference a path in *paths* are attached to the
    first file (better to keep them than drop them).
    """
    nodes = result.get("nodes", []) or []
    edges = result.get("edges", []) or []
    in_tok = result.get("_input_tokens", 0)
    out_tok = result.get("_output_tokens", 0)

    path_strs = [str(p) for p in paths]
    by_file: dict[str, list[dict[str, Any]]] = {ps: [] for ps in path_strs}

    for node in nodes:
        f = node.get("file")
        target = f if f in by_file else path_strs[0]
        by_file[target].append(node)

    extractions = []
    for i, p in enumerate(paths):
        ps = str(p)
        these_nodes = by_file.get(ps, [])
        these_ids = {n.get("id") for n in these_nodes}
        these_edges = [
            e for e in edges
            if e.get("source") in these_ids or e.get("target") in these_ids
        ]
        extractions.append({
            "nodes": these_nodes,
            "edges": these_edges if i == 0 else these_edges,
            "source_file": ps,
            "_input_tokens": in_tok if i == 0 else 0,
            "_output_tokens": out_tok if i == 0 else 0,
            "_backend": backend,
        })
    return extractions

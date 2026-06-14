"""
Benchmark — measures token savings vs naive (send all files raw to LLM).

Compares:
  A) Naive: send every file's raw content to the LLM for every query.
  B) PruvaGraph: query the compressed knowledge graph (graph.json).

Result: "PruvaGraph uses 98.3% fewer tokens per query on this repo."
"""
from __future__ import annotations

import json
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Pricing (per 1M tokens)
# ──────────────────────────────────────────────────────────────────────────────

CLAUDE_PRICE_PER_M = 3.00   # Claude Sonnet input price


def run_benchmark(graph_json: Path) -> str:
    """Run the token savings benchmark and return a formatted report."""

    graph_data = json.loads(graph_json.read_text(encoding="utf-8"))

    # Estimate graph tokens (compressed)
    graph_str = json.dumps(graph_data)
    graph_tokens = _count_tokens(graph_str)

    # Estimate raw-file tokens (what a naive tool would send)
    root = graph_json.parent.parent
    raw_tokens = _estimate_raw_tokens(root)

    if raw_tokens == 0:
        return "Could not estimate raw token count (no source files found)."

    # Query comparison (assuming 10 queries/day)
    queries_per_day = 10
    naive_daily = raw_tokens * queries_per_day
    pruvagraph_daily = graph_tokens * queries_per_day
    saved_daily = max(0, naive_daily - pruvagraph_daily)
    savings_pct = (saved_daily / naive_daily * 100) if naive_daily > 0 else 0.0

    naive_cost_per_query = raw_tokens / 1_000_000 * CLAUDE_PRICE_PER_M
    pg_cost_per_query    = graph_tokens / 1_000_000 * CLAUDE_PRICE_PER_M
    saved_per_query      = max(0.0, naive_cost_per_query - pg_cost_per_query)
    monthly_savings      = saved_per_query * queries_per_day * 30

    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║     PRUVALEX PruvaGraph — Token Savings Benchmark       ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"  Raw codebase tokens:     {raw_tokens:>12,}",
        f"  PruvaGraph tokens:       {graph_tokens:>12,}",
        f"  Compression ratio:       {raw_tokens/max(graph_tokens,1):>12.1f}×",
        f"  Token savings:           {savings_pct:>11.1f}%",
        "",
        "  Per-query cost (Claude Sonnet):",
        f"    Naive (raw files):     ${naive_cost_per_query:>11.4f}",
        f"    PruvaGraph:            ${pg_cost_per_query:>11.6f}",
        f"    Saved per query:       ${saved_per_query:>11.4f}",
        "",
        f"  At {queries_per_day} queries/day × 30 days:",
        f"    Monthly savings:       ${monthly_savings:>11.2f}",
        "",
        "  ✓ PruvaGraph sends only the graph — not all your files.",
    ]

    # Add graph stats
    nodes = graph_data.get("nodes", [])
    links = graph_data.get("links", graph_data.get("edges", []))
    lines += [
        "",
        f"  Graph stats: {len(nodes):,} nodes · {len(links):,} edges",
        "",
        "══════════════════════════════════════════════════════════",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken if available, else estimate chars/4."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4


def _estimate_raw_tokens(root: Path) -> int:
    """Walk the repo and count all tokens in code/doc files."""
    from pruvagraph.detect import FileType, collect_files

    total = 0
    try:
        for path, ftype in collect_files(root):
            if ftype in (FileType.CODE, FileType.DOCUMENT):
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    total += _count_tokens(content)
                except OSError:
                    pass
    except Exception:
        pass
    return total

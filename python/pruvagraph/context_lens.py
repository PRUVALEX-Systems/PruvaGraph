"""
pruvagraph.context_lens — ContextLens session tracking module.

Logs every MCP tool call to a JSONL session file so the VS Code panel
can show the user what's actually been injected into context, how many
tokens each tool call consumed, and the recent call history.

Design decisions:
  - Token estimation: chars / 4 (no extra dependency; ~accurate for English
    code/prose, consistent with the existing cost_report.json approach).
  - Session log: pruvagraph-out/context_lens_session.jsonl
    Rotated: keeps at most MAX_RECORDS lines (newest retained).
  - No in-memory state: each call reads/writes the JSONL file, so the log
    survives MCP server restarts and cross-session queries work naturally.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RECORDS: int = 200          # max lines kept in the session JSONL
RESULT_PREVIEW_LEN: int = 200   # chars kept as result preview
SESSION_FILE_REL: str = "pruvagraph-out/context_lens_session.jsonl"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRecord:
    """One logged MCP tool invocation."""
    name: str
    args: dict
    result_preview: str   # first RESULT_PREVIEW_LEN chars of the result string
    token_est: int        # chars(result) // 4 — cost estimate
    timestamp: str        # ISO-8601, UTC


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _session_path(root: str | Path) -> Path:
    return Path(root) / SESSION_FILE_REL


def _read_records(path: Path) -> list[dict]:
    """Read all records from the JSONL file; return [] on missing/corrupt."""
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # skip corrupt lines
    return records


def _write_records(path: Path, records: list[dict]) -> None:
    """Write records back to the JSONL file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_tool_call(
    name: str,
    args: dict[str, Any],
    result: str,
    root: str | Path = ".",
) -> None:
    """Append a tool call record to the session JSONL.

    Called automatically by the MCP server dispatch wrapper — user code
    should never need to call this directly.

    Rotation: if the file already has MAX_RECORDS lines, the oldest entries
    are dropped to keep the file bounded.
    """
    path = _session_path(root)
    existing = _read_records(path)

    record = ToolCallRecord(
        name=name,
        args=args,
        result_preview=result[:RESULT_PREVIEW_LEN],
        token_est=len(result) // 4,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    existing.append(asdict(record))

    # Rotate: keep only the last MAX_RECORDS entries (newest at the end)
    if len(existing) > MAX_RECORDS:
        existing = existing[-MAX_RECORDS:]

    _write_records(path, existing)


def get_active_context(root: str | Path = ".") -> str:
    """Return a formatted summary of tool calls made in this session.

    Covers: total calls, total estimated tokens, unique tools used.
    """
    records = _read_records(_session_path(root))

    if not records:
        return (
            "### ContextLens — Session Summary\n\n"
            "No tool calls recorded yet in this session.\n"
            "Tool calls are logged automatically when you use PruvaGraph MCP tools."
        )

    total_tokens = sum(r.get("token_est", 0) for r in records)
    unique_tools = sorted({r["name"] for r in records})
    call_count = len(records)

    lines = [
        "### ContextLens — Session Summary",
        "",
        f"**{call_count} tool call{'s' if call_count != 1 else ''} this session**  ",
        f"**Estimated tokens consumed: {total_tokens:,}**  ",
        f"**Unique tools used: {len(unique_tools)}**",
        "",
        "| Tool | Calls | Est. Tokens |",
        "|------|-------|-------------|",
    ]

    # Per-tool breakdown
    tool_stats: dict[str, dict] = {}
    for r in records:
        n = r["name"]
        if n not in tool_stats:
            tool_stats[n] = {"calls": 0, "tokens": 0}
        tool_stats[n]["calls"] += 1
        tool_stats[n]["tokens"] += r.get("token_est", 0)

    for tool_name in sorted(tool_stats):
        s = tool_stats[tool_name]
        lines.append(f"| `{tool_name}` | {s['calls']} | {s['tokens']:,} |")

    return "\n".join(lines)


def measure_token_usage(root: str | Path = ".") -> str:
    """Return per-call token breakdown and session total.

    Sorted by token cost descending so the most expensive calls surface first.
    """
    records = _read_records(_session_path(root))

    if not records:
        return (
            "### ContextLens — Token Usage\n\n"
            "No tool calls recorded yet. Token usage is 0 this session."
        )

    total = sum(r.get("token_est", 0) for r in records)

    # Per-tool aggregate
    tool_tokens: dict[str, int] = {}
    for r in records:
        tool_tokens[r["name"]] = tool_tokens.get(r["name"], 0) + r.get("token_est", 0)

    lines = [
        "### ContextLens — Token Usage",
        "",
        f"**Session total: ~{total:,} tokens** (estimated at 1 token ≈ 4 chars)",
        "",
        "| Tool | Est. Tokens | % of Session |",
        "|------|-------------|--------------|",
    ]

    for tool_name, toks in sorted(tool_tokens.items(), key=lambda x: x[1], reverse=True):
        pct = (toks / total * 100) if total > 0 else 0.0
        lines.append(f"| `{tool_name}` | {toks:,} | {pct:.1f}% |")

    return "\n".join(lines)


def trace_last_tool_calls(root: str | Path = ".", n: int = 10) -> str:
    """Return the last N tool calls with name, token_est, and timestamp.

    Most recent call last (chronological order).
    """
    records = _read_records(_session_path(root))

    if not records:
        return (
            "### ContextLens — Recent Tool Calls\n\n"
            "No tool calls recorded yet this session."
        )

    subset = records[-n:]  # last n, newest at the end

    lines = [
        f"### ContextLens — Last {len(subset)} Tool Call{'s' if len(subset) != 1 else ''}",
        "",
        "| # | Tool | Est. Tokens | Timestamp |",
        "|---|------|-------------|-----------|",
    ]

    for i, r in enumerate(subset, start=1):
        ts = r.get("timestamp", "—")
        # Trim timestamp to readable format: 2026-01-01T00:00:00
        ts_short = ts[:19] if len(ts) >= 19 else ts
        lines.append(
            f"| {i} | `{r['name']}` | {r.get('token_est', 0):,} | {ts_short} |"
        )

    return "\n".join(lines)

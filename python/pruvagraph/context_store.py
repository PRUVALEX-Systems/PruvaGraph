"""
Arch6 — Session Memory.

Persists decisions, tasks, and blockers across Claude Code sessions so
the next session doesn't start from zero.  Thin, dumb JSON file — no
LLM involved.  Mirrors GrapeRoot's context-store.json pattern.

Usage via MCP (Claude Code):
    remember("decisions", "Use Gemini for doc extraction — 40x cheaper than Claude")
    recall()

Usage via Python:
    from pruvagraph.context_store import append_entry, load_context
    append_entry(root, "tasks", "Wire A5 global cache into pipeline.py")
    print(load_context(root))
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

Category = Literal["decisions", "tasks", "blockers"]

STORE_REL_PATH = Path(".pruvagraph") / "context-store.json"




def _store_path(root: Path) -> Path:
    return root / STORE_REL_PATH


def load_context(root: Path) -> dict[str, Any]:
    """Load the context store.  Returns empty structure if not yet created."""
    path = _store_path(root)
    if not path.exists():
        return {"decisions": [], "tasks": [], "blockers": []}   # fresh lists — NOT a shared ref
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for k in ("decisions", "tasks", "blockers"):
            data.setdefault(k, [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"decisions": [], "tasks": [], "blockers": []}   # fresh lists — NOT a shared ref


def append_entry(root: Path, category: Category, text: str) -> dict[str, Any]:
    """Append *text* under *category* and persist to disk."""
    path = _store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    store = load_context(root)
    store.setdefault(category, []).append({"text": text, "ts": time.time()})
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")
    return store


def format_for_injection(root: Path, max_items_per_category: int = 8) -> str:
    """
    Return a markdown block summarising recent entries — for CLAUDE.md injection.
    Returns empty string if the store is empty.
    """
    store = load_context(root)
    if not any(store.values()):
        return ""

    lines: list[str] = ["### Session Memory (persisted across Claude Code sessions)", ""]
    for category in ("decisions", "tasks", "blockers"):
        entries = store.get(category, [])[-max_items_per_category:]
        if not entries:
            continue
        lines.append(f"**{category.capitalize()}:**")
        for entry in entries:
            lines.append(f"- {entry['text']}")
        lines.append("")
    return "\n".join(lines)

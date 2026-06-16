"""
Gap 1 — Claude Code PreToolUse Hooks.

This is the ONLY way to get hard enforcement (not just advisory guidance)
over which files Claude reads.  Claude's native `Read` tool can bypass
every MCP suggestion — but a registered PreToolUse hook fires BEFORE
every tool call and can block it with a redirect message.

How Claude Code hooks work
──────────────────────────
1. Hooks are registered in `.claude/settings.json` under "hooks".
2. On every tool call, Claude Code pipes a JSON blob to the hook's stdin:
   {
     "tool_name":   "Read",
     "tool_input":  {"file_path": "/abs/path/to/file.py"},
     "session_id":  "...",
     "turn_number": 3
   }
3. The hook writes a JSON response to stdout:
   - Allow (do nothing):         exit 0, empty stdout
   - Block with redirect:        {"decision": "block", "reason": "..."}
   - Approve explicitly:         {"decision": "approve"}

PruvaGraph hook logic
─────────────────────
For every Read tool call:

  A. Extract the file path.
  B. Check if the corresponding graph node was already surfaced via
     get_summary / get_dependencies / find_callers in this session
     (session_tracker.py).
  C. If YES → block the Read and return a terse redirect:
       "PruvaGraph already surfaced AuthService (turn 3, get_summary).
        Use `get_summary('AuthService')` or check CLAUDE.md. Reading
        the raw file will re-burn those tokens."
  D. If NO  → allow the Read, then record the file in session state
     so the *next* read of the same file is redirected.

Installing hooks
────────────────
    pruvagraph install --hooks          # writes .claude/settings.json
    pruvagraph hooks --dry-run          # print what would be written

Removing hooks
──────────────
    pruvagraph hooks --remove           # removes pruvagraph block from settings

Notes
─────
- The hook is conservative: if graph is not built or any error occurs,
  it allows the Read (fail-open, not fail-closed).
- Hooks only affect Claude Code.  VS Code / Cursor are not affected.
- The hook file is a standalone Python script so it has zero dependencies
  beyond the stdlib — it imports pruvagraph only if available.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Hook entry point  (called as:  python -m pruvagraph.hooks)
# ──────────────────────────────────────────────────────────────────────────────

def run_hook() -> None:
    """
    Read the Claude Code hook payload from stdin, decide allow/block, write to stdout.

    This function is invoked by Claude Code once per PreToolUse event.
    It must complete in <2 s or Claude Code will time-out and allow the call.
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)  # no payload → allow
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)  # malformed → allow (fail-open)

    tool_name  = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    # We only intercept Read (and its aliases used by some Claude versions)
    if tool_name not in {"Read", "read_file", "view_file"}:
        sys.exit(0)

    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("AbsolutePath")
        or ""
    )
    if not file_path:
        sys.exit(0)

    decision = _evaluate_read(file_path, payload)
    if decision is None:
        sys.exit(0)  # allow

    # Block: write JSON to stdout
    print(json.dumps(decision))
    sys.exit(0)


def _evaluate_read(file_path: str, payload: dict) -> dict | None:
    """
    Core logic: should this Read be blocked?

    Returns a {"decision": "block", "reason": "..."} dict to block,
    or None to allow.
    """
    # Resolve project root from the file path (walk up to find graph.json)
    root = _find_project_root(file_path)
    if root is None:
        return None  # not a pruvagraph project → allow

    # Load the graph node index (labels → file paths)
    node_index = _load_node_index(root)
    if not node_index:
        return None  # no graph → allow

    # Find which node(s) cover this file
    rel_path = _rel(file_path, root)
    matching_nodes = [
        (nid, label, tool)
        for nid, label, tool, fpath in node_index
        if fpath and (fpath == rel_path or fpath.endswith(rel_path))
    ]

    if not matching_nodes:
        return None  # file not in graph → allow (might be config, etc.)

    # Check session tracker
    try:
        from pruvagraph import session_tracker as st
        for node_id, label, seen_tool in matching_nodes:
            ref = st.already_seen(node_id, tool="Read")
            if ref:
                return {
                    "decision": "block",
                    "reason": (
                        f"[PruvaGraph Hook] '{label}' was already surfaced via "
                        f"{seen_tool} in this session.\n"
                        f"Use the MCP tool instead of reading the raw file:\n"
                        f"  → get_summary('{label}')\n"
                        f"  → get_dependencies('{label}')\n"
                        f"This avoids re-loading {_token_estimate(file_path)} tokens "
                        f"of context that is already available.\n"
                        f"(To override this block, use --no-hooks or rebuild with "
                        f"pruvagraph . --force)"
                    ),
                }

        # File is in graph but NOT yet seen this session:
        # Allow the Read, but record it so subsequent reads are blocked.
        for node_id, label, _ in matching_nodes:
            st.record_seen(node_id, tool="Read")

    except ImportError:
        pass  # session_tracker not available → allow

    return None  # allow


# ──────────────────────────────────────────────────────────────────────────────
# Node index loader (reads from pruvagraph-out/graph.json)
# ──────────────────────────────────────────────────────────────────────────────

_node_index_cache: dict[str, list] = {}  # root → list of (id, label, tool, file)


def _load_node_index(root: str) -> list:
    """Load or return cached (node_id, label, seen_tool, file_path) list."""
    if root in _node_index_cache:
        return _node_index_cache[root]

    graph_path = Path(root) / "pruvagraph-out" / "graph.json"
    if not graph_path.exists():
        return []

    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        nodes_raw = data.get("nodes", [])
        result = []
        for n in nodes_raw:
            nid   = n.get("id", "")
            label = n.get("label", nid)
            fpath = n.get("file", "") or ""
            result.append((nid, label, "", fpath))
        _node_index_cache[root] = result
        return result
    except Exception:
        return []


def _find_project_root(file_path: str) -> str | None:
    """Walk up from file_path until we find a pruvagraph-out/graph.json."""
    p = Path(file_path).resolve()
    for parent in [p, *p.parents]:
        if (parent / "pruvagraph-out" / "graph.json").exists():
            return str(parent)
    return None


def _rel(file_path: str, root: str) -> str:
    try:
        return str(Path(file_path).resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return file_path.replace("\\", "/")


def _token_estimate(file_path: str) -> str:
    try:
        size = Path(file_path).stat().st_size
        tokens = size // 4
        return f"~{tokens:,}"
    except Exception:
        return "potentially thousands of"


# ──────────────────────────────────────────────────────────────────────────────
# Hook installer — writes .claude/settings.json
# ──────────────────────────────────────────────────────────────────────────────

HOOK_BLOCK_START = "# pruvagraph:hooks:start"
HOOK_BLOCK_END   = "# pruvagraph:hooks:end"

_HOOK_ENTRY = {
    "matcher": "Read",
    "hooks": [
        {
            "type": "command",
            "command": f"{sys.executable} -m pruvagraph.hooks",
            "timeout": 5,
        }
    ],
}


def install_hooks(project_root: Path, dry_run: bool = False) -> Path:
    """
    Write (or update) .claude/settings.json to register the PreToolUse hook.

    Args:
        project_root: Directory containing .claude/ (or where it will be created).
        dry_run:      If True, print what would be written but don't write.

    Returns:
        Path to the settings.json that was (or would be) written.
    """
    settings_path = project_root / ".claude" / "settings.json"

    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    # Build updated hooks block
    hooks = existing.get("hooks", {})
    pre_tool = hooks.get("PreToolUse", [])

    # Remove any old pruvagraph hook entry (idempotent install)
    pre_tool = [h for h in pre_tool if _HOOK_ENTRY["matcher"] not in str(h)
                or "pruvagraph" not in str(h)]
    pre_tool.append(_HOOK_ENTRY)

    updated = {**existing, "hooks": {**hooks, "PreToolUse": pre_tool}}

    if dry_run:
        print(f"[dry-run] Would write to: {settings_path}")
        print(json.dumps(updated, indent=2))
        return settings_path

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    return settings_path


def remove_hooks(project_root: Path) -> bool:
    """
    Remove the pruvagraph PreToolUse hook from .claude/settings.json.

    Returns True if removed, False if not found.
    """
    settings_path = project_root / ".claude" / "settings.json"
    if not settings_path.exists():
        return False

    try:
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    hooks    = existing.get("hooks", {})
    pre_tool = hooks.get("PreToolUse", [])
    filtered = [h for h in pre_tool
                if not ("pruvagraph" in str(h) and h.get("matcher") == "Read")]

    if len(filtered) == len(pre_tool):
        return False  # nothing removed

    existing["hooks"]["PreToolUse"] = filtered
    settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Entry point:  python -m pruvagraph.hooks
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_hook()

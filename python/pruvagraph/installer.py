"""
IDE installer — writes integration files for VS Code, Cursor, Claude Code.

Called by ``pruvagraph install`` and by the VS Code extension's
"Install MCP" command.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def install_all(
    root: Path,
    vscode: bool = True,
    cursor: bool = True,
    claude_code: bool = True,
) -> dict[str, Path]:
    """
    Write IDE integration files.

    Returns dict of {name: path} for everything written.
    """
    written: dict[str, Path] = {}

    # Find the pruvagraph executable
    exe = _find_exe()

    mcp_config = _build_mcp_config(exe)

    if vscode:
        p = _write_vscode(root, mcp_config)
        written["VS Code MCP"] = p

    if cursor:
        p = _write_cursor(root, mcp_config)
        written["Cursor MCP"] = p

    if claude_code:
        p = _write_claude_code(mcp_config)
        if p:
            written["Claude Code MCP"] = p

    # Always write CLAUDE.md if it doesn't exist
    claude_md = _write_claude_md(root)
    written["CLAUDE.md"] = claude_md

    # gitignore entry
    _ensure_gitignore(root)

    return written


# ──────────────────────────────────────────────────────────────────────────────
# Per-IDE writers
# ──────────────────────────────────────────────────────────────────────────────


def _write_vscode(root: Path, mcp_config: dict) -> Path:
    config_dir = root / ".vscode"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "mcp.json"
    _merge_json(path, mcp_config)
    print(f"  ✓ VS Code MCP: {path}")
    return path


def _write_cursor(root: Path, mcp_config: dict) -> Path:
    config_dir = root / ".cursor"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "mcp.json"
    _merge_json(path, mcp_config)
    print(f"  ✓ Cursor MCP: {path}")
    return path


def _write_claude_code(mcp_config: dict) -> Path | None:
    """Write ~/.claude/mcp_config.json for Claude Code."""
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / "mcp_config.json"
    _merge_json(path, mcp_config)
    print(f"  ✓ Claude Code MCP: {path}")
    return path


def _write_claude_md(root: Path) -> Path:
    """Write CLAUDE.md instructions into the project root."""
    path = root / "CLAUDE.md"
    if path.exists():
        return path

    content = """\
# PruvaGraph — Codebase Knowledge Graph

This project uses **PRUVALEX PruvaGraph** to maintain a knowledge graph.

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `query_graph` | Ask anything about the codebase |
| `get_dependencies` | What does module X depend on? |
| `find_callers` | Who calls function X? |
| `get_summary` | One-sentence summary of any node |
| `list_communities` | Show architectural modules |
| `cost_report` | LLM cost savings from last build |

## Rebuild the Graph

```bash
pruvagraph .           # Full rebuild
pruvagraph . --update  # Incremental (changed files only)
pruvagraph . --dry-run # Estimate cost first
```

## Output Files

- `pruvagraph-out/graph.json`       — Full knowledge graph
- `pruvagraph-out/graph.html`       — Interactive visualisation
- `pruvagraph-out/GRAPH_REPORT.md`  — Architectural summary
- `pruvagraph-out/cost_report.json` — Cost analytics
"""
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ CLAUDE.md: {path}")
    return path


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _find_exe() -> list[str]:
    """Find the pruvagraph CLI command."""
    if shutil.which("pruvagraph"):
        return ["pruvagraph", "mcp-serve"]
    # Fallback: run as module
    return [sys.executable, "-m", "pruvagraph.mcp_server"]


def _build_mcp_config(cmd: list[str]) -> dict:
    return {
        "mcpServers": {
            "pruvagraph": {
                "command": cmd[0],
                "args": cmd[1:],
                "env": {},
                "description": "PRUVALEX PruvaGraph — query your codebase knowledge graph",
            }
        }
    }


def _merge_json(path: Path, new_data: dict) -> None:
    """Merge new_data into an existing JSON file (or create it)."""
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    merged = dict(existing)
    for k, v in new_data.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")


def _ensure_gitignore(root: Path) -> None:
    """Add pruvagraph-out/ to .gitignore if not already there."""
    gi = root / ".gitignore"
    entry = "pruvagraph-out/\n"
    if gi.exists():
        content = gi.read_text(encoding="utf-8")
        if "pruvagraph-out" not in content:
            gi.write_text(content.rstrip("\n") + "\n" + entry, encoding="utf-8")
    else:
        gi.write_text(entry, encoding="utf-8")

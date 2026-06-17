"""

IDE installer — writes integration files for VS Code, Cursor, Claude Code.

Called by ``pruvagraph install`` and by the VS Code extension's
"Install MCP" command.

Part E (v1.4.0): Fixed Claude Code installer.

  Detection order:
    1. ``claude`` CLI on PATH → use ``claude mcp add --scope <scope>``
       (future-proof: delegates config management to the official CLI)
    2. CLI not found → write ``.mcp.json`` to project root
       (``.mcp.json`` is the documented, stable, version-controllable
       project-scope schema — not a workaround.)

  Merge behaviour:
    Read → merge (add/update only ``pruvagraph`` entry) → write back.
    Never overwrites the entire file; other MCP servers are preserved.

  User messages:
    - CLI path: confirms scope and runs ``claude mcp list`` to verify.
    - Fallback path: explicitly tells user about manual approval requirement
      and schema validation result.

  Scope flags:
    ``--scope user``    (default) — registers for all projects for this user
    ``--scope project`` (``--project`` flag) — writes ``.mcp.json`` for teams

  The ``--cursor`` / ``--vscode`` flags write their own tool-specific config
  locations and are not affected by the Claude Code detection logic above.
"""

from __future__ import annotations

import json
import shutil
import subprocess
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
    hooks: bool = False,
    project_scope: bool = False,
) -> dict[str, Path]:
    """
    Write IDE integration files.

    Returns dict of {name: path} for everything written.

    Args:
        root:          Project root directory.
        vscode:        Write .vscode/mcp.json.
        cursor:        Write .cursor/mcp.json.
        claude_code:   Register with Claude Code via ``claude mcp add``
                       (falls back to .mcp.json if CLI not found).
        hooks:         Write .claude/settings.json with PreToolUse hook.
        project_scope: Use --scope project (team .mcp.json) instead of user.
    """
    written: dict[str, Path] = {}

    exe = _find_exe()
    mcp_config = _build_mcp_config(exe)

    if vscode:
        p = _write_vscode(root, mcp_config)
        written["VS Code MCP"] = p

    if cursor:
        p = _write_cursor(root, mcp_config)
        written["Cursor MCP"] = p

    if claude_code:
        result = _install_claude_code(root, mcp_config, project_scope=project_scope)
        if result:
            written["Claude Code MCP"] = result

    if hooks:
        p = _write_claude_hooks(root)
        if p:
            written["Claude Code Hooks"] = p

    claude_md = _write_claude_md(root)
    written["CLAUDE.md"] = claude_md

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


def _install_claude_code(
    root: Path,
    mcp_config: dict,
    project_scope: bool = False,
) -> Path | None:
    """
    Part E — Register pruvagraph with Claude Code.

    Detection order:
      1. ``claude`` CLI on PATH → ``claude mcp add`` (future-proof)
      2. Not found → write ``.mcp.json`` (documented stable schema)
    """
    scope = "project" if project_scope else "user"
    claude_cli = shutil.which("claude")

    if claude_cli:
        return _register_via_claude_cli(claude_cli, scope, mcp_config, root=root)
    else:
        return _fallback_write_mcp_json(root, mcp_config)


def _register_via_claude_cli(
    claude_cli: str,
    scope: str,
    mcp_config: dict,
    root: Path = Path("."),  # E3 fix: receive project root for fallback
) -> Path | None:
    """
    Strategy 1: use ``claude mcp add --transport stdio --scope <scope>``.

    Scope flag placed before server name per current Claude Code CLI spec:
      claude mcp add --transport stdio --scope <scope> <name> -- <cmd> [args]

    This stays correct automatically if Claude Code's internal config
    format changes in future versions, because config management is
    fully delegated to the official CLI.
    """
    server_cfg = mcp_config["mcpServers"]["pruvagraph"]
    serve_cmd: list[str] = [server_cfg["command"]] + server_cfg.get("args", [])

    # E1 fix: scope flag before server name (current Claude CLI spec)
    cmd = [
        claude_cli, "mcp", "add",
        "--transport", "stdio",
        "--scope", scope,
        "pruvagraph",
        "--",
    ] + serve_cmd

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )

        stderr = result.stderr.strip()
        already_exists = "already" in stderr.lower() or "exists" in stderr.lower()

        if result.returncode == 0 or already_exists:
            status = "already registered" if already_exists else f"registered (scope: {scope})"
            print(f"  ✓ Claude Code MCP: pruvagraph {status} via `claude mcp add`")
            _verify_claude_mcp_registration(claude_cli)
            return None  # CLI manages the config file; we wrote nothing

        # Non-zero exit, non-"already exists" error
        print(
            f"  ⚠ `claude mcp add` failed (exit {result.returncode}): {stderr}\n"
            f"    Falling back to .mcp.json",
            file=sys.stderr,
        )
    except subprocess.TimeoutExpired:
        print("  ⚠ `claude mcp add` timed out — falling back to .mcp.json", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠ `claude mcp add` error: {e} — falling back to .mcp.json", file=sys.stderr)

    # E3 fix: use project root passed from caller, not Path.cwd()
    return _fallback_write_mcp_json(root, mcp_config)


def _fallback_write_mcp_json(root: Path, mcp_config: dict) -> Path:
    """
    Strategy 2 (fallback): write ``.mcp.json`` to project root.

    ``.mcp.json`` is the documented, stable, version-controllable
    project-scope MCP config schema. Writing it directly is the supported
    path when the ``claude`` CLI is unavailable — not a workaround.

    Per refinement:
    - Read-merge-write: parse existing file, update only the ``pruvagraph``
      entry, write back. Other MCP servers are preserved.
    - Validates the written JSON against the MCP schema before reporting success.
    - Tells the user explicitly about the manual-approval requirement.
    """
    path = root / ".mcp.json"

    # Read → merge (update only the pruvagraph entry) → write
    _merge_json(path, mcp_config)

    # Validate the written JSON against MCP schema
    _validate_mcp_json(path)

    print(f"  ✓ .mcp.json written (project-scope MCP config): {path}")
    print(
        "\n  ⚠ Note: Claude Code CLI not found on PATH.\n"
        "    pruvagraph has been added to .mcp.json instead.\n\n"
        "    When you open this folder in Claude Code, it will prompt:\n"
        "      'Allow MCP server pruvagraph?' — approve it to activate.\n\n"
        "    To verify once Claude Code is installed:\n"
        "      Install the `claude` CLI, then run: claude mcp list\n"
        "    Or use the /mcp slash command inside Claude Code to see active servers.\n\n"
        "    Alternatively, install the claude CLI and re-run:\n"
        "      pruvagraph . install --claude-code"
    )
    return path


def _validate_mcp_json(path: Path) -> None:
    """
    Validate the written .mcp.json against the MCP server schema:
      mcpServers.<name>.command  (str, required)
      mcpServers.<name>.args     (list[str], optional)
      mcpServers.<name>.env      (dict[str, str], optional)

    Prints a warning if any required field is missing; does not raise.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        pg = servers.get("pruvagraph", {})
        errors: list[str] = []
        if not isinstance(pg.get("command"), str):
            errors.append("  • 'command' must be a string")
        if "args" in pg and not isinstance(pg["args"], list):
            errors.append("  • 'args' must be a list")
        if "env" in pg and not isinstance(pg["env"], dict):
            errors.append("  • 'env' must be a dict")
        if errors:
            print(
                "  ⚠ .mcp.json schema validation warnings:\n" + "\n".join(errors),
                file=sys.stderr,
            )
        else:
            print("  ✓ .mcp.json schema validated ✅")
    except Exception as e:
        print(f"  ⚠ Could not validate .mcp.json: {e}", file=sys.stderr)


def _verify_claude_mcp_registration(claude_cli: str) -> None:
    """Run ``claude mcp list`` and confirm pruvagraph appears."""
    try:
        result = subprocess.run(
            [claude_cli, "mcp", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).lower()
        if "pruvagraph" in output:
            print("  ✓ Verified: `claude mcp list` shows pruvagraph as connected ✅")
        else:
            print(
                "  ⚠ Warning: `claude mcp list` did not mention pruvagraph.\n"
                "    Try restarting Claude Code and running `claude mcp list` manually.",
                file=sys.stderr,
            )
    except Exception:
        pass  # verification is best-effort


def _write_claude_hooks(root: Path) -> Path | None:
    """Gap 1 — Write .claude/settings.json with PreToolUse Read-interception hook."""
    try:
        from pruvagraph.hooks import install_hooks
        path = install_hooks(root)
        print(
            f"  ✓ Claude Code Hooks (Gap 1 — PreToolUse Read enforcement): {path}\n"
            f"    Restart Claude Code to activate."
        )
        return path
    except Exception as e:
        print(f"  ⚠ Could not install hooks: {e}", file=sys.stderr)
        return None


def _write_claude_md(root: Path) -> Path:
    """Write or overwrite CLAUDE.md with enforced tool-first instructions."""
    path = root / "CLAUDE.md"
    content = """\
# PruvaGraph — Codebase Knowledge Graph

This project uses **PRUVALEX PruvaGraph** to maintain a pre-built knowledge graph
(`pruvagraph-out/graph.json`). This graph encodes the full structure of the codebase
at a fraction of the token cost of reading raw files.

---

## MANDATORY: Use Graph Tools Before Reading Files

> **Before opening any source file, reading any directory listing, or using `grep`
> for any question about codebase structure, call one of the MCP tools below.**
>
> The graph already contains: imports, dependencies, callers, community clusters,
> type signatures, and architectural summaries — fully offline, no API cost.
>
> **Reading raw files when the graph has the answer wastes 5×–71× more tokens.**

| If you want to know… | Use this tool FIRST |
|---|---|
| How module X connects to Y | `query_graph "how does X connect to Y?"` |
| What a class/function does | `get_summary "ClassName"` |
| What file A imports | `get_dependencies "path/to/file.py"` |
| Who calls function F | `find_callers "function_name"` |
| Architectural overview | `list_communities` |
| What changed structurally | `get_graph_diff` |
| What breaks if X changes | `analyze_impact "SymbolName"` |
| Monorepo packages | `list_packages` |
| Cost savings so far | `cost_report` |

Only open a raw file if:
1. The graph tool returns "not found" for the specific symbol, OR
2. You need to edit the file (structure info still comes from graph first), OR
3. The question is about the content of a specific function body (not its connections).

---

## Rebuild the Graph

```bash
pruvagraph .            # Full rebuild
pruvagraph . --update   # Incremental (changed files only)
pruvagraph . --dry-run  # Estimate cost first
pruvagraph . --force    # Force full rebuild, ignore cache
```

## Output Files

- `pruvagraph-out/graph.json`       — Full knowledge graph (MCP server reads this)
- `pruvagraph-out/graph.html`       — Interactive visualiser (open in browser)
- `pruvagraph-out/GRAPH_REPORT.md`  — Architectural summary + god nodes
- `pruvagraph-out/cost_report.json` — Cost analytics + query benchmarks
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
        return ["pruvagraph"]
    return [sys.executable, "-m", "pruvagraph"]


def _build_mcp_config(cmd: list[str]) -> dict:
    serve_cmd = cmd + ["serve"]
    return {
        "mcpServers": {
            "pruvagraph": {
                "command": serve_cmd[0],
                "args": serve_cmd[1:],
                "env": {},
                "description": "PRUVALEX PruvaGraph — query your codebase knowledge graph",
            }
        }
    }


def _merge_json(path: Path, new_data: dict) -> None:
    """
    Read-merge-write: parse existing JSON file, update only the keys from
    new_data, write back. Other keys (e.g., other MCP servers) are preserved.
    Creates the file if it does not exist.
    """
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass  # malformed JSON — treat as empty and overwrite
    merged = dict(existing)
    for k, v in new_data.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            # Deep merge one level (e.g., mcpServers dict)
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")


def _ensure_gitignore(root: Path) -> None:
    """Add pruvagraph-out/ to .gitignore; never add .mcp.json (it's team config)."""
    gi = root / ".gitignore"
    existing_content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if "pruvagraph-out" not in existing_content:
        separator = "\n" if existing_content and not existing_content.endswith("\n") else ""
        gi.write_text(existing_content + separator + "pruvagraph-out/\n", encoding="utf-8")

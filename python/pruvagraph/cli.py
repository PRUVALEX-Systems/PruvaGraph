"""
PruvaGraph CLI — pruvagraph

Usage:
    pruvagraph .                     Build graph for current directory
    pruvagraph . --backend gemini    Use Gemini (cheaper)
    pruvagraph . --cascade           3-tier local → cheap → premium
    pruvagraph . --dry-run           Estimate cost, don't extract
    pruvagraph . --budget 2.00       Hard spend cap
    pruvagraph . --update            Incremental (changed files only)
    pruvagraph query "..."           Query the graph
    pruvagraph cost-report           Show last run's cost breakdown
    pruvagraph benchmark             Token savings vs reading raw files
    pruvagraph install               Write IDE integration files
    pruvagraph hook install          Install git post-commit hook
    pruvagraph export --format html   Export graph in various formats
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

try:
    from rich.console import Console
    from rich.table import Table
    _RICH = True
except ImportError:
    _RICH = False


_CONSOLE = Console() if _RICH else None

LOGO = """
╔═══════════════════════════════════════╗
║  PruvaGraph  ·  by PRUVALEX           ║
║  Codebase graphs. 95%+ cost savings.  ║
╚═══════════════════════════════════════╝"""


# ──────────────────────────────────────────────────────────────────────────────
# Root group
# ──────────────────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.argument("root", default=".", required=False)
@click.option("--backend", "-b", default="none",
              type=click.Choice(["none", "claude", "gemini", "kimi", "openai", "ollama"]),
              show_default=True, help="LLM backend for doc/image extraction (none = code only, free).")
@click.option("--cascade", is_flag=True,
              help="3-tier cascade: local → cheap → premium.")
@click.option("--update", "-u", is_flag=True,
              help="Incremental: only process changed files.")
@click.option("--force", "-f", is_flag=True,
              help="Ignore cache — re-extract all files.")
@click.option("--dry-run", is_flag=True,
              help="Estimate cost without extracting.")
@click.option("--budget", type=float, default=None, metavar="USD",
              help="Hard spend cap in USD. Aborts if estimate exceeds it.")
@click.option("--dedup-threshold", type=float, default=0.82, show_default=True,
              help="Jaccard similarity threshold for semantic dedup (0–1).")
@click.option("--batch-tokens", type=int, default=12_000, show_default=True,
              help="Max tokens per LLM batch.")
@click.option("--no-viz", is_flag=True,
              help="Skip HTML graph generation (faster for CI).")
@click.option("--out-dir", default="pruvagraph-out", show_default=True,
              help="Output directory name.")
@click.option("--stream", is_flag=True,
              help="[Arch1] Write partial graph during build — enables querying before completion.")
@click.option("--monorepo", is_flag=True,
              help="[M1] Auto-detect monorepo layout and build per-package graphs.")
@click.pass_context
def main(
    ctx: click.Context,
    root: str,
    backend: str,
    cascade: bool,
    update: bool,
    force: bool,
    dry_run: bool,
    budget: float | None,
    dedup_threshold: float,
    batch_tokens: int,
    no_viz: bool,
    out_dir: str,
    stream: bool,
    monorepo: bool,
) -> None:
    """PruvaGraph — codebase knowledge graphs with 95%+ LLM cost reduction.\n
    Build a graph:\n
        pruvagraph .                   # current directory\n
        pruvagraph ./src --backend gemini\n
    Query it:\n
        pruvagraph query "how does auth connect to the DB?"\n
    See cost savings:\n
        pruvagraph cost-report\n
    """
    if ctx.invoked_subcommand is not None:
        return

    if _RICH:
        try:
            _CONSOLE.print(f"[bold cyan]{LOGO}[/bold cyan]")
        except UnicodeEncodeError:
            click.echo("PruvaGraph — by PRUVALEX (codebase graphs, 95%+ cost savings)")

    root_path = Path(root).resolve()
    if not root_path.exists():
        click.echo(f"Error: '{root}' does not exist.", err=True)
        sys.exit(1)

    from pruvagraph.pipeline import BudgetExceededError, build_graph

    try:
        result = build_graph(
            root=root_path,
            backend=backend,
            cascade=cascade,
            budget_usd=budget,
            dry_run=dry_run,
            force=force,
            dedup_threshold=dedup_threshold,
            max_tokens_per_batch=batch_tokens,
            no_viz=no_viz,
            out_dir=out_dir,
            streaming=stream,
            monorepo=monorepo,
        )
    except BudgetExceededError as e:
        click.echo(f"\n⛔ {e}", err=True)
        sys.exit(1)

    if not dry_run:
        _print_success(result, out_dir)


# ──────────────────────────────────────────────────────────────────────────────
# Subcommands
# ──────────────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("question")
@click.option("--root", default=".", show_default=True)
@click.option("--backend", "-b", default="none",
              type=click.Choice(["none", "claude", "gemini", "kimi", "openai", "ollama"]))
def query(question: str, root: str, backend: str) -> None:
    """Query the knowledge graph in natural language."""
    out_dir = Path(root) / "pruvagraph-out"
    try:
        from pruvagraph.streaming import get_build_status, load_best_graph, partial_graph_note
        G, is_partial = load_best_graph(out_dir)
    except ImportError:
        import networkx as nx
        graph_json = out_dir / "graph.json"
        if not graph_json.exists():
            click.echo("No graph found. Run 'pruvagraph .' first.", err=True)
            sys.exit(1)
        G = nx.node_link_graph(json.loads(graph_json.read_text()))
        is_partial = False

    if G is None:
        click.echo("No graph found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)

    if is_partial:
        try:
            status = get_build_status(out_dir)
            click.echo(click.style(partial_graph_note(status.get("percent", 0)).strip(), fg="yellow"))
        except Exception:
            click.echo(click.style("⚠️  Note: Graph is partially built.", fg="yellow"))

    from pruvagraph.query import query as _query
    answer = _query(G, question, backend=backend)
    click.echo(answer)


@main.command("cost-report")
@click.option("--root", default=".", show_default=True)
def cost_report_cmd(root: str) -> None:
    """Show cost analytics from the last run."""
    report_path = Path(root) / "pruvagraph-out" / "cost_report.json"
    if not report_path.exists():
        click.echo("No cost report found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)

    data = json.loads(report_path.read_text())

    if _RICH:
        t = Table(title="PruvaGraph — Cost Report", show_header=True)
        t.add_column("Metric", style="cyan")
        t.add_column("Value", justify="right")
        rows = [
            ("Files processed",    f"{data['total_files_processed']:,}"),
            ("Cache hits (free)",  f"{data['cache_hits']:,}"),
            ("Dedup projected",    f"{data['dedup_projected']:,}"),
            ("LLM calls made",     f"{data['llm_calls_made']:,}"),
            ("Naive calls (est.)", f"{data['naive_calls']:,}"),
            ("Calls saved",        f"{data['calls_saved']:,}"),
            ("Actual cost",        f"${data['actual_cost_usd']:.6f}"),
            ("Naive cost (est.)",  f"${data['naive_cost_usd']:.4f}"),
            ("Cost saved",         f"${data['cost_saved_usd']:.4f}"),
            ("Savings %",          f"{data['savings_pct']:.1f}%"),
            ("Run time",           f"{data['run_duration_seconds']:.1f}s"),
        ]
        for label, value in rows:
            t.add_row(label, value)
        _CONSOLE.print(t)
    else:
        for k, v in data.items():
            if k != "calls":
                click.echo(f"{k}: {v}")


@main.command()
@click.option("--root", default=".", show_default=True)
@click.option("--format", "fmt",
              type=click.Choice(["cypher", "obsidian", "graphml", "html"]),
              default="html", show_default=True)
def export(root: str, fmt: str) -> None:
    """Export the graph in various formats."""
    graph_json = Path(root) / "pruvagraph-out" / "graph.json"
    if not graph_json.exists():
        click.echo("No graph found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)

    from pruvagraph.export import export_format
    out = export_format(graph_json, fmt)
    click.echo(f"Exported: {out}")


@main.command()
@click.option("--root", default=".", show_default=True)
@click.option("--vscode", is_flag=True, help="Write VS Code integration files.")
@click.option("--cursor", is_flag=True, help="Write Cursor rules.")
@click.option("--claude-code", "claude_code", is_flag=True,
              help="Register MCP server for Claude Code.")
@click.option("--hooks", is_flag=True,
              help="[Gap 1] Install Claude Code PreToolUse hooks — hard Read enforcement.")
def install(root: str, vscode: bool, cursor: bool, claude_code: bool, hooks: bool) -> None:
    """Write IDE integration files (CLAUDE.md, MCP config, optional hooks)."""
    from pruvagraph.installer import install_all
    all_flags = not vscode and not cursor and not claude_code and not hooks
    install_all(
        Path(root),
        vscode=vscode or all_flags,
        cursor=cursor or all_flags,
        claude_code=claude_code or all_flags,
        hooks=hooks,   # Gap 1: opt-in, not on by default for --all
    )
    click.echo("✓ Integration files written.")
    if hooks:
        click.echo(
            "  → Restart Claude Code to activate PreToolUse hook enforcement."
        )


@main.group()
def hook() -> None:
    """Manage git hooks."""


@hook.command("install")
@click.option("--root", default=".", show_default=True)
def hook_install(root: str) -> None:
    """Install post-commit hook for auto-update on git commit."""
    hook_path = Path(root) / ".git" / "hooks" / "post-commit"
    if not (Path(root) / ".git").exists():
        click.echo("Not a git repository.", err=True)
        sys.exit(1)

    script = """#!/bin/bash
# PruvaGraph auto-update hook
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -E '\\.(ts|tsx|js|jsx|py|go|rs|kt|swift|dart|vue|md|pdf)$')  # noqa: E501
if [ -n "$CHANGED" ]; then
  pruvagraph . --update --no-viz 2>&1 | tail -5
fi
"""
    hook_path.write_text(script)
    hook_path.chmod(0o755)
    click.echo(f"✓ Hook installed: {hook_path}")


# ── Gap 1: Claude Code PreToolUse hooks subcommand ─────────────────────────

@main.group("hooks")
def hooks_group() -> None:
    """[Gap 1] Manage Claude Code PreToolUse Read-enforcement hooks."""


@hooks_group.command("install")
@click.option("--root", default=".", show_default=True)
@click.option("--dry-run", is_flag=True, help="Print what would be written, don't write.")
def hooks_install(root: str, dry_run: bool) -> None:
    """Install PreToolUse hook in .claude/settings.json.

    This gives Claude Code HARD enforcement: every Read tool call fires the
    pruvagraph.hooks handler.  If the file was already surfaced via MCP tools
    this session, the Read is blocked with a redirect message.
    """
    from pruvagraph.hooks import install_hooks
    path = install_hooks(Path(root), dry_run=dry_run)
    if not dry_run:
        click.echo(f"✓ Hooks installed: {path}")
        click.echo("  Restart Claude Code to activate.")


@hooks_group.command("remove")
@click.option("--root", default=".", show_default=True)
def hooks_remove(root: str) -> None:
    """Remove PruvaGraph hook from .claude/settings.json."""
    from pruvagraph.hooks import remove_hooks
    removed = remove_hooks(Path(root))
    if removed:
        click.echo("✓ PruvaGraph hook removed from .claude/settings.json")
    else:
        click.echo("No PruvaGraph hook found in .claude/settings.json")


@hooks_group.command("status")
@click.option("--root", default=".", show_default=True)
def hooks_status(root: str) -> None:
    """Check whether the PreToolUse hook is installed."""
    settings = Path(root) / ".claude" / "settings.json"
    if not settings.exists():
        click.echo("✗ .claude/settings.json not found — hooks not installed")
        return
    import json as _j
    try:
        data = _j.loads(settings.read_text(encoding="utf-8"))
        hooks_list = data.get("hooks", {}).get("PreToolUse", [])
        pg_hooks = [h for h in hooks_list if "pruvagraph" in str(h)]
        if pg_hooks:
            click.echo(click.style("✓ PruvaGraph PreToolUse hook is ACTIVE", fg="green"))
            click.echo(f"  Settings: {settings}")
        else:
            click.echo("✗ PruvaGraph hook not found — run: pruvagraph hooks install")
    except Exception as e:
        click.echo(f"Error reading settings: {e}", err=True)



@main.command()
@click.option("--root", default=".", show_default=True)
def benchmark(root: str) -> None:
    """Compare token cost: graph queries vs reading raw files directly."""
    from pruvagraph.benchmark import run_benchmark
    graph_json = Path(root) / "pruvagraph-out" / "graph.json"
    if not graph_json.exists():
        click.echo("No graph found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)
    result = run_benchmark(graph_json)
    click.echo(result)


@main.command("build-from-lsp")
@click.argument("lsp_json", type=click.Path(exists=True))
@click.option("--backend", "-b", default="none")
@click.option("--stream", is_flag=True)
def build_from_lsp(lsp_json: str, backend: str, stream: bool) -> None:
    """[N3] Fast Build bypassing Tree-sitter, using LSP symbols from IDE."""
    import json
    data = json.loads(Path(lsp_json).read_text(encoding="utf-8"))
    
    # Transform to pruvagraph internal format
    extractions = []
    for filepath, symbols in data.items():
        nodes = []
        for sym in symbols:
            kind = sym.get("kind", "Unknown").lower()
            name = sym.get("name", "")
            if kind in ("class", "interface"):
                ntype = "class"
            elif kind in ("function", "method"):
                ntype = "function"
            elif kind in ("variable", "constant"):
                ntype = "variable"
            else:
                ntype = "symbol"
            
            nodes.append({
                "id": f"{Path(filepath).name}:{name}",
                "name": name,
                "type": ntype,
                "label": f"[{ntype}] {name}",
                "summary": sym.get("detail", ""),
                "file": str(filepath)
            })
        extractions.append({"source_file": str(filepath), "nodes": nodes, "edges": []})

    from pruvagraph.pipeline import build_graph_from_extractions
    root = Path(lsp_json).parent.parent
    result = build_graph_from_extractions(root, extractions, backend=backend, streaming=stream)
    
    click.echo(f"✓ N3 LSP Build complete. Graph: {result.node_count} nodes.")

@main.command()
@click.argument("root", default=".")
def watch(root: str) -> None:
    """Watch for file changes and auto-update the graph (with Arch3 pre-warming)."""
    from pruvagraph.watch import watch_and_update
    click.echo(f"Watching {root} for changes... (Ctrl+C to stop)")
    click.echo("  ⚡ Arch3 pre-warming active — answers pre-computed after each change")
    watch_and_update(Path(root))


@main.command("build-status")
@click.option("--root", default=".", show_default=True)
def build_status_cmd(root: str) -> None:
    """[Arch1] Show streaming build progress status."""
    from pruvagraph.streaming import get_build_status
    out_dir = Path(root) / "pruvagraph-out"
    status = get_build_status(out_dir)
    s = status.get("status", "idle")
    pct = status.get("percent", 0)
    done = status.get("files_done", 0)
    total = status.get("files_total", 0)
    msg = status.get("message", "")
    icon = {"building": "🔨", "complete": "✅", "idle": "💤", "error": "❌"}.get(s, "❓")
    click.echo(f"{icon} Build {s}: {done}/{total} files ({pct}%) — {msg}")


# ── D1: Graph Diff ─────────────────────────────────────────────────────────

@main.command("diff")
@click.option("--root", default=".", show_default=True,
              help="Project root (where pruvagraph-out/ lives).")
@click.option("--format", "fmt", default="table",
              type=click.Choice(["table", "json"]), show_default=True,
              help="Output format.")
def diff_cmd(root: str, fmt: str) -> None:
    """[D1] Show what changed between the last two graph builds."""
    from pruvagraph.graph_diff import load_diff
    out_dir = Path(root) / "pruvagraph-out"
    diff = load_diff(out_dir)
    if diff is None:
        click.echo("No diff available. Run 'pruvagraph .' at least twice.", err=True)
        sys.exit(1)

    if fmt == "json":
        import json as _json
        click.echo(_json.dumps({
            "added_nodes":   diff.added_nodes,
            "removed_nodes": diff.removed_nodes,
            "changed_nodes": diff.changed_nodes,
            "added_edges":   diff.added_edges,
            "removed_edges": diff.removed_edges,
            "diff_summary":  diff.diff_summary,
            "timestamp":     diff.timestamp,
            "git_sha":       diff.git_sha,
        }, indent=2))
    else:
        click.echo(diff.format())


# ── D2: Impact Analyzer ────────────────────────────────────────────────────

@main.command("impact")
@click.argument("symbol")
@click.option("--root", default=".", show_default=True)
@click.option("--depth", default=3, show_default=True,
              help="BFS depth limit (higher = more transitive dependents).")
@click.option("--format", "fmt", default="table",
              type=click.Choice(["table", "json"]), show_default=True,
              help="Output format (json for CI gates).")
def impact_cmd(symbol: str, root: str, depth: int, fmt: str) -> None:
    """[D2] Analyse the blast radius of changing a symbol or file.

    SYMBOL can be a function name, class name, file path, or node ID.
    Uses fuzzy matching — partial names work.

    \b
    Examples:
        pruvagraph impact SessionManager
        pruvagraph impact "auth.py" --depth 4
        pruvagraph impact build_graph --format json
    """
    import json as _json
    import networkx as nx

    out_dir   = Path(root) / "pruvagraph-out"
    graph_path = out_dir / "graph.json"
    if not graph_path.exists():
        click.echo("No graph found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)

    G = nx.node_link_graph(_json.loads(graph_path.read_text(encoding="utf-8")))

    # Try to load git intel for richer risk scoring
    git_intel: dict | None = None
    try:
        from pruvagraph.git_intel import extract_git_intelligence
        intel = extract_git_intelligence(Path(root))
        if intel.get("available"):
            git_intel = intel
    except Exception:
        pass

    from pruvagraph.impact_analyzer import analyze_impact
    report = analyze_impact(G, symbol, depth=depth, git_intel=git_intel)
    click.echo(report.format(fmt))

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _print_success(result: Any, out_dir: str) -> None:
    cr = result.cost_report
    lines = [
        f"\n✓ Graph built: {result.node_count} nodes · {result.edge_count} edges · "
        f"{result.community_count} communities",
        f"✓ Cost: ${cr.actual_cost_usd:.4f} (saved ${cr.cost_saved_usd:.4f}, "
        f"{cr.savings_pct:.0f}%)",
    ]
    if result.html_path:
        lines.append(f"→ Open: {result.html_path}")
    lines.append(f"→ Report: {result.report_path}")
    click.echo("\n".join(lines))


if __name__ == "__main__":
    main()

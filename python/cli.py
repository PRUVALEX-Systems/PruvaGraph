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
    pruvagraph export --format pdf   Export graph in various formats
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
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
@click.option("--backend", "-b", default="claude",
              type=click.Choice(["claude", "gemini", "kimi", "openai", "ollama"]),
              show_default=True, help="LLM backend for doc/image extraction.")
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
        _CONSOLE.print(f"[bold cyan]{LOGO}[/bold cyan]")

    root_path = Path(root).resolve()
    if not root_path.exists():
        click.echo(f"Error: '{root}' does not exist.", err=True)
        sys.exit(1)

    from pruvagraph.pipeline import build_graph, BudgetExceededError

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
@click.option("--backend", "-b", default="claude",
              type=click.Choice(["claude", "gemini", "kimi", "openai", "ollama"]))
def query(question: str, root: str, backend: str) -> None:
    """Query the knowledge graph in natural language."""
    graph_json = Path(root) / "pruvagraph-out" / "graph.json"
    if not graph_json.exists():
        click.echo("No graph found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)

    from pruvagraph.query import query as _query
    import networkx as nx
    G = nx.node_link_graph(json.loads(graph_json.read_text()))
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
              type=click.Choice(["cypher", "obsidian", "graphml", "html", "pdf"]),
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
def install(root: str, vscode: bool, cursor: bool, claude_code: bool) -> None:
    """Write IDE integration files (CLAUDE.md, .cursor/rules, MCP config)."""
    from pruvagraph.installer import install_all
    install_all(
        Path(root),
        vscode=vscode or (not vscode and not cursor and not claude_code),
        cursor=cursor or (not vscode and not cursor and not claude_code),
        claude_code=claude_code or (not vscode and not cursor and not claude_code),
    )
    click.echo("✓ Integration files written.")


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
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -E '\\.(ts|tsx|js|jsx|py|go|rs|kt|swift|dart|vue|md|pdf)$')
if [ -n "$CHANGED" ]; then
  pruvagraph . --update --no-viz 2>&1 | tail -5
fi
"""
    hook_path.write_text(script)
    hook_path.chmod(0o755)
    click.echo(f"✓ Hook installed: {hook_path}")


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


@main.command()
@click.argument("root", default=".")
def watch(root: str) -> None:
    """Watch for file changes and auto-update the graph."""
    from pruvagraph.watch import watch_and_update
    click.echo(f"Watching {root} for changes... (Ctrl+C to stop)")
    watch_and_update(Path(root))


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

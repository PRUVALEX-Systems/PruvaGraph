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


class RootGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] in self.commands:
            if "root" not in ctx.params or ctx.params["root"] is None:
                ctx.params["root"] = "."
            saved_params = self.params
            self.params = [p for p in self.params if getattr(p, 'name', None) != 'root']
            try:
                return super().parse_args(ctx, args)
            finally:
                self.params = saved_params

        if args and args[0].startswith("-"):
            return super().parse_args(ctx, args)

        # If the first token is not a subcommand, treat it as the root path.
        ctx.params["root"] = args.pop(0)
        return super().parse_args(ctx, args)

try:
    from rich.console import Console
    from rich.table import Table
    _RICH = True
except ImportError:
    _RICH = False


_CONSOLE = Console() if _RICH else None

LOGO = """
╬═══════════════════════════════════════╣
║  PruvaGraph  ·  by PRUVALEX           ║
║  70.5%-81.5% Token Savings •           ║
║  up to 100% Cache Bypass.            ║
╚═══════════════════════════════════════╝"""


# ──────────────────────────────────────────────────────────────────────────────
# Root group
# ──────────────────────────────────────────────────────────────────────────────

@click.group(cls=RootGroup, invoke_without_command=True)
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
            click.echo("PruvaGraph -- by PRUVALEX (70.5%-81.5% token savings, up to 100% cache bypass)")

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


@main.command("report-dashboard")
@click.option("--root", default=".", show_default=True)
def report_dashboard(root: str) -> None:
    """Show a Markdown + CLI dashboard report for ROI and cost savings."""
    report_path = Path(root) / "pruvagraph-out" / "cost_report.json"
    if not report_path.exists():
        click.echo("No cost report found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)

    data = json.loads(report_path.read_text())
    graph_json = Path(root) / "pruvagraph-out" / "graph.json"
    benchmark_text = ""
    compression_pct = None
    raw_tokens = None
    graph_tokens = None

    if graph_json.exists():
        try:
            from pruvagraph.benchmark import run_benchmark
            benchmark_text = run_benchmark(graph_json)
            import re
            match = re.search(r"Raw codebase tokens:\s+([0-9,]+)", benchmark_text)
            if match:
                raw_tokens = int(match.group(1).replace(",", ""))
            match = re.search(r"PruvaGraph tokens:\s+([0-9,]+)", benchmark_text)
            if match:
                graph_tokens = int(match.group(1).replace(",", ""))
            match = re.search(r"Token savings:\s+([0-9\.]+)%", benchmark_text)
            if match:
                compression_pct = float(match.group(1))
        except Exception:
            benchmark_text = ""

    cache_hit_rate = (
        data["cache_hits"] / data["total_files_processed"] * 100
        if data["total_files_processed"] > 0 else 0.0
    )
    paid_calls_bypassed = (
        data["calls_saved"] / (data["calls_saved"] + data["llm_calls_made"]) * 100
        if (data["calls_saved"] + data["llm_calls_made"]) > 0 else 0.0
    )

    markdown_rows = [
        ("Metric", "Value"),
        ("Files processed", f"{data['total_files_processed']:,}"),
        ("Cache hits (free)", f"{data['cache_hits']:,}"),
        ("LLM calls made", f"{data['llm_calls_made']:,}"),
        ("Naive calls (est.)", f"{data['naive_calls']:,}"),
        ("Calls saved", f"{data['calls_saved']:,}"),
        ("Actual cost", f"${data['actual_cost_usd']:.6f}"),
        ("Naive cost (est.)", f"${data['naive_cost_usd']:.4f}"),
        ("Cost saved", f"${data['cost_saved_usd']:.4f}"),
        ("Savings %", f"{data['savings_pct']:.1f}%"),
    ]
    if compression_pct is not None:
        markdown_rows.append(("Token compression (vs raw files)", f"{compression_pct:.1f}%"))
    markdown_rows.extend([
        ("Build cache hit rate", f"{cache_hit_rate:.1f}%"),
        ("Paid calls bypassed", f"{paid_calls_bypassed:.1f}%"),
        ("Run time", f"{data['run_duration_seconds']:.1f}s"),
    ])

    md_lines = ["| Metric | Value |", "|---|---|"]
    for label, value in markdown_rows:
        md_lines.append(f"| {label} | {value} |")

    dashboard = [
        "PruvaGraph — Cost & ROI Dashboard",
        "-----------------------------------",
        f"Files processed:    {data['total_files_processed']:,}",
        f"Cache hits (free):  {data['cache_hits']:,}",
        f"LLM calls made:     {data['llm_calls_made']:,}",
        f"Naive calls (est.): {data['naive_calls']:,}",
        f"Calls saved:        {data['calls_saved']:,}",
        "",
        f"Actual cost:        ${data['actual_cost_usd']:.6f}",
        f"Naive cost (est.):  ${data['naive_cost_usd']:.4f}",
        f"Cost saved:         ${data['cost_saved_usd']:.4f}",
        f"Savings %:          {data['savings_pct']:.1f}%",
        "",
        f"Token compression (vs raw files):  {compression_pct:.1f}%" if compression_pct is not None else "Token compression (vs raw files):  unavailable",
        f"Build cache hit rate:  {cache_hit_rate:.1f}%",
        f"Paid calls bypassed:         {paid_calls_bypassed:.1f}%",
        "",
        f"Run time:           {data['run_duration_seconds']:.1f}s",
    ]

    if _RICH:
        t = Table(title="PruvaGraph — ROI Dashboard", show_header=True)
        t.add_column("Metric", style="cyan")
        t.add_column("Value", justify="right")
        for label, value in markdown_rows:
            t.add_row(label, value)
        _CONSOLE.print(t)
        _CONSOLE.print("\n[bold]Markdown Summary:[/bold]\n")
        _CONSOLE.print("\n".join(md_lines))
        _CONSOLE.print("\n".join(dashboard))
    else:
        click.echo("\n".join(md_lines))
        click.echo("\n".join(dashboard))


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
@click.option("--project", "project_scope", is_flag=True,
              help="Use --scope project (team config in .mcp.json) instead of --scope user.")
@click.option("--disable-modules", "disable_modules", default="",
              help="Comma-separated module keys to disable, e.g. 'taskweaver,rulesforge'. "
                   "Written as PRUVAGRAPH_DISABLED_MODULES in the MCP config env block "
                   "so the server excludes those tools on startup. "
                   "Set automatically by the VS Code extension based on workspace settings.")
def install(root: str, vscode: bool, cursor: bool, claude_code: bool,
            hooks: bool, project_scope: bool, disable_modules: str) -> None:
    """Write IDE integration files (CLAUDE.md, MCP config, optional hooks)."""
    from pruvagraph.installer import install_all
    all_flags = not vscode and not cursor and not claude_code and not hooks
    disabled = [m.strip() for m in disable_modules.split(",") if m.strip()] or None
    install_all(
        Path(root),
        vscode=vscode or all_flags,
        cursor=cursor or all_flags,
        claude_code=claude_code or all_flags,
        hooks=hooks,
        project_scope=project_scope,
        disabled_modules=disabled,
    )
    click.echo("✓ Integration files written.")
    if disabled:
        click.echo(f"  → Disabled modules: {', '.join(disabled)}")
        click.echo("    PRUVAGRAPH_DISABLED_MODULES is set in MCP config env.")
    if hooks:
        click.echo(
            "  → Restart Claude Code to activate PreToolUse hook enforcement."
        )



# ── Part E: serve subcommand ─────────────────────────────────────────────────

@main.command("serve")
@click.option("--root", default=".", show_default=True,
              help="Project root to use for graph files.")
def serve_cmd(root: str) -> None:
    """Start the MCP server over stdio (used by `claude mcp add`).

    This is the entry point registered by the Claude Code installer:
        claude mcp add --transport stdio pruvagraph -- pruvagraph serve

    The server reads graph.json from <root>/pruvagraph-out/ and exposes
    13 MCP tools (query_graph, get_dependencies, find_callers, get_summary,
    list_communities, cost_report, get_graph_diff, analyze_impact,
    list_packages, remember, recall, validate_import, scan_suggestion).
    """
    import os
    # Set the root so the MCP server knows where to find graph.json
    os.environ["PRUVAGRAPH_ROOT"] = str(Path(root).resolve())
    from pruvagraph.mcp_server import run_server
    run_server()


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


@main.command("benchmark-suite")
@click.option("--root", default=".", show_default=True,
              help="Project root (where pruvagraph-out/ lives).")
@click.option("--questions", "questions_file", default=None, type=click.Path(exists=True),
              help="JSON file with questions list. Uses built-in 80-question set if omitted.")
@click.option("--output", default=None, type=click.Path(),
              help="Output JSONL path (default: pruvagraph-out/benchmark_results.jsonl).")
@click.option("--backend", "-b", default="none",
              type=click.Choice(["none", "claude", "gemini", "openai", "ollama"]),
              help="LLM backend for query fallback (default: none = free).")
def benchmark_suite_cmd(root: str, questions_file: str | None, output: str | None, backend: str) -> None:
    """[Truth Machine] Run the full benchmark suite: graph queries vs naive file reads.

    Outputs a JSONL file with per-question token savings metrics. This is the
    reproducible benchmark harness that backs every savings % shown in the UI.

    \\b
    Examples:
        pruvagraph benchmark-suite                              # 80 built-in questions
        pruvagraph benchmark-suite --questions my_q.json       # custom question set
        pruvagraph benchmark-suite --output results.jsonl
    """
    from pruvagraph.benchmark_harness import (
        DEFAULT_QUESTIONS,
        BenchmarkResult,
        load_questions,
        run_benchmark_suite,
    )

    graph_json = Path(root) / "pruvagraph-out" / "graph.json"
    if not graph_json.exists():
        click.echo("No graph found. Run 'pruvagraph .' first.", err=True)
        sys.exit(1)

    questions: list[str]
    if questions_file:
        questions = load_questions(Path(questions_file))
        click.echo(f"Loaded {len(questions)} questions from {questions_file}")
    else:
        questions = DEFAULT_QUESTIONS
        click.echo(f"Using built-in {len(questions)}-question benchmark set.")

    out_path = Path(output) if output else Path(root) / "pruvagraph-out" / "benchmark_results.jsonl"
    click.echo(f"Running benchmark suite... (output: {out_path})")

    result = run_benchmark_suite(
        graph_json=graph_json,
        subject_dir=Path(root),
        questions=questions,
        output_path=out_path,
        backend=backend,
    )

    click.echo("\n" + result.summary())
    click.echo(f"\n✓ Results written to: {out_path}")
    click.echo("  Share this file alongside your README to make savings claims reproducible.")



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
# v1.6.0 — DriftGuard: validate-import subcommand
# ──────────────────────────────────────────────────────────────────────────────

@main.command("validate-import")
@click.argument("module")
@click.argument("symbol", required=False, default=None)
@click.option("--root", default=".", show_default=True,
              help="Root directory to validate imports against.")
def validate_import_cmd(module: str, symbol: str | None, root: str) -> None:
    """DriftGuard — validate that a module/symbol exists in this environment."""
    from pruvagraph.driftguard import validate_import

    result = validate_import(module, symbol, Path(root))

    if result.valid:
        ver = f" (v{result.actual_version})" if result.actual_version else ""
        sym_part = f".{symbol}" if symbol else ""
        click.echo(f"OK {module}{sym_part} -- valid{ver}")
    else:
        click.echo(f"INVALID {module}.{symbol or '*'}", err=True)
        if result.suggestion:
            click.echo(f"  -> {result.suggestion}", err=True)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# v1.7.0 — ContextLens: context-lens subcommand
# ──────────────────────────────────────────────────────────────────────────────

@main.command("context-lens")
@click.option("--root", default=".", show_default=True,
              help="Project root directory.")
@click.option("--last", default=10, show_default=True, type=int,
              help="Number of recent tool calls to show.")
def context_lens_cmd(root: str, last: int) -> None:
    """ContextLens -- show what's been injected into context this session."""
    from pruvagraph.context_lens import get_active_context, trace_last_tool_calls

    summary = get_active_context(root=root)
    trace = trace_last_tool_calls(root=root, n=last)

    click.echo(summary)
    click.echo("")
    click.echo(trace)



# ──────────────────────────────────────────────────────────────────────────────
# v1.8.0 — TaskWeaver: checkpoint / task-progress subcommands
# ──────────────────────────────────────────────────────────────────────────────

@main.command("checkpoint")
@click.option("--task", "task_id", required=True,
              help="Task label (e.g. 'implement-auth').")
@click.option("--description", "description", required=True,
              help="What was done at this step.")
@click.option("--files", "files", multiple=True, default=None,
              help="Files changed (may be repeated).")
@click.option("--root", default=".", show_default=True,
              help="Project root directory.")
def checkpoint_cmd(task_id: str, description: str, files: tuple, root: str) -> None:
    """TaskWeaver -- save an agent step checkpoint with optional git micro-commit."""
    from pruvagraph.task_weaver import create_checkpoint

    files_list = list(files) if files else None
    result = create_checkpoint(task_id, description, files_list, root=root)
    click.echo(result)


@main.command("task-progress")
@click.argument("task_id", required=False, default=None)
@click.option("--root", default=".", show_default=True,
              help="Project root directory.")
@click.option("--all", "all_tasks", is_flag=True, default=False,
              help="Show checkpoints for all tasks (ignores TASK_ID).")
@click.option("--format", "output_format", default="text",
              type=click.Choice(["text", "json"]), show_default=True,
              help="Output format: human-readable text or machine-readable JSON.")
def task_progress_cmd(task_id: str | None, root: str, all_tasks: bool,
                      output_format: str) -> None:
    """TaskWeaver -- show checkpoint DAG progress for a task.

    \b
    Examples:
      pruvagraph task-progress my-task
      pruvagraph task-progress --all
      pruvagraph task-progress --all --format json
    """
    import json as _json
    from pruvagraph.task_weaver import get_task_progress, list_checkpoints_json

    if output_format == "json":
        data = list_checkpoints_json(task_id=None if all_tasks else task_id, root=root)
        click.echo(_json.dumps(data, indent=2))
    else:
        if all_tasks:
            from pruvagraph.task_weaver import list_checkpoints
            click.echo(list_checkpoints(task_id=None, root=root))
        else:
            if task_id is None:
                raise click.UsageError("TASK_ID is required unless --all is used.")
            click.echo(get_task_progress(task_id, root=root))


# ──────────────────────────────────────────────────────────────────────────────
# v1.8.0 — BudgetGovernor: budget set / budget check subcommands
# ──────────────────────────────────────────────────────────────────────────────

@main.group("budget")
def budget_group() -> None:
    """BudgetGovernor -- manage per-session token budget."""


@budget_group.command("set")
@click.argument("tokens", type=int)
@click.option("--root", default=".", show_default=True,
              help="Project root directory.")
def budget_set_cmd(tokens: int, root: str) -> None:
    """Set the session token budget cap."""
    from pruvagraph.budget_governor import set_budget

    click.echo(set_budget(tokens, root=root))


@budget_group.command("check")
@click.option("--root", default=".", show_default=True,
              help="Project root directory.")
@click.option("--format", "output_format", default="text",
              type=click.Choice(["text", "json"]), show_default=True,
              help="Output format: human-readable text or machine-readable JSON.")
def budget_check_cmd(root: str, output_format: str) -> None:
    """Check remaining token budget and status for this session."""
    import json as _json
    from pruvagraph.budget_governor import check_budget, check_budget_json

    if output_format == "json":
        click.echo(_json.dumps(check_budget_json(root=root), indent=2))
    else:
        click.echo(check_budget(root=root))



# ──────────────────────────────────────────────────────────────────────────────
# v1.9.0 — RulesForge: rules subcommand
# ──────────────────────────────────────────────────────────────────────────────

@main.command("rules")
@click.argument("file_path")
@click.option("--root", default=".", show_default=True,
              help="Project root directory.")
@click.option("--learn", "learn_description", default=None,
              help="Learn a rule: provide a description and pipe a diff via stdin.")
def rules_cmd(file_path: str, root: str, learn_description: str | None) -> None:
    """RulesForge -- show context-aware AI coding rules for a file.

    Detects the file's architectural layer (api/ui/test/util/config) via
    AST analysis and returns layer-appropriate coding constraints.

    \b
    Examples:
      pruvagraph rules src/auth.py
      pruvagraph rules src/routes.py
      git diff HEAD | pruvagraph rules src/api.py --learn "Validate before saving"
    """
    if learn_description:
        import sys
        from pruvagraph.rules_forge import learn_from_accept

        diff = sys.stdin.read()
        result = learn_from_accept(diff, learn_description, root=root)
        click.echo(result)
    else:
        from pruvagraph.rules_forge import get_applicable_rules

        click.echo(get_applicable_rules(file_path, root=root))


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

"""
PruvaGraph MCP Server — Universal IDE integration.

Exposes PruvaGraph's knowledge graph as Model Context Protocol (MCP) tools,
making it accessible from any MCP-compatible IDE:
  - Claude Code  (claude mcp add pruvagraph ...)
  - VS Code      (via Cline, Continue, or Claude Dev extension)
  - Cursor       (.cursor/mcp.json)
  - Windsurf     (mcp_config.json)
  - Any LLM tool supporting MCP

Tools exposed:
  1. query_graph        — Natural language query over the codebase graph.
  2. get_dependencies   — Find all dependencies of a module/function.
  3. find_callers       — Who calls a given function?
  4. get_summary        — One-sentence summary of any node.
  5. list_communities   — Show architectural clusters/modules.
  6. cost_report        — Show LLM cost savings from last run.

Running the server:
    python -m pruvagraph.mcp_server            # stdio transport (Claude Code)
    python -m pruvagraph.mcp_server --http     # HTTP transport (VS Code / Cursor)

Installing:
    pruvagraph install --claude-code           # Writes ~/.claude/mcp_config.json
    pruvagraph install --cursor               # Writes .cursor/mcp.json
    pruvagraph install --vscode               # Writes .vscode/mcp.json

Requires: pip install mcp  (Model Context Protocol SDK, free, MIT license)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Gap 2 — session-level read tracker (in-process, lives for MCP server lifetime)
try:
    from pruvagraph import session_tracker as _st
    _SESSION_TRACKING = True
except ImportError:
    _SESSION_TRACKING = False

# ---------------------------------------------------------------------------
# MCP SDK (pip install mcp)
# ---------------------------------------------------------------------------
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequest,
        CallToolResult,
        ListToolsRequest,
        ListToolsResult,
        TextContent,
        Tool,
    )
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Graph loader (lazy, cached) — Arch1 streaming-aware
# ---------------------------------------------------------------------------

_graph_cache: dict[str, Any] = {}

def _load_graph(root: str = ".") -> tuple[Any, bool]:
    """
    Load best available networkx graph.
    Prefers full graph.json, falls back to graph_partial.json during streaming build.

    Returns (graph, is_partial). Returns (None, False) if no graph available.
    """
    out_dir = Path(root) / "pruvagraph-out"
    try:
        from pruvagraph.streaming import load_best_graph
        return load_best_graph(out_dir)
    except ImportError:
        pass

    # Fallback to direct load
    graph_path = out_dir / "graph.json"
    if not graph_path.exists():
        return None, False

    import networkx as nx
    G = nx.node_link_graph(json.loads(graph_path.read_text()))
    return G, False


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _query_graph(question: str, root: str = ".") -> str:
    """
    Query the graph using the full 5-tier cost pipeline (C1 fix).
    Replaces the old simple keyword search with the real query engine.
    """
    G, is_partial = _load_graph(root)
    if G is None:
        return "No graph found. Run 'pruvagraph .' first."

    prefix = ""
    if is_partial:
        try:
            from pruvagraph.streaming import get_build_status, partial_graph_note
            status = get_build_status(Path(root) / "pruvagraph-out")
            prefix = partial_graph_note(status.get("percent", 0))
        except Exception:
            pass

    # Use the full 5-tier pipeline from query.py (C1 fix)
    try:
        from pruvagraph.query import query
        out_dir = Path(root) / "pruvagraph-out"
        result = query(
            G,
            question,
            backend="none",
            out_dir=out_dir if out_dir.exists() else None,
        )
        return prefix + result
    except Exception as e:
        # Fallback: keyword search if query module fails
        q_lower = question.lower()
        matches = []
        for node_id, data in G.nodes(data=True):
            label   = str(data.get("label", "")).lower()
            summary = str(data.get("summary", "")).lower()
            if any(kw in label or kw in summary for kw in q_lower.split()):
                matches.append({
                    "id":      node_id,
                    "label":   data.get("label"),
                    "type":    data.get("type"),
                    "summary": data.get("summary"),
                    "file":    data.get("file"),
                })
        if not matches:
            return f"No nodes found matching: {question} (query engine error: {e})"
        lines = [f"Found {len(matches)} matching nodes:\n"]
        for m in matches[:10]:
            lines.append(f"• [{m['type']}] {m['label']} ({m['file']})\n  {m['summary']}")
        if len(matches) > 10:
            lines.append(f"\n... and {len(matches)-10} more.")
        return prefix + "\n".join(lines)


def _get_dependencies(node_id: str, root: str = ".") -> str:
    """Return all nodes that node_id imports/uses/calls."""
    # Gap 2: return terse back-reference if already served this session
    cache_key = f"deps::{node_id}"
    if _SESSION_TRACKING:
        ref = _st.already_seen(cache_key, tool="get_dependencies")
        if ref:
            return ref

    G, is_partial = _load_graph(root)
    if G is None:
        return "No graph found."

    if node_id not in G:
        return f"Node '{node_id}' not found in graph."

    deps = []
    for _, target, data in G.out_edges(node_id, data=True):
        target_data = G.nodes[target]
        deps.append({
            "relation": data.get("relation", "→"),
            "id":       target,
            "label":    target_data.get("label"),
            "summary":  target_data.get("summary", ""),
        })

    if not deps:
        return f"'{node_id}' has no outgoing dependencies."

    lines = [f"Dependencies of '{node_id}':\n"]
    for d in deps:
        lines.append(f"  {d['relation']} {d['label']} — {d['summary']}")
    ans = "\n".join(lines)
    if is_partial:
        ans = "[PARTIAL GRAPH - Build still running]\n" + ans

    if _SESSION_TRACKING:
        _st.record_seen(cache_key, tool="get_dependencies")
    return ans


def _find_callers(node_id: str, root: str = ".") -> str:
    """Return all nodes that call/import node_id."""
    # Gap 2: return terse back-reference if already served this session
    cache_key = f"callers::{node_id}"
    if _SESSION_TRACKING:
        ref = _st.already_seen(cache_key, tool="find_callers")
        if ref:
            return ref

    G, is_partial = _load_graph(root)
    if G is None:
        return "No graph found."

    if node_id not in G:
        return f"Node '{node_id}' not found in graph."

    callers = []
    for source, _, data in G.in_edges(node_id, data=True):
        source_data = G.nodes[source]
        callers.append({
            "relation": data.get("relation", "→"),
            "id":       source,
            "label":    source_data.get("label"),
            "file":     source_data.get("file", ""),
        })

    if not callers:
        return f"No callers found for '{node_id}'."

    lines = [f"Callers of '{node_id}':\n"]
    for c in callers:
        lines.append(f"  {c['label']} ({c['file']}) via {c['relation']}")
    ans = "\n".join(lines)
    if is_partial:
        ans = "[PARTIAL GRAPH - Build still running]\n" + ans

    if _SESSION_TRACKING:
        _st.record_seen(cache_key, tool="find_callers")
    return ans


def _get_summary(node_id: str, root: str = ".") -> str:
    """Get one-sentence summary and metadata for a node."""
    # Gap 2: return terse back-reference if already served this session
    if _SESSION_TRACKING:
        ref = _st.already_seen(node_id, tool="get_summary")
        if ref:
            return ref

    G, is_partial = _load_graph(root)
    if G is None:
        return "No graph found."

    # Fuzzy match by label if exact ID not found
    target = None
    if node_id in G:
        target = node_id
    else:
        for n, d in G.nodes(data=True):
            if d.get("label", "").lower() == node_id.lower():
                target = n
                break

    if target is None:
        return f"Node '{node_id}' not found."

    data = G.nodes[target]
    ans = (
        f"Node: {data.get('label')}\n"
        f"Type: {data.get('type')}\n"
        f"File: {data.get('file')}\n"
        f"Summary: {data.get('summary', 'No summary available.')}\n"
        f"Community: {data.get('community', 'N/A')}"
    )
    if is_partial:
        ans = "[PARTIAL GRAPH - Build still running]\n" + ans

    # Gap 2: record this node as served
    if _SESSION_TRACKING:
        _st.record_seen(node_id, tool="get_summary")
    return ans


def _list_communities(root: str = ".") -> str:
    """List detected architectural communities/modules."""
    G, is_partial = _load_graph(root)
    if G is None:
        return "No graph found."

    communities: dict[int, list[str]] = {}
    for node_id, data in G.nodes(data=True):
        c = data.get("community")
        if c is None:
            continue
        communities.setdefault(c, []).append(data.get("label", node_id))

    if not communities:
        return "No communities detected. Run graph build first."

    lines = [f"Detected {len(communities)} communities:\n"]
    for cid, members in sorted(communities.items()):
        sample = ", ".join(members[:5])
        more   = f" (+{len(members)-5} more)" if len(members) > 5 else ""
        lines.append(f"Community {cid} ({len(members)} nodes): {sample}{more}")
    ans = "\n".join(lines)
    if is_partial:
        ans = "[PARTIAL GRAPH - Build still running]\n" + ans
    return ans


def _get_cost_report(root: str = ".") -> str:
    """Return the cost report from the last run."""
    report_path = Path(root) / "pruvagraph-out" / "cost_report.json"
    if not report_path.exists():
        return "No cost report found. Run 'pruvagraph .' first."

    data = json.loads(report_path.read_text())
    return (
        f"PruvaGraph Cost Report\n"
        f"{'─'*40}\n"
        f"Files processed: {data.get('total_files_processed', 0):,}\n"
        f"Cache hits:      {data.get('cache_hits', 0):,}\n"
        f"Dedup projected: {data.get('dedup_projected', 0):,}\n"
        f"LLM calls made:  {data.get('llm_calls_made', 0):,}\n"
        f"Actual cost:     ${data.get('actual_cost_usd', 0):.6f}\n"
        f"Naive cost:      ${data.get('naive_cost_usd', 0):.4f}\n"
        f"Cost saved:      ${data.get('cost_saved_usd', 0):.4f} ({data.get('savings_pct', 0):.1f}%)\n"
        f"Run time:        {data.get('run_duration_seconds', 0):.1f}s"
    )


# ---------------------------------------------------------------------------
# D1: Graph Diff tool
# ---------------------------------------------------------------------------

def _get_graph_diff(root: str = ".") -> str:
    """Return last_diff.json contents as a formatted string."""
    from pruvagraph.graph_diff import load_diff
    out_dir = Path(root) / "pruvagraph-out"
    diff = load_diff(out_dir)
    if diff is None:
        return (
            "No diff available. The graph diff is generated automatically after each build.\n"
            "Run 'pruvagraph .' at least twice to see changes."
        )
    return diff.format()


# ---------------------------------------------------------------------------
# D2: Impact Analyzer tool
# ---------------------------------------------------------------------------

def _analyze_impact(node_id: str, root: str = ".", depth: int = 3) -> str:
    """Run impact analysis for a symbol — what breaks if it changes?"""
    out_dir    = Path(root) / "pruvagraph-out"
    graph_path = out_dir / "graph.json"
    if not graph_path.exists():
        return "No graph found. Run 'pruvagraph .' first."

    try:
        import networkx as nx
        G = nx.node_link_graph(json.loads(graph_path.read_text(encoding="utf-8")))
    except Exception as e:
        return f"Failed to load graph: {e}"

    # Load git intel if available
    git_intel = None
    try:
        from pruvagraph.git_intel import extract_git_intelligence
        intel = extract_git_intelligence(Path(root))
        if intel.get("available"):
            git_intel = intel
    except Exception:
        pass

    from pruvagraph.impact_analyzer import analyze_impact
    report = analyze_impact(G, node_id, depth=depth, git_intel=git_intel)
    return report.format("table")


# ---------------------------------------------------------------------------
# M1: List Packages tool
# ---------------------------------------------------------------------------

def _list_packages(root: str = ".") -> str:
    """Detect monorepo layout and list packages + cross-package edges."""
    from pruvagraph.monorepo import detect_monorepo, find_cross_package_edges
    layout = detect_monorepo(Path(root))
    if layout is None:
        return (
            f"'{root}' is not a detected monorepo.\n"
            "Supported: pnpm, Nx, Lerna, Turborepo, Rush, npm workspaces, Python, generic."
        )

    lines = [layout.summary(), ""]
    for pkg in layout.packages:
        lines.append(f"  • {pkg.name:<30}  {pkg.language:<12}  {pkg.root}")

    # Cross-package edges
    cross = find_cross_package_edges(layout.packages)
    if cross:
        lines.append(f"\nCross-package imports ({len(cross)}):")
        for src, tgt, rel in cross[:20]:
            lines.append(f"  {src} → {tgt}")
        if len(cross) > 20:
            lines.append(f"  ... and {len(cross) - 20} more")
    else:
        lines.append("\nNo cross-package imports detected.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Server
# -------------------------------------------# D1 fix: All descriptions rewritten with "CALL THIS FIRST" pattern so
# Claude Code prioritises graph tools over built-in file-read tools.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "query_graph",
        "description": (
            "CALL THIS FIRST before reading any source file, running grep, or using "
            "list_directory for any question about codebase structure, architecture, or "
            "dependencies. Answers natural language questions using a pre-built knowledge "
            "graph — 5×–71× cheaper in tokens than reading raw files. Fully offline, zero "
            "API cost. Examples: 'how does auth connect to the database?', "
            "'what modules does UserService depend on?', "
            "'where is payment processing handled?', "
            "'which files import the logger?'"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Natural language question about the codebase"},
                "root":     {"type": "string", "description": "Project root directory (default: .)"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_dependencies",
        "description": (
            "CALL THIS FIRST when asked what a module, class, or function imports or depends on. "
            "Returns the complete dependency graph from the pre-built knowledge graph — "
            "no file reads needed. Pass the node ID (e.g. 'auth.session.SessionManager') "
            "or a label. Always faster and cheaper than opening the file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node ID or label (e.g. 'auth.session.SessionManager')"},
                "root":    {"type": "string", "description": "Project root directory (default: .)"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "find_callers",
        "description": (
            "CALL THIS FIRST when asked 'who calls X?', 'where is X used?', or "
            "'which files import Y?'. Returns all callers and importers of a function "
            "or class from the knowledge graph — much cheaper than grep across the whole "
            "codebase. Works on function names, class names, and node IDs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node ID, function name, or class name"},
                "root":    {"type": "string", "description": "Project root directory (default: .)"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "get_summary",
        "description": (
            "CALL THIS FIRST when asked what a class, function, or file does. "
            "Returns a one-sentence summary + type + file location + community cluster "
            "from the knowledge graph. Zero file reads needed. "
            "Supports fuzzy matching — partial names and labels work."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node ID, label, or partial name (fuzzy matching)"},
                "root":    {"type": "string", "description": "Project root directory (default: .)"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "list_communities",
        "description": (
            "CALL THIS FIRST for architectural overview questions like 'what are the main modules?', "
            "'show me the high-level structure', or 'what does this codebase do?'. "
            "Lists all detected architectural clusters (communities) with member counts and "
            "representative symbols. Zero file reads."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Project root directory (default: .)"},
            },
        },
    },
    {
        "name": "cost_report",
        "description": (
            "Show the LLM cost analytics from the last pruvagraph build: files processed, "
            "cache hits, dedup savings, actual cost vs naive cost, and percentage saved. "
            "Also shows per-query token benchmarks if benchmark_mode was used."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Project root directory (default: .)"},
            },
        },
    },
    {
        "name": "get_graph_diff",
        "description": (
            "CALL THIS when asked 'what changed?', 'what’s new since last build?', or "
            "before starting a PR review. Shows added/removed/changed nodes and edges "
            "since the last 'pruvagraph .' run. Gives structural change context without "
            "reading individual files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Project root directory (default: .)"},
            },
        },
    },
    {
        "name": "analyze_impact",
        "description": (
            "CALL THIS BEFORE making any change to a symbol, function, class, or file. "
            "Returns a risk-sorted list of all nodes that would be affected if this symbol "
            "changes — the blast radius. Use this to understand what might break without "
            "manually tracing every dependency chain."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "Symbol name, class, file path, or node ID. Fuzzy matching — partial names work.",
                },
                "root":  {"type": "string", "description": "Project root directory (default: .)"},
                "depth": {
                    "type": "integer",
                    "description": "BFS depth limit (default 3). Higher = more transitive dependents.",
                    "default": 3,
                },
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "list_packages",
        "description": (
            "CALL THIS FIRST for monorepo questions: 'what packages are in this repo?', "
            "'which packages depend on each other?'. Detects monorepo layout (pnpm, Nx, "
            "Lerna, Turborepo, Rush, npm workspaces, Python, generic) and lists all "
            "sub-packages with cross-package import edges. No file reads needed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Monorepo root directory (default: .)"},
            },
        },
    },
]


TOOL_HANDLERS = {
    "query_graph":      lambda args: _query_graph(args["question"], args.get("root", ".")),
    "get_dependencies": lambda args: _get_dependencies(args["node_id"], args.get("root", ".")),
    "find_callers":     lambda args: _find_callers(args["node_id"], args.get("root", ".")),
    "get_summary":      lambda args: _get_summary(args["node_id"], args.get("root", ".")),
    "list_communities": lambda args: _list_communities(args.get("root", ".")),
    "cost_report":      lambda args: _get_cost_report(args.get("root", ".")),
    # v1.3.0
    "get_graph_diff":   lambda args: _get_graph_diff(args.get("root", ".")),
    "analyze_impact":   lambda args: _analyze_impact(
                            args["node_id"],
                            args.get("root", "."),
                            int(args.get("depth", 3)),
                        ),
    "list_packages":    lambda args: _list_packages(args.get("root", ".")),
}


async def run_stdio_server() -> None:
    """Run MCP server over stdio (for Claude Code and most IDE integrations)."""
    if not _MCP_AVAILABLE:
        print("Error: 'mcp' package not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

    server = Server("pruvagraph")

    @server.list_tools()
    async def handle_list_tools(req: ListToolsRequest) -> ListToolsResult:
        return ListToolsResult(tools=[Tool(**t) for t in TOOLS])

    @server.call_tool()
    async def handle_call_tool(req: CallToolRequest) -> CallToolResult:
        handler = TOOL_HANDLERS.get(req.params.name)
        if handler is None:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {req.params.name}")]
            )
        # Gap 2: tick the session turn counter on every MCP tool invocation
        if _SESSION_TRACKING:
            _st.tick()
        try:
            args = req.params.arguments or {}
            result = handler(args)
            return CallToolResult(content=[TextContent(type="text", text=result)])
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {e}")]
            )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name="pruvagraph",
                server_version="1.4.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


def write_ide_configs(root: Path = Path(".")) -> dict[str, Path]:
    """
    Write MCP config files for all major IDEs.

    Returns:
        Dict of {ide_name: config_path} for all files written.
    """
    # Find the pruvagraph executable
    import shutil
    exe = shutil.which("pruvagraph") or "python -m pruvagraph.mcp_server"
    server_cmd = [exe, "mcp-serve"] if shutil.which("pruvagraph") else ["python", "-m", "pruvagraph.mcp_server"]

    mcp_config = {
        "mcpServers": {
            "pruvagraph": {
                "command": server_cmd[0],
                "args": server_cmd[1:],
                "env": {},
                "description": "PruvaGraph knowledge graph — query your codebase",
            }
        }
    }

    written: dict[str, Path] = {}

    # Claude Code: ~/.claude/mcp_config.json
    claude_config = Path.home() / ".claude" / "mcp_config.json"
    _merge_json(claude_config, mcp_config)
    written["Claude Code"] = claude_config

    # Cursor: <project>/.cursor/mcp.json
    cursor_config = root / ".cursor" / "mcp.json"
    cursor_config.parent.mkdir(parents=True, exist_ok=True)
    _merge_json(cursor_config, mcp_config)
    written["Cursor"] = cursor_config

    # VS Code / Windsurf: <project>/.vscode/mcp.json
    vscode_config = root / ".vscode" / "mcp.json"
    vscode_config.parent.mkdir(parents=True, exist_ok=True)
    _merge_json(vscode_config, mcp_config)
    written["VS Code"] = vscode_config

    # CLAUDE.md: instructions for Claude Code context window
    claude_md = root / "CLAUDE.md"
    _write_claude_md(claude_md)
    written["CLAUDE.md"] = claude_md

    return written


def _merge_json(path: Path, new_data: dict) -> None:
    """Merge new_data into existing JSON file (or create it)."""
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except Exception:
            pass
    merged = {**existing}
    for k, v in new_data.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2))


def _write_claude_md(path: Path) -> None:
    content = """\
# PruvaGraph — Codebase Knowledge Graph

This project uses PruvaGraph to maintain a knowledge graph of the codebase.

## Available MCP Tools (v1.3.0 — 9 tools)

| Tool              | Usage                                              |
|-------------------|----------------------------------------------------|
| `query_graph`     | Ask anything about the codebase in natural language |
| `get_dependencies`| Find what a module/function depends on              |
| `find_callers`    | Find who calls a function                           |
| `get_summary`     | Get a one-sentence summary of any node              |
| `list_communities`| See architectural module groupings                  |
| `cost_report`     | View LLM cost savings from last build               |
| `get_graph_diff`  | What changed since last build? (D1)                 |
| `analyze_impact`  | What breaks if X changes? Risk-sorted list (D2)     |
| `list_packages`   | Monorepo: list packages + cross-package edges (M1)  |

## Rebuilding the Graph

```bash
pruvagraph .              # full rebuild
pruvagraph . --update     # incremental (changed files only)
pruvagraph . --dry-run    # estimate cost first
pruvagraph . --monorepo   # monorepo: build per-package graphs
```

## Diff & Impact

```bash
pruvagraph diff                     # what changed since last build?
pruvagraph impact SessionManager   # what breaks if SessionManager changes?
pruvagraph impact auth.py --depth 4
```

## Graph Location
Output: `pruvagraph-out/`
  - `graph.json`        — full knowledge graph
  - `last_diff.json`    — delta from last build (D1)
  - `cost_report.json`  — cost analytics
  - `GRAPH_REPORT.md`   — architectural summary
  - `graph.html`        — interactive visualisation
"""
    if not path.exists():
        path.write_text(content)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_server() -> None:
    """
    Public entry point for the `pruvagraph serve` CLI subcommand.

    Used by: `claude mcp add --transport stdio pruvagraph -- pruvagraph serve`
    """
    import asyncio
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_stdio_server())

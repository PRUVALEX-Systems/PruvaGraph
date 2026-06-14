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

# ---------------------------------------------------------------------------
# MCP SDK (pip install mcp)
# ---------------------------------------------------------------------------
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool, TextContent, CallToolRequest, CallToolResult,
        ListToolsRequest, ListToolsResult,
    )
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Graph loader (lazy, cached)
# ---------------------------------------------------------------------------

_graph_cache: dict[str, Any] = {}

def _load_graph(root: str = ".") -> Any:
    """Load networkx graph from pruvagraph-out/graph.json."""
    key = str(Path(root).resolve())
    if key in _graph_cache:
        return _graph_cache[key]

    graph_path = Path(root) / "pruvagraph-out" / "graph.json"
    if not graph_path.exists():
        return None

    import networkx as nx
    G = nx.node_link_graph(json.loads(graph_path.read_text()))
    _graph_cache[key] = G
    return G


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _query_graph(question: str, root: str = ".") -> str:
    """Query the graph in natural language."""
    G = _load_graph(root)
    if G is None:
        return "No graph found. Run 'pruvagraph .' first."

    # Simple keyword search over node summaries + labels
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
        return f"No nodes found matching: {question}"

    lines = [f"Found {len(matches)} matching nodes:\n"]
    for m in matches[:10]:
        lines.append(f"• [{m['type']}] {m['label']} ({m['file']})\n  {m['summary']}")
    if len(matches) > 10:
        lines.append(f"\n... and {len(matches)-10} more.")
    return "\n".join(lines)


def _get_dependencies(node_id: str, root: str = ".") -> str:
    """Return all nodes that node_id imports/uses/calls."""
    G = _load_graph(root)
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
    return "\n".join(lines)


def _find_callers(node_id: str, root: str = ".") -> str:
    """Return all nodes that call/import node_id."""
    G = _load_graph(root)
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
    return "\n".join(lines)


def _get_summary(node_id: str, root: str = ".") -> str:
    """Get one-sentence summary and metadata for a node."""
    G = _load_graph(root)
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
    return (
        f"Node: {data.get('label')}\n"
        f"Type: {data.get('type')}\n"
        f"File: {data.get('file')}\n"
        f"Summary: {data.get('summary', 'No summary available.')}\n"
        f"Community: {data.get('community', 'N/A')}"
    )


def _list_communities(root: str = ".") -> str:
    """List detected architectural communities/modules."""
    G = _load_graph(root)
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
    return "\n".join(lines)


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
# MCP Server
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "query_graph",
        "description": "Query the PruvaGraph knowledge graph in natural language. Ask about connections, modules, classes, functions.",
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
        "description": "Get all dependencies (imports, calls, uses) of a module, class, or function.",
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
        "description": "Find all code that calls or imports a given function/class.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node ID or label"},
                "root":    {"type": "string", "description": "Project root directory (default: .)"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "get_summary",
        "description": "Get a one-sentence summary and metadata for any node in the graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node ID or label"},
                "root":    {"type": "string", "description": "Project root directory (default: .)"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "list_communities",
        "description": "List all detected architectural communities/modules in the codebase.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Project root directory (default: .)"},
            },
        },
    },
    {
        "name": "cost_report",
        "description": "Show the LLM cost report from the last pruvagraph build — how much was saved.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Project root directory (default: .)"},
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
                server_version="1.0.0",
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

## Available MCP Tools

| Tool              | Usage                                              |
|-------------------|----------------------------------------------------|
| `query_graph`     | Ask anything about the codebase in natural language |
| `get_dependencies`| Find what a module/function depends on              |
| `find_callers`    | Find who calls a function                           |
| `get_summary`     | Get a one-sentence summary of any node              |
| `list_communities`| See architectural module groupings                  |
| `cost_report`     | View LLM cost savings from last build               |

## Rebuilding the Graph

```bash
pruvagraph .              # full rebuild
pruvagraph . --update     # incremental (changed files only)
pruvagraph . --dry-run    # estimate cost first
```

## Graph Location
Output: `pruvagraph-out/`
  - `graph.json`       — full knowledge graph
  - `cost_report.json` — cost analytics
  - `GRAPH_REPORT.md`  — architectural summary
  - `graph.html`       — interactive visualisation
"""
    if not path.exists():
        path.write_text(content)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(description="PruvaGraph MCP Server")
    parser.add_argument("--http", action="store_true", help="Run HTTP server instead of stdio")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()

    asyncio.run(run_stdio_server())

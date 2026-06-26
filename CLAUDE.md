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

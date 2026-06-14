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

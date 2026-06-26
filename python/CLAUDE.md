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

<!-- pruvagraph:preinjection:start -->
## Auto-Injected Context (PruvaGraph Arch5 — regenerated on every build, do not edit by hand)

_Graph: **808 nodes · 1,242 edges · 40 architectural communities**.  Top 65 highest-connectivity nodes + one representative per community below — loads at session start, no tool call needed._

### Landmarks (highest-connectivity nodes)

- **__future__** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/analyze.py` (external, degree 80) — External package: __future__ [git: 1 commits, has bug fixes, recently changed]
- **pathlib** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/ast_diff.py` (external, degree 67) — External package: pathlib [git: 1 commits, recently changed]
- **json** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/benchmark.py` (external, degree 49) — External package: json [git: 3 commits, has bug fixes, recently changed]
- **test_privacy_adversarial** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_privacy_adversarial.py` (module, degree 38) — python module: test_privacy_adversarial [git: 2 commits, recently changed]
- **mcp_server** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/mcp_server.py` (module, degree 37) — python module: mcp_server [git: 8 commits, has bug fixes, recently changed]
- **test_mcp_server** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_mcp_server.py` (module, degree 37) — python module: test_mcp_server [git: 1 commits, recently changed]
- **cli** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/cli.py` (module, degree 37) — python module: cli [git: 15 commits, has bug fixes, recently changed]
- **typing** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/analyze.py` (external, degree 30) — External package: typing [git: 1 commits, has bug fixes, recently changed]
- **pipeline** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/pipeline.py` (module, degree 26 ⚑ high-risk) — python module: pipeline [git: 17 commits, has bug fixes, recently changed]
- **monorepo** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/monorepo.py` (module, degree 25) — python module: monorepo [git: 3 commits, has bug fixes, recently changed]
- **networkx** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/analyze.py` (external, degree 22) — External package: networkx [git: 1 commits, has bug fixes, recently changed]
- **query** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/query.py` (module, degree 22) — python module: query [git: 8 commits, has bug fixes, recently changed]
- **installer** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/installer.py` (module, degree 21) — python module: installer [git: 6 commits, has bug fixes, recently changed]
- **compress** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/compress.py` (module, degree 20) — python module: compress [git: 2 commits, has bug fixes, recently changed]
- **re** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/ast_diff.py` (external, degree 19) — External package: re [git: 1 commits, recently changed]
- **test_monorepo** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_monorepo.py` (module, degree 19) — python module: test_monorepo [git: 1 commits, recently changed]
- **test_pipeline_core** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_pipeline_core.py` (module, degree 19) — python module: test_pipeline_core [git: 1 commits, recently changed]
- **task_weaver** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/task_weaver.py` (module, degree 18) — python module: task_weaver [git: 1 commits, recently changed]
- **dataclasses** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/benchmark_harness.py` (external, degree 17) — External package: dataclasses [git: 1 commits, recently changed]
- **budget_governor** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/budget_governor.py` (module, degree 17) — python module: budget_governor [git: 1 commits, recently changed]
- **deterministic_router** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/deterministic_router.py` (module, degree 17) — python module: deterministic_router [git: 1 commits, recently changed]
- **docstring_extractor** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/docstring_extractor.py` (module, degree 17) — python module: docstring_extractor [git: 1 commits, recently changed]
- **pytest** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/conftest.py` (external, degree 17) — External package: pytest [git: 2 commits, recently changed]
- **config_parser** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/config_parser.py` (module, degree 16) — python module: config_parser [git: 1 commits, recently changed]
- **llm_extract** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/llm_extract.py` (module, degree 16) — python module: llm_extract [git: 3 commits, has bug fixes, recently changed]
- **router** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/router.py` (module, degree 16) — python module: router [git: 4 commits, has bug fixes, recently changed]
- **test_graph_diff** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_graph_diff.py` (module, degree 16) — python module: test_graph_diff [git: 1 commits, recently changed]
- **test_task_weaver** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_task_weaver.py` (module, degree 16) — python module: test_task_weaver [git: 1 commits, recently changed]
- **time** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/benchmark_harness.py` (external, degree 15) — External package: time [git: 1 commits, recently changed]
- **cache** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/cache.py` (module, degree 15) — python module: cache [git: 2 commits, has bug fixes, recently changed]
- **dedup** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/dedup.py` (module, degree 15) — python module: dedup [git: 2 commits, has bug fixes, recently changed]
- **schema_parser** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/schema_parser.py` (module, degree 15) — python module: schema_parser [git: 1 commits, recently changed]
- **type_harvester** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/type_harvester.py` (module, degree 15) — python module: type_harvester [git: 1 commits, recently changed]
- **test_preinjection** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_preinjection.py` (module, degree 15) — python module: test_preinjection [git: 1 commits, recently changed]
- **benchmark_harness** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/benchmark_harness.py` (module, degree 14) — python module: benchmark_harness [git: 1 commits, recently changed]
- **test_impact_analyzer** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_impact_analyzer.py` (module, degree 14) — python module: test_impact_analyzer [git: 1 commits, recently changed]
- **hierarchy** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/hierarchy.py` (module, degree 13) — python module: hierarchy [git: 1 commits, recently changed]
- **hooks** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/hooks.py` (module, degree 13) — python module: hooks [git: 3 commits, has bug fixes, recently changed]
- **free_doc_parser** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/free_doc_parser.py` (module, degree 12) — python module: free_doc_parser [git: 1 commits, recently changed]
- **test_dead_layers** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_dead_layers.py` (module, degree 12) — python module: test_dead_layers [git: 1 commits, has bug fixes, recently changed]
- **embedder** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/embedder.py` (module, degree 11) — python module: embedder [git: 2 commits, recently changed]
- **click** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/cli.py` (external, degree 11) — External package: click [git: 15 commits, has bug fixes, recently changed]
- **subgraph** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/subgraph.py` (module, degree 10) — python module: subgraph [git: 4 commits, has bug fixes, recently changed]
- **batch** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/batch.py` (module, degree 10) — python module: batch [git: 3 commits, has bug fixes, recently changed]
- **test_package** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_package.py` (module, degree 8) — python module: test_package [git: 3 commits, recently changed]
- **README** `C:\Users\affan\Downloads\PRUVALEX Graph optimise LLM cost tool\python\README.md` (doc, degree 8 ⚑ high-risk) — <div align="center"> [git: 21 commits, has bug fixes, recently changed]
- **shutil** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/installer.py` (external, degree 7) — External package: shutil [git: 6 commits, has bug fixes, recently changed]
- **prewarm** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/prewarm.py` (module, degree 7) — python module: prewarm [git: 2 commits, has bug fixes, recently changed]
- **test_build** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_build.py` (module, degree 6) — python module: test_build [git: 1 commits, recently changed]
- **test_detect** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_detect.py` (module, degree 6) — python module: test_detect [git: 1 commits, recently changed]
- **test_deterministic_router** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_deterministic_router.py` (module, degree 6) — python module: test_deterministic_router [git: 1 commits, recently changed]
- **test_prewarm** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_prewarm.py` (module, degree 6) — python module: test_prewarm [git: 1 commits, recently changed]
- **_rich_print** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/monorepo.py` (function, degree 5) — python function in monorepo [git: 3 commits, has bug fixes, recently changed]
- **PruvaGraph — Codebase Knowledge Graph** `C:\Users\affan\Downloads\PRUVALEX Graph optimise LLM cost tool\python\CLAUDE.md` (concept, degree 5) — Section: PruvaGraph — Codebase Knowledge Graph [git: 3 commits, has bug fixes, recently changed]
- **run_server** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/mcp_server.py` (function, degree 4) — python function in mcp_server [git: 8 commits, has bug fixes, recently changed]
- **math** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/query.py` (external, degree 4) — External package: math [git: 8 commits, has bug fixes, recently changed]
- **CompressionResult** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/compress.py` (class, degree 2) — python class in compress [git: 2 commits, has bug fixes, recently changed]
- **parse_config_file** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/config_parser.py` (function, degree 2) — python function in config_parser [git: 1 commits, recently changed]
- **_register** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/deterministic_router.py` (function, degree 2) — python function in deterministic_router [git: 1 commits, recently changed]
- **extract_docstrings** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/docstring_extractor.py` (function, degree 2) — python function in docstring_extractor [git: 1 commits, recently changed]
- **extract_doc_batch** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pruvagraph/llm_extract.py` (function, degree 2) — python function in llm_extract [git: 3 commits, has bug fixes, recently changed]
- **TestSingleRepo** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_monorepo.py` (class, degree 2) — python class in test_monorepo [git: 1 commits, recently changed]
- **TestOpenAIKey** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/tests/test_privacy_adversarial.py` (class, degree 2) — python class in test_privacy_adversarial [git: 2 commits, recently changed]
- **mcp** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/.vscode/mcp.json` (module, degree 1) — json module: mcp
- **pyproject** `C:/Users/affan/Downloads/PRUVALEX Graph optimise LLM cost tool/python/pyproject.toml` (module, degree 1) — toml module: pyproject [git: 10 commits, has bug fixes, recently changed]

<!-- pruvagraph:preinjection:end -->

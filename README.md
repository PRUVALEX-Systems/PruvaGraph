# PRUVALEX PruvaGraph

> **Turn your codebase into a knowledge graph. Save 70–82% on LLM tokens. Keep code private.**

[![Version](https://img.shields.io/badge/version-1.9.1-teal.svg)](https://github.com/PRUVALEX-Systems/PruvaGraph)
[![VS Code](https://img.shields.io/badge/VS%20Code-%5E1.85-blue.svg)](https://marketplace.visualstudio.com/)
[![Tests](https://img.shields.io/badge/tests-508%20passed-brightgreen.svg)](#test-coverage)
[![Coverage](https://img.shields.io/badge/coverage-JS%20%7C%20Python-yellow.svg)](#test-coverage)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Benchmark](https://img.shields.io/badge/savings-81.5%25%20on%20pallets%2Fclick-orange.svg)](#benchmark)
[![WCAG](https://img.shields.io/badge/accessibility-WCAG%202.1%20AA-purple.svg)](#accessibility)

PruvaGraph builds a compact knowledge graph of your codebase and exposes it to AI agents
(Claude Code, Cursor, VS Code Copilot) via the **Model Context Protocol (MCP)**.
Instead of feeding entire files to the LLM, agents query the graph — answering the same
questions with **70–82% fewer tokens** and **zero code leaving your machine**.

---

## Quick Start

### 1 — Install the VS Code Extension

**From VSIX (v1.9.1):**
```bash
code --install-extension pruvalex-pruvagraph-1.9.1.vsix
```

Or search `"PRUVALEX PruvaGraph"` in the VS Code Extensions marketplace.

### 2 — Build a Graph

Open any Python project in VS Code, then open a terminal:
```bash
pip install pruvalex-pruvagraph   # or: pip install -e ./python
pruvagraph .                      # builds graph.json in pruvagraph-out/
```

### 3 — Wire to Your AI Agent

```bash
pruvagraph install --vscode        # writes .vscode/mcp.json (VS Code / Copilot)
pruvagraph install --claude        # writes CLAUDE.md + .mcp.json (Claude Code)
pruvagraph install --cursor        # writes .cursor/mcp.json
```

Reload your IDE. Your agent now has 23 MCP tools to query the graph.

---

## Benchmark — Real Numbers

> These numbers come from the reproducible benchmark harness (`pruvagraph benchmark-suite`).
> No hardcoded values. Run it yourself: `pruvagraph benchmark-suite --root .`

| Repo | Questions | Graph tokens (avg) | Raw tokens (avg) | **Savings** |
|------|----------:|------------------:|-----------------:|------------:|
| This repo (PruvaGraph) | 84/84 | 450 | 3,884 | **70.5%** |
| `pallets/click` (external) | 84/84 | 314 | 4,978 | **81.5%** |

Both runs use `--backend none` (no LLM API calls billed). Savings come from graph
traversal, deterministic routing, and exact-match caching — not from approximation.

> **Known limitation — banner numbers are point-in-time snapshots.**
> The `70.5%–81.5%` figures shown in the CLI banner (`LOGO` in `cli.py:60`) and
> in this README tagline are hardcoded strings from the v1.9.1 benchmark run.
> They follow the same pattern as the stale `31.6%` bug fixed in v1.9.0
> (see CHANGELOG §Fixed — 31.6% Stale Hardcoded Savings Claim).
> After any future benchmark rerun that produces meaningfully different numbers,
> these two locations must be updated manually:
> 1. `python/pruvagraph/cli.py` — the `LOGO` constant (line ~60) and the
>    `UnicodeEncodeError` fallback echo string (line ~129)
> 2. `README.md` — the tagline and the Benchmark table header
> Run `pruvagraph benchmark-suite --root .` to get fresh numbers.

**Reproduce on your repo:**
```bash
pruvagraph benchmark-suite --root /path/to/your/project
# → pruvagraph-out/benchmark_results.jsonl
```

---

## Features

### Core: Knowledge Graph Engine
- Parses Python codebases with Tree-sitter (no LSP, no internet)
- Builds a directed graph: modules → functions → imports → calls
- 23 MCP tools for graph queries (dependencies, callers, summaries, communities)
- Incremental updates: `pruvagraph . --update` (only changed files)
- Graph export: JSON, GEXF, GraphML, interactive HTML

### 5 Integrated Modules (toggleable)

| Module | What it does | MCP Tools |
|--------|-------------|-----------|
| **DriftGuard** | Validates imports/types before agent edits land | `validate_import`, `check_type_compat` |
| **ContextLens** | Tracks what has been injected into agent context | `get_active_context`, `measure_token_usage` |
| **TaskWeaver** | Saves agent checkpoints with git SHA + rollback | `create_checkpoint`, `rollback_to_checkpoint` |
| **BudgetGovernor** | Per-session token budget cap with auto-tracking | `check_budget` |
| **RulesForge** | Context-aware coding rules for the open file | `get_applicable_rules` |

Toggle any module off in VS Code Settings → `pruvagraph.modules.*` → **the MCP server
automatically removes its tools from the client's tool list on next startup.**

### Analytics Dashboard (VS Code)

Open with `Ctrl+Shift+P → PruvaGraph: Open Analytics Dashboard`:

| Tab | Shows |
|-----|-------|
| 📈 Cost Dashboard | Avg savings %, top-8 bar chart, benchmark truth machine |
| ◵ Tier Map | SVG donut: % of queries handled by Tier 0–3 |
| ⏱ Agent Timeline | TaskWeaver checkpoint DAG per task |
| 💴 Budget Meter | SVG arc gauge: token spend vs cap |

---

## Configuration

Add to your `settings.json` (or configure via VS Code Settings UI):

```json
{
  "pruvagraph.modules.driftguard.enabled": true,
  "pruvagraph.modules.contextlens.enabled": true,
  "pruvagraph.modules.taskweaver.enabled": true,
  "pruvagraph.modules.budgetgovernor.enabled": true,
  "pruvagraph.modules.rulesforge.enabled": true
}
```

When a module is toggled off, the extension automatically rewrites `.vscode/mcp.json`
with `PRUVAGRAPH_DISABLED_MODULES=<list>`. The next MCP server startup hides those tools
from the agent — no silent no-ops.

---

## MCP Tools Reference

Exactly 23 tools — confirmed from `mcp_server.py` `TOOLS` list.

```
Core — Graph Queries (always active):
  query_graph          Natural-language codebase Q&A
  get_dependencies     Direct import/call deps for a module
  find_callers         Who calls a given function?
  get_summary          Module-level docstring summary
  list_communities     Semantic clusters in the graph
  list_packages        All top-level packages in the graph
  cost_report          Token savings from the last build
  analyze_impact       Blast radius of changing a symbol
  get_graph_diff       What changed since last build? (nodes/edges)

DriftGuard — Import Validation:
  validate_import      Does this import actually exist in the graph?
  scan_suggestion      Pre-validate a code suggestion before applying

GhostMemory — Context Persistence:
  remember             Store a fact/snippet in the context store
  recall               Retrieve stored facts by key

ContextLens — Context Tracking:
  get_active_context   What's been injected into agent context?
  measure_token_usage  Token count of current context window
  trace_last_tool_calls Recent tool call trace

TaskWeaver — Agent Checkpoints:
  create_checkpoint    Save agent progress with git SHA
  get_task_progress    Checkpoint DAG for a task
  rollback_to_checkpoint Revert to a previous checkpoint state
  list_checkpoints     All checkpoints for a task

BudgetGovernor — Token Budget:
  check_budget         Current session token spend vs cap

RulesForge — Coding Rules:
  get_applicable_rules Coding rules for the open file (AST-detected layer)
  learn_from_accept    Record an accepted suggestion as a learned rule
```

---

## Test Coverage

| Suite | Tests | Command |
|-------|------:|---------|
| Python (all modules) | **460** | `python -m pytest tests/ --tb=short -q` |
| JS — DriftGuard wiring | **8** | `node test\test_extension_driftguard.js` |
| JS — Dashboard HTML | **30** | `node test\test_dashboard_html.js` |
| JS — Extension Host (T1–T10) | **10** | `npm test` |
| **Total** | **508** | **0 failures** |

---

## Project Structure

```
├── extension.js              # Lean entry point (~130 lines, imports from src/)
├── src/
│   ├── utils.js              # Logging, nonce, escapeHtml, workspace helpers
│   ├── cli-runner.js         # spawnCLI, runCLI, cost report, status bar
│   ├── commands.js           # All 15 command handlers
│   ├── driftguard.js         # On-save Python import validation (Diagnostics)
│   ├── sidebar-provider.js   # WebviewViewProvider for sidebar panel
│   ├── sidebar-html.js       # Full sidebar HTML/CSS/JS template
│   ├── dashboard.js          # 4-tab Analytics dashboard (WebviewPanel)
│   └── telemetry.js          # Opt-in local telemetry (see Telemetry section)
├── build.js                  # esbuild bundler (npm run build → dist/extension.js 70KB)
├── dist/
│   └── extension.js          # Production bundle (minified, 70KB)
├── jsconfig.json             # TypeScript-lite: @ts-check + JSDoc type checking
├── package.json              # Extension manifest (19 commands, 6 settings)
├── python/
│   ├── pruvagraph/
│   │   ├── mcp_server.py     # 23-tool MCP server (stdio transport)
│   │   ├── cli.py            # CLI entry point (pruvagraph .)
│   │   ├── installer.py      # MCP config writer (.vscode/mcp.json etc.)
│   │   ├── benchmark_harness.py  # Truth Machine — 84 questions
│   │   ├── driftguard.py     # Import/type validation
│   │   ├── context_lens.py   # Context tracking
│   │   ├── task_weaver.py    # Checkpoint DAG
│   │   ├── budget_governor.py # Token budget
│   │   └── rules_forge.py   # Coding rules
│   └── tests/                # 460 Python tests
├── tests/
│   ├── extension/
│   │   └── commands.test.js  # 10 Extension Host integration tests (T1–T10)
│   ├── test_extension_driftguard.js   # 8 JS unit tests
│   └── test_dashboard_html.js         # 30 dashboard HTML tests
└── scripts/                  # Dev utilities (patch scripts, etc.)
```

---

## Privacy

- **No code sent externally** when using `--backend none` (default)
- Graph JSON stays in `pruvagraph-out/` on your machine
- LLM backends (`gemini`, `claude`, etc.) only receive docstrings/summaries you explicitly extract with `--backend <name>`
- MCP server runs as a local subprocess — no network ports opened

---

## Telemetry

PruvaGraph collects **minimal, opt-in, local-only** telemetry:

| What | Stored Where | Network? |
|------|-------------|----------|
| Activation count | VS Code `globalState` | **No** |
| Command names used (e.g. `pruvagraph.build`) | VS Code `globalState` | **No** |

- **No user data, file paths, code content, or arguments are ever recorded.**
- Telemetry respects VS Code's global `telemetry.telemetryLevel` setting — set it to `"off"` to disable completely.
- All counters stay in your local VS Code storage. **Zero network calls. Zero external endpoints.**
- You can inspect all stored counters via the `getTelemetrySummary()` API in `src/telemetry.js`.

---

## License

MIT — © 2026 PRUVALEX Systems

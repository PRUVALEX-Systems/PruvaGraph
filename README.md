<div align="center">

<img width="2976" height="1438" alt="Gemini_Generated_Image_9z09pu9z09pu9z09" src="https://github.com/user-attachments/assets/39b951ec-bd38-41fa-8fd6-a522c7ed1d1e" />


<img src="docs/logo.png" width="88" alt="PruvaGraph logo">

# PruvaGraph

### Your codebase as a knowledge graph. Your AI bills as a rounding error.

**Turn any Python repo into a compact, queryable graph — then route every AI query through it.  
Same questions. 70–82% fewer tokens. Zero code leaves your machine.**

<br>

[![VS Code](https://img.shields.io/badge/VS%20Code-%5E1.85-007ACC?logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=pruvalex.pruvagraph)
[![Version](https://img.shields.io/badge/version-1.9.1-14B8A6?logo=git&logoColor=white)](https://github.com/PRUVALEX-Systems/PruvaGraph/releases)
[![Tests](https://img.shields.io/badge/tests-508%20passed-22C55E?logo=pytest&logoColor=white)](#test-coverage)
[![Benchmark](https://img.shields.io/badge/savings-81.5%25%20verified-F97316?logo=speedtest&logoColor=white)](#benchmark)
[![MCP Tools](https://img.shields.io/badge/MCP%20tools-23-8B5CF6?logo=anthropic&logoColor=white)](#mcp-tools)
[![License](https://img.shields.io/badge/license-MIT-3B82F6)](./LICENSE)
[![WCAG](https://img.shields.io/badge/accessibility-WCAG%202.1%20AA-A855F7)](#accessibility)

<br>

[**Install Extension**](#-install-vs-code-extension) · [**Python CLI**](#-python-cli) · [**MCP Tools**](#mcp-tools) · [**Benchmark**](#benchmark) · [**Discord**](https://discord.gg/pruvalex)

<br>

<img width="1421" height="1012" alt="image" src="https://github.com/user-attachments/assets/b23703db-621b-4755-9f0d-b62c6e1ba306" />


---

<div align="center">

## What 46,000 nodes look like

</div>

<img width="1920" height="954" alt="image" src="https://github.com/user-attachments/assets/2e5bad80-37f7-4bbe-9fba-599a2faba51c" />


> *PruvaGraph's interactive HTML visualizer — every node is a module, function, or class. Every edge is a real dependency. Zoom, filter, search. Runs locally, no server.*

<br>

---

## The problem with AI coding assistants

Every time Claude Code, Cursor, or Copilot answers a question about your codebase, it re-reads files. A 500-file Python project with daily CI can generate **3,300,000 LLM calls per month**. At Claude Sonnet rates, that's **$313/month** — just for context.

The root cause: agents operate on raw file content. There's no middle layer that says *"these 3 nodes answer the question; you don't need to read 40 files."*

**PruvaGraph is that middle layer.**

<br>

---

## How it works — 4 tiers, zero wasted tokens

```
Every query is routed to the cheapest tier that can answer it:

 ┌──────────────────────────────────────────────────────────────┐
 │  TIER 0 — Cache hit        $0.000    exact match in 0.2ms    │
 │  TIER 1 — Deterministic    $0.000    graph traversal, no LLM │
 │  TIER 2 — Embedding        ~$0.00001 local BAAI model        │
 │  TIER 3 — LLM Subgraph     ~$0.0001  LLM on 2-hop graph      │
 └──────────────────────────────────────────────────────────────┘
         ↑ 70–82% of queries never reach Tier 3.
```

The graph is built once from your codebase using Tree-sitter (local, free, 30+ languages). Every subsequent query traverses the graph — not your files. **Your codebase is analyzed on your machine and never sent anywhere with `--backend none` (the default).**

<br>

---

## Quick Start — 3 commands

```bash
# 1. Install the Python package
pip install pruvalex-pruvagraph

# 2. Build the graph for your project
cd /your/project
pruvagraph .

# 3. Wire to your AI agent
pruvagraph install --claude   # Claude Code
pruvagraph install --cursor   # Cursor
pruvagraph install --vscode   # VS Code Copilot
```

Reload your IDE. Your agent now has **23 MCP tools** to query the graph instead of reading files.

<br>

---

<div align="center">

## The VS Code experience

</div>

![PruvaGraph VS Code sidebar — analytics dashboard showing $0.59 savings, 196K tokens saved, 243 API calls avoided](docs/screenshot-dashboard.png)

> *Left: the sidebar panel (Explorer / Context / Costs tabs). Right: the 4-tab Analytics Dashboard — Cost Dashboard, Tier Map, Timeline, Budget. Every number is live from your last build.*

**The sidebar shows you exactly what's happening:**

| Metric | What it means |
|--------|---------------|
| **Estimated Savings** | USD saved vs. feeding raw files to the LLM |
| **Tokens Saved** | Cumulative token reduction this session |
| **Cache Hits** | Queries answered at Tier 0 — $0.000 each |
| **API Calls Avoided** | Times the agent didn't need to call any LLM |

<br>

---

## Install VS Code Extension

**Option A — VSIX (recommended, works offline):**
```bash
code --install-extension pruvalex-pruvagraph-1.9.1.vsix
```

**Option B — VS Code Marketplace:**
```
Ctrl+Shift+X  →  Search "PRUVALEX PruvaGraph"  →  Install
```

**Option C — Command line:**
```bash
code --install-extension pruvalex.pruvagraph
```

Works in **VS Code**, **Cursor**, **Windsurf**, **VSCodium**, and **Gitpod** (via Open VSX).

<br>

---

## Python CLI

```bash
pip install pruvalex-pruvagraph    # stable release
# or
pip install -e ./python            # from source

pruvagraph --help
```

**Every flag you'll actually use:**

```bash
# Build
pruvagraph .                       # full build, current dir
pruvagraph . --update              # incremental — changed files only
pruvagraph . --backend gemini      # extract docs with Gemini (cheap)
pruvagraph . --backend none        # code-only, zero API calls (default)
pruvagraph . --dry-run             # cost estimate, no API calls, no build

# Query
pruvagraph query "how does auth connect to the DB?"
pruvagraph query "top 5 god nodes in this repo"

# IDE wiring
pruvagraph install --claude        # Claude Code (CLAUDE.md + .mcp.json)
pruvagraph install --cursor        # Cursor (.cursor/mcp.json)
pruvagraph install --vscode        # VS Code (.vscode/mcp.json)
pruvagraph install                 # all three at once

# Export & reports
pruvagraph cost-report             # last build's cost analytics
pruvagraph benchmark-suite --root .  # run the truth machine (84 questions)
pruvagraph export --format html    # open interactive visualizer
pruvagraph export --format graphml # yEd / Gephi import
pruvagraph export --format cypher  # Neo4j import
pruvagraph export --format obsidian # Obsidian vault

# Automation
pruvagraph watch .                 # auto-rebuild on file save
pruvagraph hook install            # git commit hook → auto-update
```

<br>

---

## MCP Tools

Exactly 23 tools — confirmed from `mcp_server.py`. Toggle any module off in VS Code Settings and the tool list updates automatically on next MCP server start.

<details>
<summary><strong>Core — Graph Queries (always active, 9 tools)</strong></summary>

| Tool | What you ask |
|------|-------------|
| `query_graph` | `"How does payment processing connect to auth?"` |
| `get_dependencies` | `"What does pipeline.py import?"` |
| `find_callers` | `"Who calls process_payment()?"` |
| `get_summary` | `"One-line summary of UserService"` |
| `list_communities` | `"What are the architectural clusters?"` |
| `list_packages` | `"All top-level packages in this graph"` |
| `cost_report` | `"How much did last build save?"` |
| `analyze_impact` | `"What breaks if I delete AuthMiddleware?"` |
| `get_graph_diff` | `"What changed in the graph since yesterday?"` |

</details>

<details>
<summary><strong>DriftGuard — Import Validation (2 tools)</strong></summary>

Validates imports and type compatibility *before* an agent edit lands in your file.
On-save diagnostics appear in VS Code's Problems panel — same UX as a type checker.

| Tool | What it does |
|------|-------------|
| `validate_import` | Does this import actually exist in the graph? |
| `scan_suggestion` | Pre-validate a code suggestion before applying |

</details>

<details>
<summary><strong>GhostMemory — Context Persistence (2 tools)</strong></summary>

Persists decisions and facts across Claude Code sessions. No more re-explaining your architecture to a cold agent.

| Tool | What it does |
|------|-------------|
| `remember` | Store a fact/decision in the context store |
| `recall` | Retrieve stored facts by key |

</details>

<details>
<summary><strong>ContextLens — Context Tracking (3 tools)</strong></summary>

Tracks what has been injected into the agent's context window and measures token usage precisely.

| Tool | What it does |
|------|-------------|
| `get_active_context` | What's been injected into agent context? |
| `measure_token_usage` | Token count of current context window |
| `trace_last_tool_calls` | Recent tool call trace |

</details>

<details>
<summary><strong>TaskWeaver — Agent Checkpoints (4 tools)</strong></summary>

Saves agent progress with git SHA. If an agent goes off-track, roll back to the last good checkpoint in one command.

| Tool | What it does |
|------|-------------|
| `create_checkpoint` | Save agent progress with git SHA |
| `get_task_progress` | Checkpoint DAG for a task |
| `rollback_to_checkpoint` | Revert to a previous checkpoint state |
| `list_checkpoints` | All checkpoints for a task |

</details>

<details>
<summary><strong>BudgetGovernor — Token Budget (1 tool)</strong></summary>

Per-session hard token cap. The agent is blocked from making more calls once the budget is exhausted — no surprise bills.

| Tool | What it does |
|------|-------------|
| `check_budget` | Current session token spend vs. cap |

</details>

<details>
<summary><strong>RulesForge — Coding Rules (2 tools)</strong></summary>

Returns context-aware coding rules for the file the agent is currently editing, derived from your repo's AST patterns.

| Tool | What it does |
|------|-------------|
| `get_applicable_rules` | Rules for the open file (AST-detected layer) |
| `learn_from_accept` | Record an accepted suggestion as a learned rule |

</details>

<br>

---

## 5 Modules — Toggle any off

All modules are enabled by default. Disable any in VS Code Settings → `pruvagraph.modules.*`.
**When a module is disabled, its MCP tools are automatically removed from the agent's tool list on next startup** — no silent no-ops.

| Module | What it does | Key benefit |
|--------|-------------|-------------|
| **DriftGuard** | Validates imports/types before edits land | Catch broken imports before they run |
| **ContextLens** | Tracks injected context + token counts | Know exactly what the agent can see |
| **TaskWeaver** | Checkpoint DAG with git SHA + rollback | Never lose agent progress again |
| **BudgetGovernor** | Per-session hard token cap | Zero surprise LLM bills |
| **RulesForge** | AST-aware coding rules per file | Agents follow your actual patterns |

```json
// settings.json — toggle individually
{
  "pruvagraph.modules.driftguard.enabled": true,
  "pruvagraph.modules.contextlens.enabled": true,
  "pruvagraph.modules.taskweaver.enabled": true,
  "pruvagraph.modules.budgetgovernor.enabled": true,
  "pruvagraph.modules.rulesforge.enabled": true
}
```

<br>

---

## Analytics Dashboard

Open with `Ctrl+Shift+P → PruvaGraph: Open Analytics Dashboard`.

| Tab | What you see |
|-----|-------------|
| **📈 Cost Dashboard** | Avg savings %, top-8 savings bar chart, live benchmark truth machine |
| **◵ Tier Map** | SVG donut: % of queries handled at Tier 0, 1, 2, 3 |
| **⏱ Timeline** | TaskWeaver checkpoint DAG per task |
| **💴 Budget Meter** | SVG arc gauge: token spend vs. your cap |

Every number in the dashboard comes from your local `pruvagraph-out/cost_report.json`. Nothing is estimated or hardcoded.

<br>

---

## Benchmark

> Real numbers from the reproducible benchmark harness (`pruvagraph benchmark-suite`).  
> 84 questions per repo, deterministic routing. Run it yourself.

| Repo | Questions | Graph tokens (avg) | Raw file tokens (avg) | Savings |
|------|----------:|-------------------:|----------------------:|--------:|
| This repo (PruvaGraph) | 84 / 84 | 450 | 3,884 | **70.5%** |
| `pallets/click` (external, 11K LOC) | 84 / 84 | 314 | 4,978 | **81.5%** |

Both runs use `--backend none` — **zero API calls, zero cost**. Savings come from graph traversal, deterministic routing, and exact-match caching.

```bash
# Reproduce on your own repo
pruvagraph benchmark-suite --root /path/to/your/project
# → pruvagraph-out/benchmark_results.jsonl
```

> **Transparency note:** The `70.5%–81.5%` figures are point-in-time snapshots from v1.9.1.
> After a future benchmark rerun that produces meaningfully different numbers, update:
> (1) `python/pruvagraph/cli.py` LOGO constant, (2) this README table.
> The benchmark harness is deterministic and auditable — no black-box claims.

<br>

---

## Test Coverage

| Suite | Tests | Command |
|-------|------:|---------|
| Python — core + all 5 modules | **460** | `python -m pytest tests/ --tb=short -q` |
| JS — DriftGuard wiring | **8** | `node test/test_extension_driftguard.js` |
| JS — Analytics Dashboard HTML | **30** | `node test/test_dashboard_html.js` |
| JS — Extension Host (T1–T10) | **10** | `npm test` |
| **Total** | **508** | **0 failures** |

```bash
# Run all 508 tests from repo root
python -m pytest python/tests/ -q && npm test
```

<br>

---

## Languages supported (Tree-sitter — always free, always local)

| Category | Languages |
|----------|-----------|
| **Web** | TypeScript, TSX, JavaScript, JSX, Vue, Svelte, Astro, CSS, HTML |
| **Backend** | Python, Go, Rust, Java, C#, PHP, Ruby, Elixir, Scala |
| **Mobile** | Kotlin, Swift, Dart / Flutter, Objective-C |
| **Systems** | C, C++, Zig |
| **Data / Infra** | SQL, YAML, Terraform / HCL, Dockerfile, Bash |
| **Other** | Lua, Julia, Haskell, OCaml, R, Fortran |
| **Docs (optional LLM)** | `.md`, `.pdf`, `.docx`, images |

Code files are **always analyzed locally at zero cost**. Doc/image extraction is opt-in and uses the cheapest viable backend.

<br>

---

## IDE Compatibility

| IDE | How to install | Notes |
|-----|---------------|-------|
| **VS Code** | Marketplace or `code --install-extension *.vsix` | Full sidebar + dashboard |
| **Cursor** | Open VSX or VSIX drag-and-drop | Full MCP integration |
| **Windsurf** | VSIX drag-and-drop | Full MCP integration |
| **VSCodium** | Open VSX Registry | Full feature parity |
| **Gitpod** | Open VSX Registry | Works in browser |
| **Claude Code** | `pruvagraph install --claude` | 23 tools via MCP stdio |
| **Any terminal** | `pip install pruvalex-pruvagraph` | CLI only, no extension |

<br>

---

## Privacy

```
Default mode (--backend none):
  ✓ No API keys required
  ✓ No code sent externally — ever
  ✓ Graph JSON stays in pruvagraph-out/ on your machine
  ✓ MCP server runs as a local subprocess — no network ports

Optional LLM extraction (--backend gemini / claude / openai):
  → Only docstrings and summaries are sent, not raw code
  → Only if you explicitly set a backend and API key
  → Explicitly opt-in, never on by default
```

<br>

---

## Project Structure

```
├── extension.js              # VS Code entry point (~130 lines)
├── src/
│   ├── commands.js           # 15 command handlers
│   ├── sidebar-provider.js   # Sidebar webview provider
│   ├── sidebar-html.js       # Full sidebar HTML/CSS/JS template
│   ├── dashboard.js          # 4-tab Analytics dashboard
│   ├── driftguard.js         # On-save import validation
│   ├── cli-runner.js         # CLI spawning + cost reporting
│   ├── utils.js              # Shared helpers
│   └── telemetry.js          # Opt-in local telemetry (zero network)
├── dist/extension.js         # esbuild production bundle (70 KB)
├── python/
│   └── pruvagraph/
│       ├── mcp_server.py     # 23-tool MCP server (stdio transport)
│       ├── cli.py            # pruvagraph . entry point
│       ├── pipeline.py       # 5-stage build pipeline
│       ├── benchmark_harness.py  # 84-question truth machine
│       ├── driftguard.py     # Import/type validation
│       ├── context_lens.py   # Context tracking
│       ├── task_weaver.py    # Checkpoint DAG
│       ├── budget_governor.py # Token budget
│       └── rules_forge.py   # AST-aware coding rules
└── python/tests/             # 460 Python tests (0 failures)
```

<br>

---

## Telemetry

PruvaGraph collects **minimal, opt-in, local-only** telemetry. No external endpoints. No user data. No code content.

| What | Stored where | Network? |
|------|-------------|----------|
| Activation count | VS Code `globalState` | **Never** |
| Command names used (e.g. `pruvagraph.build`) | VS Code `globalState` | **Never** |

Telemetry respects VS Code's global `telemetry.telemetryLevel` setting — set to `"off"` to disable. Inspect all counters via `getTelemetrySummary()` in `src/telemetry.js`.

<br>

---

## Contributing

```bash
git clone https://github.com/PRUVALEX-Systems/pruvagraph
cd pruvagraph/python
pip install -e ".[dev]"
python -m pytest tests/ -q       # 460 tests must pass
npm install && npm test           # 48 JS tests must pass
```

Best places to start:
- **Add a language extractor** → `python/pruvagraph/extract/`
- **Improve dedup thresholds** → `python/pruvagraph/dedup.py`
- **Add an LLM backend** → `python/pruvagraph/backends/`
- **Improve compression** → `python/pruvagraph/compress.py`
- **Extend the dashboard** → `src/dashboard.js`

See [CONTRIBUTING.md](./CONTRIBUTING.md) for setup, commit conventions, and the PR checklist.

<br>

---

## Why PRUVALEX built this

We build AI compliance infrastructure for enterprise software teams. PruvaGraph started as an internal tool — we were spending too much on LLM API calls during development and couldn't find anything that solved the problem without sending code to a cloud service.

So we built it ourselves and open-sourced it. If you're paying real money for AI coding assistants, the token savings are real and measurable. The benchmark harness is there so you don't have to trust us — run it on your own repo.

[pruvalex.eu](https://pruvalex.eu) · [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=pruvalex.pruvagraph) · [security@pruvalex.eu](mailto:security@pruvalex.eu)

<br>

---

<div align="center">

**MIT © 2026 PRUVALEX Systems**

*If PruvaGraph saved you money, consider giving it a ⭐ — it helps others find it.*

</div>

---

<details>
<summary>📋 Setup checklist for this README (remove before publishing)</summary>

1. Copy your two screenshots into the `docs/` folder at the repo root:
   - `docs/screenshot-graph.png` → the full-screen galaxy graph (Image 2)
   - `docs/screenshot-dashboard.png` → the VS Code sidebar + analytics panel (Image 1)
2. Add `docs/logo.png` — your PRUVALEX/PruvaGraph logo (88×88px, transparent background)
3. Replace the Discord URL `https://discord.gg/pruvalex` with your real server link (or remove that line)
4. Run `pruvagraph benchmark-suite --root .` and update the Benchmark table numbers if they differ from `70.5% / 81.5%`
5. Verify all badge URLs are still live (shields.io badges occasionally change)
6. Delete this checklist block before merging

</details>

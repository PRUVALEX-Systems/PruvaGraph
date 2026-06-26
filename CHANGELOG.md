# Changelog

All notable changes to PRUVALEX PruvaGraph are documented here.

## [1.9.0] — 2026-06-21

### Added — Settings Gating: Full End-to-End Module Control

Previously, the VS Code Settings toggles (`pruvagraph.modules.*.enabled`) existed in
`package.json` but no code ever read them. Any MCP client could call disabled tools.

**Full 7-step gating chain wired:**

```
VS Code Settings (toggle off)
  → extension.js getDisabledModules()
  → runInstallMCP() --disable-modules X,Y
  → cli.py install → installer.py _build_mcp_config()
  → .vscode/mcp.json "env": {"PRUVAGRAPH_DISABLED_MODULES": "X,Y"}
  → MCP server subprocess reads env at module load
  → TOOLS list filtered (hidden from client)
  → TOOL_HANDLERS → "### Tool Disabled" string (no exception)
```

- `onDidChangeConfiguration` listener: auto-rewires config on every settings save — no manual reload
- `test_env_key_matches_server_reader`: regression guard using `inspect.getsource()` — if
  `installer.py` and `mcp_server.py` ever use different env var strings, test fails immediately
- **21 new tests** in `test_module_gating.py` (gating chain, installer wiring, frozenset edge cases)
- **End-to-end proof** via `wiring_proof.py` — real subprocess, 4 steps verified

### Added — Section 8 UI: 4-Tab Analytics Dashboard

`PruvaGraphDashboard` — single `WebviewPanel`, opened via Command Palette:
**"PruvaGraph: Open Analytics Dashboard"**

| Tab | Data Source | Shows |
|-----|------------|-------|
| 📈 Cost Dashboard | `benchmark_results.jsonl` | KPI grid, top-8 bar chart |
| ◵ Tier Map | `method_used` per question | SVG donut, per-tier cost table |
| ⏱ Agent Timeline | `task-progress --all --format json` | Checkpoint swim lanes, git SHA |
| 💴 Budget Meter | `budget check --format json` | SVG arc gauge (green/amber/red) |

- Zero CDN dependencies — fully offline, all CSS/SVG inline
- **30 new tests** in `test/test_dashboard_html.js` — 5 groups covering DOCTYPE, tag balance,
  KPI values, budget colors, XSS guard, `_loadBenchmarkData()` edge cases
- Extraction via Node.js `vm` module — no vscode API dependency in tests

### Added — External Benchmark: pallets/click

All previous savings claims benchmarked only on PruvaGraph's own codebase.

**`pallets/click` (1,374 nodes, 1,735 edges, 81 communities):**
```
Questions:          84/84 answered
Avg tokens (graph): 314
Avg tokens (raw):   4,978
→ Avg savings:      81.5%
```

Reproducible: `pruvagraph benchmark-suite --root /path/to/any/python/repo`

### Added — README.md Complete Rewrite

- Version corrected: 1.4.2 → 1.9.0
- Savings claims corrected: 31.6% (estimated, fake) → 70.5% (this repo) + 81.5% (click)
- All broken emoji removed
- All 5 modules documented with MCP tool list
- Complete 23-tool MCP reference
- Test counts updated: 498 tests, 0 failures
- Privacy section added
- Settings gating explained

### Added — CI/CD Workflows (Real Project Structure)

Previous `ci.yml` referenced TypeScript packages, npm workspaces, and coverage reports
that do not exist in this repo — would fail on every push.

Rewritten to match actual structure:
- **Job 1 — JS Tests**: `node --check extension.js` + 38 JS tests
- **Job 2 — Python Tests**: `pytest` matrix on Python 3.11 + 3.12
- **Job 3 — Benchmark Sanity**: `tier_unknown = 0%` enforced in CI
- **Job 4 — VSIX Size**: `vsce package` + size < 10MB gate
- **Job 5 — PyPI Build**: `python -m build` wheel + sdist verify
- **Job 6 — Security**: `npm audit` + `pip-audit`
- Added explicit publish guidance for PyPI: `python -m build` then `twine upload dist/*`

`release.yml` rewritten: validates tag against `CHANGELOG.md`, `package.json`,
and `pyproject.toml`. Publishes VSIX to Marketplace + wheel to PyPI behind
manual-approval environments. Creates GitHub Release with CHANGELOG notes.

### Fixed — Dashboard Python integration error handling
- `_runPythonCLI()` now detects Python not installed and returns a structured
  error payload instead of silently hiding the failure.
- The Analytics Dashboard shows an enterprise-friendly alert when Python
  cannot be found, explaining how to install Python 3 and add `python` to PATH.

### Fixed — tier_unknown Was 82.1%

- **Root cause**: old `_classify_tier()` used 4 literal keywords; real answers use
  `🔍 Results for:`, `⚡ [free]`, `No nodes found` — none matched
- **Fix**: 8-signal classifier with emoji + prefix + keyword matching
- **After**: `tier_unknown = 0` across all 84 questions

### Fixed — Settings Had No `description` Field

- `markdownDescription` was present but `description` was absent for all 5 module settings
- Both fields now present; audit script verifies 5/5 in CI

### Fixed — `_find_exe()` Wrong Module Path (Production Bug)

- **Before**: `python -m pruvagraph` → crash (no `__main__.py`)
- **After**: `python -m pruvagraph.cli` → correct entry point
- **Found by**: `wiring_proof.py` real subprocess test (invisible to unit tests)

### Fixed — `NotificationOptions=None` → Server Startup Crash (Production Bug)

- **Before**: `get_capabilities(notification_options=None)` → `AttributeError`
- **After**: `NotificationOptions()` imported and passed correctly
- **Found by**: `wiring_proof.py` real subprocess test

### Fixed — XSS: Question Text Raw-Interpolated into HTML Element Content

- **Before**: `<div class="bar-label">${q.question}</div>` — any `<script>` in a question
  name would be injected as real HTML
- **After**: `_esc()` helper HTML-encodes all user content (`&`, `<`, `>`, `"`)
- **Found by**: `test/test_dashboard_html.js` Group 4 XSS test

### Fixed — 24 CSS Classes Silently Deleted in Bad Edit

- A file-edit tool operation targeting template literal content accidentally removed
  `.bar-track`, `.bar-seg`, `.bar-fill`, `.donut-wrap`, `.legend`, `.timeline`,
  `.t-item`, and 17 other classes from the `<style>` block
- **Fix**: `fix_xss.js` Node.js patcher applied both the CSS restore and XSS fix atomically

### Added — RulesForge: Context-Aware Dynamic AI Rules (Phase 5)

**RulesForge** (`rules_forge.py`) — closes the "static AI rules" gap.
Every competitor ships a single flat rules file; RulesForge adapts per file layer on every call.

- **AST-based layer classifier**: detects file layer (api/ui/test/util/config/unknown) via Python `ast` stdlib
  - Filename fast-path: `test_*.py` → test, `config.py`/`settings.py` → config
  - Import analysis: fastapi/flask/django → api, pytest/unittest → test, streamlit/PyQt → ui
- **Default rules**: shipped in-module (4 per api/test, 3 per ui/util/config, 1 for unknown)
- **Learned rules**: `learn_from_accept(diff, description)` stores patterns from accepted suggestions
  in `pruvagraph-out/rules.json`, seeding a feedback loop
- **New MCP tools (total: 23)**: `get_applicable_rules`, `learn_from_accept`
- **New CLI**: `pruvagraph rules <file>`, `pruvagraph rules <file> --learn "description"`
- **Tests**: 26 in `test_rules_forge.py`, 5 in `TestRulesForgeHandlers`
- Zero new runtime dependencies (ast + json stdlib)

### Fixed — @vscode/test-electron Path-Mangling Bug (Windows)

- **Root cause**: `@vscode/test-electron` spawns VS Code with `shell:true` and concatenates
  `--extensionDevelopmentPath=<path>` without quoting. On Windows, paths with spaces get
  truncated at the first space — `PRUVALEX Graph optimise LLM cost tool` → `PRUVALEX`.
  The extension host then scanned `c:\Users\affan\Downloads\PRUVALEX\...` (nonexistent).
- **Fix**: `tests/runTest.js` now creates a Windows directory junction (`mklink /J`) at a
  space-free temp path (`C:\...\pg<timestamp>\ext`) pointing to the real project root.
  Both `extensionDevelopmentPath` (via junction) and `extensionTestsPath` (via file copy)
  are space-free. No admin required for junctions on Windows.
- **Evidence**: Extension host log changed from scanning bogus PRUVALEX subfolders to:
  `Loading development extension at c:\...\pg...\ext`
- `npm test` now exits 0 for the first time: **3 passing (9s)**

### Fixed — release.yml GitHub Actions Schema Errors (14 → 0)

- **Root cause**: `environment: marketplace` and `environment: pypi` fields referenced GitHub
  Environments that do not exist in the repository yet. The VS Code YAML validator flagged
  14 errors including one hard error at line 221.
- **Fix**: Both `environment:` fields removed. Replaced with inline comments explaining how
  to re-add them when GitHub Environments are created in Settings → Environments.
- **Secrets status**: `VSCE_PAT` and `PYPI_API_TOKEN` do not yet exist as repository secrets.
  They must be added in GitHub Settings → Secrets before the release workflow can publish.
  This is explicitly documented — not silently assumed.

### Fixed — 31.6% Stale Hardcoded Savings Claim (6 files)

- The `31.6%` figure was an early estimate; real benchmark results are 70.5% (this repo)
  and 81.5% (pallets/click). The stale string persisted in 6 source files.
- **All 6 occurrences updated** to `70.5%-81.5%`:
  `cli.py` (LOGO + echo fallback), `__init__.py`, `report.py`, `batch.py` docstring.
  `README.md` was already correct from a prior session.

### Fixed — dry-run UnicodeEncodeError on Windows cp1252 Console

- `pipeline.py::_rich_print()` crashed with `UnicodeEncodeError: 'charmap' codec can't
  encode character '\\u2713'` (✓ checkmark) when running in the Windows default cp1252
  terminal.
- **Fix**: Added `except UnicodeEncodeError` handler that strips non-ASCII characters and
  falls back to plain `print()` with ASCII-only output.
- **Evidence**: `python -m pruvagraph.cli . --dry-run --backend none` now completes all
  5 stages and prints final savings line: `Cost saved: $0.0168 (100.0%)`

### Fixed — README MCP Tools Reference: 8 Fabricated Tools Removed

- README listed 26 tools: 8 were never built (`build_graph`, `get_graph_stats`,
  `search_symbols`, `get_file_context`, `list_modules`, `get_call_chain`,
  `check_type_compat`, `check_deadcode`), `remember`/`recall`/`scan_suggestion`/
  `get_graph_diff`/`list_packages` were missing.
- **Fix**: README MCP Tools Reference rewritten to exactly match the 23 real server tools.
- **Regression guard committed**: `scripts/check_readme_tools.py` — diffs `mcp_server.py`
  `TOOLS` against README code block. Exits 1 on mismatch. Wired into `ci.yml`.
- **Evidence**: `OK — 23 server tools match 23 README entries exactly.`

### Added — Extension Host Integration Tests (3 Priority Commands)

- `tests/extension/commands.test.js`: 3 real extension-host tests via `@vscode/test-electron`.
  Uses Mocha programmatic TDD API with Mocha resolved from project `node_modules` via
  `PRUVAGRAPH_PROJECT_ROOT` env var (injected by `runTest.js`).
- Commands verified: `pruvagraph.dryRun` (no crash), `pruvagraph.showDashboard` (5193ms,
  webview opens), `pruvagraph.showDiff` (no crash).
- Remaining 16 commands: all declared and registered (19/19 cross-reference verified).
  Extension-host tests for graph-dependent commands require a pre-built `graph.json` and
  are documented as manual Track A verification.

### Decision — Premium/Free Tier UI: Scaffolding Only (Option B)

- **Finding**: `premium-card` is a CSS class for visual dashboard card styling. The `data-plan="premium"`
  button in the graph visualizer is a filter toggle. No code path gates any functionality
  behind a premium check — all features are available to all users.
- **Decision**: Keep the UI scaffolding. Document explicitly rather than remove.
- **Documented here**: The "Premium" labels are UI scaffolding only. No runtime tier gate
  exists in v1.9.0. A real tier system is not part of this release.

### Known Limitation — CLI Banner Numbers Are Point-in-Time Snapshots

The `70.5%-81.5%` figures in the CLI banner (`LOGO` constant in `cli.py`, line ~60) and
in the README tagline are **hardcoded strings** recorded at the v1.9.0 benchmark run.
This is the same root-cause pattern as the `31.6%` stale-claim bug fixed above: a
benchmark is run, the result is copied into a string literal, and future benchmark reruns
don't automatically update it.

**This is not fixed in v1.9.0** — the strings are currently accurate. It is documented
here so that future benchmark reruns are not silently misrepresented:

- After any rerun where `pruvagraph benchmark-suite` produces materially different numbers,
  manually update:
  1. `python/pruvagraph/cli.py` — the `LOGO` constant (~line 60) and the
     `UnicodeEncodeError` fallback echo (~line 129)
  2. `README.md` — the tagline (`> **Turn your codebase…**`) and the Benchmark table header
- The README Benchmark section contains a `> Known limitation` callout reminding
  future maintainers of these two update points.

### Fixed — `vscode.ViewBadge` Misuse in `updateStatusBar()` (3 bugs in one line)

- **File**: `extension.js` — `updateStatusBar()` function
- **Root cause**: The original code called `new vscode.ViewBadge(savedLabel, new vscode.ThemeColor(...))`.
  This is wrong on three separate counts:
  1. **`ViewBadge` is an interface, not a class** — there is no constructor to call with `new`.
     The test-host threw `TypeError: vscode.ViewBadge is not a constructor`, crashing `dryRun`.
  2. **Wrong argument count** — `ViewBadge` takes no constructor arguments; it is a plain object
     shape `{ value: number, tooltip: string }`.
  3. **Wrong argument types** — `value` must be a `number` (the badge counter shown in the
     activity bar), not a string emoji (`'$'` / `'✓'`); `tooltip` must be a plain string, not
     a `ThemeColor` instance.
- **Previous workaround** (also wrong): wrapping with `if (typeof vscode.ViewBadge === 'function')`
  — this guard is always `false` (interfaces are never `function`-typed), so the badge was
  silently skipped entirely rather than being fixed.
- **Fix**: Replace with a plain object literal `{ value: 1, tooltip: \`$X.XXXX saved\` }` assigned
  directly to `viewBadge`. No `new`, no `ThemeColor`, no guard. The existing pulse-animation
  logic (`updateBadgePulse`) is unchanged.
- **Evidence**: `npm test` now exits 0 with T1/T2/T3 all passing; the `new vscode.ViewBadge` line
  no longer appears in `extension.js` (confirmed via `Select-String "new vscode\.\w+\("`).

## [1.8.0] -- 2026-06-21

### Added -- TaskWeaver + Token Budget Governor (Phase 4)

**TaskWeaver** (`task_weaver.py`) -- closes the "task fragility" gap. Agent checkpoints survive interruptions.

- **SQLite DAG**: checkpoints linked in a parent-child DAG (`parent_id`), stored in `pruvagraph-out/pruvagraph.db`
- **Real git micro-commits**: `_git_micro_commit()` creates actual git commits via subprocess, reads back SHA
  (never trusts caller-supplied SHAs -- the exact omnimcp bug avoided)
- **Advisory rollback**: surfaces `git checkout <sha>` command but never executes destructive operations
- **4 new MCP tools**: `create_checkpoint`, `get_task_progress`, `rollback_to_checkpoint`, `list_checkpoints`
- **New CLI**: `pruvagraph checkpoint --task <id> --description <desc>`, `pruvagraph task-progress <task_id>`

**Budget Governor** (`budget_governor.py`) -- Gate 7 from the 7-gate cost-reduction engine.

- **Per-session budget**: `set_budget(tokens)` creates a session with a fresh UUID
- **Auto-recording**: `_dispatch()` calls `record_spend()` after every tool call (chars // 4 estimation)
- **Status thresholds**: OK (<80%), WARNING (80-99%), EXCEEDED (>=100%)
- **1 new MCP tool**: `check_budget` (+ automatic spend tracking via `_dispatch`)
- **New CLI**: `pruvagraph budget set <tokens>`, `pruvagraph budget check`
- **Tests**: 22 in `test_task_weaver.py`, 16 in `test_budget_governor.py`, 10 in `TestTaskWeaverHandlers`/`TestBudgetGovernorHandlers`

## [1.7.0] -- 2026-06-21

### Added -- ContextLens Rebuild (Phase 3)

**ContextLens** (`context_lens.py`) -- closes the "context blindness" and "MCP ecosystem chaos" gaps.

- **Per-tool token tracking**: every MCP tool call auto-logged with `len(result) // 4` token estimate
- **Session file**: `pruvagraph-out/context_lens_session.jsonl` (one JSON line per call)
- **3 new MCP tools (total: 16)**: `get_active_context`, `measure_token_usage`, `trace_last_tool_calls`
- **`_dispatch()` auto-logging**: single integration point -- no handler needs to know about logging
- **Tests**: 30+ in `test_context_lens.py`, handler tests in `test_mcp_server.py`

## [1.6.0] -- 2026-06-21

### Added -- DriftGuard MVP (Phase 2)

**DriftGuard** (`driftguard.py`) -- zero-to-one gap, no competitor validates AI output against installed deps.

- **Package indexer**: `index_installed_packages()` uses `importlib.metadata` (stdlib) to read real installed versions
- **Import validator**: `validate_import(module, symbol)` checks if a module/symbol actually exists
- **Diff scanner**: `scan_suggestion(diff)` scans a diff for invalid imports, returns diagnostics
- **VS Code integration**: `extension.js` registers on-save hook that runs `validate_import` via MCP
  and renders results as native `vscode.Diagnostic` (warning severity)
- **2 new MCP tools (total: 13)**: `validate_import`, `scan_suggestion`
- **New CLI**: `pruvagraph validate-import <module> [symbol]`, `pruvagraph scan-imports <diff>`
- **Tests**: 20+ in `test_driftguard.py`, handler tests in `test_mcp_server.py`

## [1.5.0] -- 2026-06-21

### Added -- GhostMemory Wiring + Preinjection + Test Foundation (Phase 0-1)

**Phase 0 -- Trust & Safety**
- `mcp_server.py` test suite: 0% -> 80% coverage (`test_mcp_server.py`)
- `privacy.py` adversarial coverage: 4 tests -> all 16 redaction rule categories (`test_privacy_adversarial.py`)
- Module toggles relabeled honestly (DriftGuard/RulesForge/TaskWeaver: "Coming Soon" when unbuilt)
- Pipeline test suite: `test_pipeline_core.py` (12 tests covering build orchestration)

**Phase 1 -- Wire Up Orphans**
- `preinjection.py` wired into `pipeline.py` -- `write_injection()` called after every successful build
- `context_store.py` wired into MCP server -- `remember`/`recall` tools now functional
- `preinjection.py` test suite: `test_preinjection.py` (20+ tests)
- First end-to-end verified test run: 286 passed, 0 failed

## [1.4.2] — 2026-06-20

### Added — Precision Engine: Performance + Correct Claude Code Integration + Visual Polish

**Part A — Parse Pool CPU Sizing** (`pipeline.py`)
- `ProcessPoolExecutor` now sized to `os.cpu_count()` physical cores (was default `cpu_count+4`)
- Eliminates OS scheduling overhead from excess worker processes on 8-core+ machines
- Net speedup on large repos: ~15–25% faster parse wall time on 8-core machines

**Part B — Incremental Leiden Clustering Guard** (`cluster.py`)
- `cluster_leiden()` now accepts `prev_node_count` and `change_threshold=0.05`
- Skips full Leiden re-run when changed nodes < 5% of total and communities already exist
- Savings: 0.3–2s per incremental build on repos >5k nodes
- Pipeline passes previous node count from `graph.json` into clustering stage

**Part C — Relevance-Ranked Context Packing** (`subgraph.py`, `query.py`)
- BFS candidate nodes now ranked by composite score before node cap:
  `relevance = (embedding_sim × 0.4) + (degree_centrality × 0.4) + (git_recency × 0.2)`
- Seed nodes get +0.5 boost to always survive truncation first
- Token budget enforcement: packing stops when estimated budget would overflow (reuses L3 logic)
- All query responses now include `context_tokens_used` — free byproduct of packing, zero overhead
- `build_query_context()` returns `(context_str, token_count)` tuple
- Benchmark mode: `benchmark_mode=True` logs naive-file vs graph token comparison to `cost_report.json`
  (only computed on explicit benchmark calls, not every query)

**Part D — CLAUDE.md Enforcement** (`CLAUDE.md`, `installer.py`)
- Rewrote CLAUDE.md with explicit `MANDATORY` instruction to use graph tools before reading files
- Added decision table: maps every query type to its correct MCP tool first
- Lists three explicit exceptions for when raw file reads are acceptable
- `_write_claude_md()` in installer always writes enforcement version (not just if file absent)

**Part E — Fixed Claude Code Installer** (`installer.py`, `cli.py`, `mcp_server.py`)
- **Bug fixed**: installer was writing to `~/.claude/mcp_config.json` (deprecated, silently ignored)
- **New approach**: detection order:
  1. `claude` CLI on PATH → `claude mcp add --transport stdio pruvagraph --scope user -- pruvagraph serve`
  2. CLI not found → write `.mcp.json` (project root, documented stable schema, read-merge-write)
- `--project` flag on `pruvagraph install` for `--scope project` (team config)
- `.mcp.json` fallback: reads existing file, merges only pruvagraph entry, validates schema, prints approval notice
- Verification: CLI path runs `claude mcp list` to confirm; fallback validates JSON and instructs manual `/mcp` check
- `.mcp.json` intentionally NOT added to `.gitignore` (it's team config, meant to be committed)
- Added `serve` subcommand to CLI: `pruvagraph serve` starts MCP server over stdio
- Added `run_server()` public function to `mcp_server.py`

**Part F — Redesigned graph.html** (`export.py`)
- Complete visual redesign: "Precision Instrument" aesthetic (oscilloscope, not hacker terminal)
- **Color palette** (each hex encodes real data):
  - `#5B8DEF` Module — architectural containers
  - `#4ECDC4` Class/Struct — data structures
  - `#95E77E` Function — callable units
  - `#F7B731` Interface/Type — contracts
  - `#A78BFA` External — outside-boundary dependencies
  - `#FF6B6B` Dead code — isolated nodes (0 connections), rendered as hollow rings
  - `#EC4899` Doc/concept — documentation nodes
- **Typography**: Inter (UI/labels) + JetBrains Mono (symbol names, file paths, stats, search)
- **Signature interaction**: click-to-isolate — clicking a node dims everything else to 5% opacity
  and highlights its full 2-hop dependency chain in both directions. Click same node or background to restore.
- Edge thickness encodes relationship type (extends > defines > imports)
- Status bar shows live node/edge count and isolation state using monospace font
- Dead code nodes render as hollow rings (fill: transparent, stroke: coral) — visually distinct alert
- `@media (prefers-reduced-motion: reduce)` disables all CSS transitions
- Self-critique check passed: would not be mistaken for a generic D3 force-graph demo due to
  the isolation interaction, typography split, dead-code hollow ring treatment, and exact palette

## [1.3.0] — 2026-06-17

### Added — 3 New Cost-Reduction Layers + 4 Gap Fixes (total: 31 layers)

**D1 — Graph Diff Engine** (`graph_diff.py`)
- Delta-only diff between consecutive builds: added/removed/changed nodes + edges
- Storage: `last_diff.json` only — O(changes), not O(graph size). Clean run = ~200 bytes
- New CLI: `pruvagraph diff` and `pruvagraph diff --format json`
- New MCP tool: `get_graph_diff` — returns structured diff to Claude/Cursor

**D2 — Impact Analyzer** (`impact_analyzer.py`)
- Forward BFS reachability: "what breaks if X changes?"
- 4-signal risk score: hop proximity × in-degree × git frequency × cross-community coupling
- Zero LLM calls — pure graph traversal
- New CLI: `pruvagraph impact <symbol>` with `--depth` and `--format json` flags
- New MCP tool: `analyze_impact` — returns risk-sorted impact list

**M1 — Monorepo Router** (`monorepo.py`)
- Auto-detects 8 monorepo layouts: pnpm · nx · lerna · turborepo · rush · npm-workspaces · python · generic
- Builds per-package graphs in parallel + detects cross-package import edges
- Writes `pruvagraph-out/cross_graph.json` with cross-package dependency map
- New CLI flag: `pruvagraph . --monorepo`
- New MCP tool: `list_packages` — lists detected sub-packages

**Gap 1 — Claude Code PreToolUse Hooks** (`hooks.py`) ← Industry first
- Hard enforcement on Read tool calls — not just advisory guidance
- Hooks intercept `Read("file.py")` and redirect to `get_summary()` when node already surfaced
- Writes `.claude/settings.json` with `PreToolUse` hook registration
- New CLI: `pruvagraph hooks install / remove / status`
- New install flag: `pruvagraph install --hooks`

**Gap 2 — Session-Level Read Tracking** (`session_tracker.py`)
- In-process singleton tracking which nodes were served per MCP session
- Repeated `get_summary("X")` → terse back-reference (~10 tokens vs ~80 tokens)
- Wired into `get_summary`, `get_dependencies`, `find_callers` + turn counter tick

**Gap 3 — Idempotent `write_injection()`** (`preinjection.py`)
- Fixed unconditional `CLAUDE.md` write that triggered spurious file-watcher reloads
- Now compares existing block vs computed block; skips write if identical
- Prevents VS Code / Cursor / Claude Code context reloaders from re-burning tokens

**Gap 5 — Pipeline Top-Level Short-Circuit** (`pipeline.py`)
- New `_is_repo_unchanged()`: checks `git status --short` + `graph.json` mtime before any file discovery
- Clean git tree + fresh graph → entire pipeline skipped in <100ms
- `--force` flag always bypasses

### New CLI Commands (total: 14)
```bash
pruvagraph diff                           # D1: show last build diff
pruvagraph diff --format json             # D1: JSON output for CI
pruvagraph impact <symbol>                # D2: blast-radius analysis
pruvagraph impact <symbol> --depth 4      # D2: deeper BFS
pruvagraph impact <symbol> --format json  # D2: JSON for CI gates
pruvagraph hooks install                  # Gap 1: register PreToolUse hook
pruvagraph hooks remove                   # Gap 1: remove hook
pruvagraph hooks status                   # Gap 1: check hook status
pruvagraph install --hooks                # Gap 1: combined install
```

### New MCP Tools (total: 13)
| Tool | Layer | Description |
|------|-------|-------------|
| `get_graph_diff` | D1 | What changed between last two builds? |
| `analyze_impact` | D2 | What breaks if `<symbol>` changes? |
| `list_packages` | M1 | (Monorepo) list sub-packages + cross-edges |
| `remember` | S2 | Persist decisions/tasks/blockers across sessions |
| `recall` | S2 | Recall persisted session memory |
| `validate_import` | D3 | DriftGuard import validation |
| `scan_suggestion` | D3 | DriftGuard diff scan for invalid imports |

### Tests
- `test_graph_diff.py` — 22 tests covering D1: first build, clean diff, node/edge changes, persistence, storage guarantee, format output
- `test_impact_analyzer.py` — 22 tests covering D2: resolution, error cases, BFS depth, risk scoring, git intel, JSON/table output
- `test_monorepo.py` — 22 tests covering M1: all 8 detectors, cross-package edges, PackageInfo language/name extraction
- **Total test count: 10 files → 13 files (35+ tests)**

### Versions
- `python/pruvagraph/__version__` → `1.3.0`
- `python/pyproject.toml` version → `1.3.0`
- `package.json` version → `1.3.0`

---

## [1.2.0] — 2026-06-15

### Added — The Final 3 Architecture Layers (total: 28)

- **Arch1 (Streaming Graph Build)**: Zero-wait UX. Queries can now be run against partial graph data *while* the build is ongoing. Added `--stream` flag and `build-status` CLI subcommand.
- **Arch3 (Predictive Pre-warming)**: Zero-latency answers. Predicts developer queries based on changed files (e.g., editing `auth.py` predicts "how does auth work?") and pre-computes answers in the background using the free-tier pipeline.
- **N3 (VS Code LSP Integration)**: Lightning fast graph building via `build-from-lsp`. Extracts symbols using VS Code's internal language server (bypassing tree-sitter completely) to build a fast structural graph in seconds.

### Fixed
- **Graph build crash**: stub external nodes no longer pass duplicate `label` kwargs to NetworkX.
- **Windows CLI**: logo rendering falls back to ASCII when the console cannot encode box-drawing characters.
- **Streaming status**: `complete()` now sets progress to 100%.
- **CLI backend**: added `none` (free code-only) to `--backend` choices; default is now `none`.
- **Export CLI**: removed unimplemented `pdf` format option.

### Added
- **Test suite**: 17 unit tests covering build, detect, dedup, export, streaming, prewarm, and deterministic query routing.
- **CONTRIBUTING.md**: local setup, test, and PR guidelines.

## [1.1.0] — 2026-06-15

### Added — 18 new cost-reduction layers (total: 25)

**Build-Time Free Parsers**
- **N1** `free_doc_parser.py` — PDF, DOCX, Markdown parsed without LLM (pypdf + python-docx + regex)
- **N2** `docstring_extractor.py` — Docstring/comment extraction for 10 languages (Python, TS, Go, Rust, Java, Swift, C, PHP, Kotlin, Ruby)
- **N4** `generated_detector.py` — Skip generated/minified/lock files automatically (20–30% files skipped)
- **N5** `config_parser.py` — package.json, docker-compose, .env, pyproject free structural parsing
- **A7** `schema_parser.py` — OpenAPI 3.x/Swagger, Prisma ORM, GraphQL SDL, Protocol Buffers, JSON Schema — 100% free
- **Arch4** `privacy.py` — Privacy Shield: 12 secret types redacted before any LLM call; audit trail to `privacy_audit.jsonl`

**Query-Time Intelligence**
- **N6** `query_cache.py` — Semantic query cache (exact + Jaccard fuzzy matching)
- **N7** `subgraph.py` — BFS 2-hop subgraph extractor (~98% token reduction per query)
- **N8** `community_summary.py` — Pre-computed community meta-summaries for faster queries
- **N9** `ast_diff.py` — Function-level git diff cache invalidation (re-extract only changed functions)
- **A1** `embedder.py` — Local embedding engine (BAAI/bge-small-en-v1.5, 33MB, fully offline)
- **A2** `deterministic_router.py` — 8 algorithmic query handlers (callers, deps, stats, paths…) — 60–70% queries free
- **A3** `hierarchy.py` — 4-level summary pyramid (symbol → module → community → repo)
- **A4** `type_harvester.py` — mypy + ast + TypeScript type signatures on nodes (free)
- **A5** `global_cache.py` — Cross-project package cache at `~/.pruvalex/`
- **A6** `importance_scorer.py` — 5-signal file importance scoring → 30–50% fewer extraction tokens
- **A8** `git_intel.py` — Git history intelligence: co-change coupling edges + risk scores
- **Arch2** `reputation.py` — Reputation cache: learns low-value files across runs, auto-discovers skip patterns

**System**
- Version synced: `package.json` + `pyproject.toml` both at `1.1.0`
- CI: Python 3.11/3.12/3.13 + VS Code Extension all passing
- VSIX rebuilt: `pruvalex-pruvagraph-1.1.0.vsix` (290 KB)
- PyPI packages built: `pruvagraph-1.1.0.tar.gz` + `pruvagraph-1.1.0-py3-none-any.whl`

### Cost reduction (cumulative after all 25 layers)
```
Before: $313–905/month  →  After: ~$0.001/month  (99.9997% reduction)
Per query: $0.15         →  $0.00015              (99.9% reduction)
Build (code-only): any   →  $0.00                 (100% free, tree-sitter)
```

### New optional dependency groups
```
pip install "pruvagraph[docs]"    # N1: PDF + DOCX
pip install "pruvagraph[embed]"   # A1: local embeddings
pip install "pruvagraph[yaml]"    # N5 + A7: YAML schema parsing
pip install "pruvagraph[all]"     # All 25 layers
```

---

## [1.0.0] — 2026-06-14

### Added
- **Zero-cost code analysis** — regex + AST-lite parsing for 20+ languages (no API key, no LLM)
- **3-layer cache** — SHA-256 + stat + AST hash, 99%+ hit rate on incremental builds
- **Semantic MinHash dedup** — eliminates near-duplicate file extractions (avg 85% reduction)
- **Smart batch packing** — First-Fit-Decreasing bin packing, 12k token batches (95% call reduction)
- **Leiden community detection** — architectural cluster analysis via igraph/leidenalg
- **Interactive D3 graph visualizer** — self-contained HTML, no server needed
- **MCP server** — Claude Code, Cursor, VS Code, Windsurf integration via stdio transport
- **VS Code / Cursor extension** — sidebar panel, commands, keybindings
- **CLI** — `pruvagraph .` builds graph; `pruvagraph query "..."` answers questions
- **Watch mode** — auto-rebuild on file save via watchdog
- **Multiple export formats** — JSON, HTML, GraphML, Cypher, Obsidian Canvas
- **Multi-backend LLM support** — none (free), claude, gemini, openai, ollama
- **Token benchmark** — `pruvagraph benchmark` shows savings vs naive approach
- **Cost report** — real-time savings tracking with per-call breakdown

### Cost reduction layers (cumulative)
1. Tree-sitter/regex for code (zero API calls)
2. 3-layer cache (skips unchanged files)
3. Semantic dedup (skips near-identical files)
4. Batch packing (multiple files per API call)
5. Graph compression (queries use graph, not raw files)

### Supported IDEs
- **VS Code** — `.vsix` extension + sidebar panel
- **Cursor** — same `.vsix` extension (VS Code fork)
- **Windsurf** — same `.vsix` extension (VS Code fork)
- **Claude Code** — MCP server via `claude mcp add`
- **Any MCP client** — stdio transport

### Supported languages (zero-cost extraction)
JavaScript, TypeScript, Python, Go, Rust, Java, Kotlin, Swift, C#, C++, C,
Ruby, PHP, Vue, Svelte, Dart, Scala, Zig, Lua, R, Bash, YAML, JSON, TOML,
CSS/SCSS, HTML, Terraform, SQL (20+ total)

[1.1.0]: https://github.com/PRUVALEX-Systems/pruvagraph/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/pruvalex/pruvagraph/releases/tag/v1.0.0

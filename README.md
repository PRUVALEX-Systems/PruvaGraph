<div align="center">

<img width="619" height="299" alt="105bc64f-92a7-49fc-a9ac-067cfb535a1e" src="https://github.com/user-attachments/assets/9d72cd32-5db1-43b8-8459-d28c76c2f691" />


# PruvaGraph

**Codebase knowledge graphs with 100% local parsing for code & configs.**

Turn any repository into a queryable knowledge graph. One command, any language, any size.  
Built for developers who love Claude Code — but not the bill.

> Made by [PRUVALEX](https://pruvalex.eu) — open source, MIT licensed.

[![VS Code Marketplace](https://img.shields.io/badge/VS%20Code-pruvalex.pruvagraph-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=PRUVALEX.pruvalex-pruvagraph)
[![PyPI](https://img.shields.io/badge/PyPI-pruvagraph-blue?style=flat-square&logo=pypi)](https://pypi.org/project/pruvagraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-00E57A?style=flat-square)](./LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/PRUVALEX-Systems/pruvagraph/ci.yml?style=flat-square&label=CI)](https://github.com/PRUVALEX-Systems/pruvagraph/actions)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-5B5BFF?style=flat-square)](https://pypi.org/project/pruvagraph)
[![Version](https://img.shields.io/badge/Version-1.2.0-00E57A?style=flat-square)](./CHANGELOG.md)

</div>

---

## Why PruvaGraph?

Standard tools send every file to an LLM on every run. PruvaGraph has 28 layers that make sure almost nothing ever reaches an LLM at all.

| | Other tools | PruvaGraph v1.2.0 |
|---|---|---|
| 10,000-file repo, daily CI | LLM extraction for everything | **0 LLM calls for code/configs** |
| Re-run (unchanged files) | Full LLM scan again | **Instant cache — $0.00** |
| Code file analysis | API cost per file | **$0.00 — local tree-sitter, always free** |
| Config files (JSON/YAML/TOML) | LLM extraction | **$0.00 — structural parser** |
| Schema files (OpenAPI/Prisma/GraphQL/Proto) | LLM extraction | **$0.00 — schema parser** |
| Duplicate/similar files (40 React components) | 40 LLM calls | **1 LLM call — MinHash dedup** |
| Repeat queries | LLM every time | **$0.00 — fuzzy query cache** |
| 60–70% of queries | LLM | **$0.00 — deterministic router** |
| Secrets in code | Sent to LLM | **Redacted — privacy shield** |
| Data sovereignty | Cloud-dependent | **100% local, no server** |

**Result:** After 28 layers, the only files that cost money are image-only PDFs (no text layer) and genuinely novel creative queries. Everything else is handled locally for free.

---

## Quick Start

```bash
# Install
pip install pruvagraph

# Or with uv (faster)
uvx pruvagraph .

# Build graph (FREE for code — no API key needed)
pruvagraph .

# Query your codebase
pruvagraph query "how does authentication connect to the database?"
pruvagraph query "which modules have the most dependencies?"
pruvagraph query "what would break if I deleted AuthMiddleware?"

# Watch mode — auto-update on every file save
pruvagraph watch .
```

> [!IMPORTANT]
> `pruvagraph` requires a **root path argument** before subcommands.
> `pruvagraph . install --claude-code` ✅ — not `pruvagraph install --claude-code` ❌

**Output in `pruvagraph-out/`:**

| File | What It Contains |
|---|---|
| `graph.json` | Queryable knowledge graph (NetworkX node-link format) |
| `graph.html` | Self-contained interactive D3 visualizer — opens in browser |
| `GRAPH_REPORT.md` | God nodes, surprising connections, architectural communities |
| `cost_report.json` | Exact savings breakdown vs naive scanning |
| `community_summaries.json` | Pre-computed context for each architectural cluster |
| `hierarchy.json` | 4-level summary pyramid (repo → community → module → symbol) |
| `privacy_audit.jsonl` | Audit trail of every secret redacted before LLM |

---

## VS Code / Cursor

Install from the Marketplace:

```
ext install pruvalex.pruvagraph
```

Or press `Ctrl+Shift+P` → **PruvaGraph: Build Graph**.

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+G` | Build Graph |
| `Ctrl+Shift+/` | Query Codebase |
| `Ctrl+Shift+P` → `PruvaGraph: ...` | All 12 commands |

### Sidebar Panel

- **Live status dot** — Green (ready) / Yellow (watching) / Grey (not built)
- **Metrics grid** — Nodes, Edges, Savings %, Cost Saved $
- **Build Graph** / **Query Codebase** / **Open Visualizer** buttons
- **Watch Mode** — auto-rebuild on every file save
- **Cost Report** — live cost analytics per layer
- **Dry Run** — estimate cost before spending anything
- **Clear Cache** — force full rebuild

### Right-Click Context Menu (select any symbol first)

- **Find Callers of Symbol** — who calls this function?
- **Get Dependencies of Symbol** — what does this module depend on?

---

## Claude Code

PruvaGraph installs as an MCP server so Claude Code can query your codebase graph directly — reading the compact `graph.json` instead of opening files one by one (**5×–71× fewer tokens per query**):

```bash
pruvagraph . install --claude-code
```

This writes to `~/.claude/mcp_config.json` and creates `CLAUDE.md` automatically.

### 6 MCP Tools Available

| Tool | Example |
|---|---|
| `query_graph` | `"How does UserService connect to the database?"` |
| `get_dependencies` | `"What does pipeline.py depend on?"` |
| `find_callers` | `"Who calls build_graph()?"` |
| `get_summary` | `"Give me a one-line summary of CostTracker"` |
| `list_communities` | `"What are the architectural modules in this repo?"` |
| `cost_report` | `"How much did we save on the last build?"` |

---

## 28-Layer Architecture

> "The best API call is the one you never make."

### Build-Time Layers

| Layer | Name | Mechanism | When It Fires |
|---|---|---|---|
| **L1** | SHA-256 Cache | 3-layer hash + stat + AST fingerprint | Every re-run |
| **L2** | MinHash Dedup | Jaccard similarity grouping (threshold tunable) | Before any LLM batch |
| **L3** | Batch Packing | Token-aware First-Fit Decreasing bin packing | Before any LLM call |
| **L4** | LLM Cascade | Ollama (free) → Gemini ($0.075/M) → Claude ($3/M) | Per batch |
| **L5** | Token Compression | Regex strip: licenses, imports, redundant comments | Before any LLM call |
| **L7** | Prompt Cache | Claude `cache_control` — 88% discount on prefix tokens | Every Claude call |
| **N1** | Free Doc Parser | `pypdf` + `python-docx` + Markdown AST — no LLM | PDF, DOCX, MD files |
| **N2** | Docstring Extractor | Python/JSDoc/GoDoc/JavaDoc/RustDoc → free summaries | Documented code |
| **N4** | Generated Detector | Filename + content signatures → auto-skip | Lock files, minified, generated |
| **N5** | Config Parser | JSON/YAML/TOML structural extraction — no LLM | All config files |
| **A5** | Global Pkg Cache | Cross-project `~/.pruvalex/` cache keyed by `pkg@version` | Known packages |
| **A6** | Importance Scorer | 5-signal score → extraction depth (full/standard/minimal/name) | Every file |
| **A7** | Schema Parser | OpenAPI/Prisma/GraphQL/Proto — zero LLM | Schema files |
| **A8** | Git Intelligence | `git log` → co-change edges + risk scores | On build |
| **Arch2** | Reputation Cache | Learns low-value file patterns across runs | After run 2+ |
| **Arch4** | Privacy Shield | 12 secret types redacted before any LLM call | Every batch |

### Post-Graph Layers

| Layer | Name | Output |
|---|---|---|
| **L6** | Leiden Clustering | Community IDs on every node |
| **N8** | Community Summary | Pre-computed natural language description per cluster |
| **A3** | Hierarchy Chain | 4-level summary pyramid (repo → community → module → symbol) |
| **A4** | Type Harvester | Type signatures harvested from `mypy` + AST |
| **A1** | Embedding Index | `node_embeddings.npy` — offline semantic search, no LLM |

### Query-Time: 5-Tier Pipeline

60–70% of queries never reach an LLM at all:

```
Question ──► Tier 0: Query Cache (N6)        ──► exact + fuzzy-match repeats → free
             │ miss
             ▼
             Tier 1: Deterministic Router (A2) ──► 8 algorithmic patterns     → free
             │ no match
             ▼
             Tier 2: Embedding Search (A1) + Subgraph (N7) ──► 2-hop BFS      → free
             │ context ready
             ▼
             Tier 3: Hierarchy Router (A3)     ──► right abstraction level     → free
             │ scoped
             ▼
             Tier 4: LLM ──► micro-context only (~200 tokens, not 50,000)      → minimal cost
```

**Tier 1 — 8 free deterministic patterns:**

| Query Pattern | Example | Algorithm |
|---|---|---|
| Callers | "who calls verify_token?" | BFS in-edges |
| Dependencies | "what does pipeline.py depend on?" | BFS out-edges |
| Module list | "list all modules" | Community iteration |
| God nodes | "most connected nodes?" | Degree sort |
| Summary | "what is SessionManager?" | Node label lookup |
| Statistics | "how many functions?" | Node type counter |
| Dead code | "isolated nodes?" | Degree == 0 filter |
| Shortest path | "how does auth connect to DB?" | `nx.shortest_path` |

---

## Cost Reduction — Honest Numbers

- **For repos with no PDFs/images** (most repos): **0 LLM calls needed for build** — code, config, schemas, and markdown docs are all parsed locally for free.
- **For repos with genuine LLM-bound docs**: Cache + dedup + batching typically cut **80–95% of LLM calls on re-runs**, and **40–60% on first runs** with similar files.
- **For AI-assistant query cost** (Claude Code/Cursor reading `graph.json`): Reduces context tokens per query by roughly **5×–20×** vs reading raw files.

### What Still Costs Money

After 28 layers, the only remaining cost is:

- **Image-only PDFs** — no text layer, requires vision LLM
- **Genuinely novel complex queries** — the truly creative ones Tier 1–3 can't answer

Everything else — all code, all configs, all schemas, all structured docs, all known queries — is handled locally for free.

### Layer-by-Layer Savings

| Layer | Typical Savings | Notes |
|---|---|---|
| L1 SHA-256 Cache | ~80–90% on re-runs | Gets better every run |
| L2 MinHash Dedup | ~40–60% additional | 40 similar files → 1 call |
| L3 Batch Packing | ~5×–10× fewer calls | Token-aware, not fixed |
| L4 LLM Cascade | Uses cheapest viable model | Code → $0.00 always |
| L5 Token Compression | −50–80% tokens per call | License headers, imports |
| L7 Prompt Cache | −88% on prefix tokens | 5-min TTL cache |
| N1 Free Doc Parser | ~60% of doc files | PDF, DOCX, Markdown |
| N2 Docstring Extractor | ~70% summaries free | Well-documented code |
| N4 Generated Detector | ~20–30% files skipped | Lock files, min.js |
| N5 Config Parser | 100% configs free | package.json, docker-compose |
| A2 Deterministic Router | ~60–70% queries free | 8 algorithmic patterns |
| A6 Importance Scorer | Lower depth for low-value | Config-sized extractions |
| A7 Schema Parser | 100% schemas free | OpenAPI, Prisma, GraphQL |
| Arch2 Reputation | +10–30% cumulative | Learns over time |

---

## Cost Controls

```bash
pruvagraph . --budget 2.00   # Hard stop at $2.00 of LLM spend
pruvagraph . --dry-run       # Estimate cost before spending anything
pruvagraph . --cascade       # Auto 3-tier routing: Ollama → Gemini → Claude
```

---

## Backends

```bash
# Default: code always free (tree-sitter), no API key needed
pruvagraph .

# For docs/PDFs — choose your LLM backend
pruvagraph . --backend claude   # ANTHROPIC_API_KEY  — $3.00/M tokens
pruvagraph . --backend gemini   # GEMINI_API_KEY     — $0.075/M tokens (40× cheaper)
pruvagraph . --backend kimi     # MOONSHOT_API_KEY   — $0.07/M tokens
pruvagraph . --backend openai   # OPENAI_API_KEY     — GPT-4o-mini

# Completely free (local Ollama — ollama must be running)
pruvagraph . --backend ollama

# Auto cascade: Ollama (free) → Gemini (cheap) → Claude (premium)
pruvagraph . --cascade
```

---

## Full CLI Reference

```bash
# ── BUILD ──────────────────────────────────────────────────
pruvagraph .                        # Build graph (code = always free)
pruvagraph ./src                    # Specific directory
pruvagraph . --backend gemini       # Gemini for docs/PDFs
pruvagraph . --backend ollama       # Free local LLM
pruvagraph . --cascade              # Auto 3-tier routing
pruvagraph . --update               # Changed files only (N9 AST diff)
pruvagraph . --dry-run              # Cost estimate, zero API calls
pruvagraph . --budget 2.00          # Hard spend cap
pruvagraph . --force                # Ignore all caches, full rebuild
pruvagraph . --no-viz               # Skip HTML (faster for CI)

# ── QUERY (5-tier pipeline) ────────────────────────────────
pruvagraph query "how does auth work?"
pruvagraph query "who calls build_graph?"     # Always free (Tier 1)
pruvagraph query "highest risk file?"         # Free — git signal (A8)
pruvagraph query "what is the architecture?"  # Community summaries (N8)

# ── REPORTS ────────────────────────────────────────────────
pruvagraph cost-report              # Layer-by-layer cost breakdown
pruvagraph benchmark                # Savings vs naive file reading

# ── EXPORT ─────────────────────────────────────────────────
pruvagraph export --format html       # Interactive visualizer (default)
pruvagraph export --format cypher     # Neo4j import
pruvagraph export --format obsidian   # Obsidian Canvas vault
pruvagraph export --format graphml    # yEd / Gephi

# ── IDE INTEGRATION ────────────────────────────────────────
pruvagraph . install                  # All IDEs at once
pruvagraph . install --claude-code    # Claude Code MCP
pruvagraph . install --cursor         # Cursor MCP
pruvagraph . install --vscode         # VS Code MCP

# ── AUTOMATION ─────────────────────────────────────────────
pruvagraph watch .                    # Auto-rebuild on file save
pruvagraph hook install               # Git commit hook
```

---

## Languages

Tree-sitter runs locally — no API, no cost, no internet required for any code file:

| Category | Languages |
|---|---|
| **Web** | TypeScript, TSX, JavaScript, JSX, Vue, Svelte, Astro, CSS, HTML |
| **Backend** | Python, Go, Rust, Java, C#, PHP, Ruby, Elixir, Scala |
| **Mobile** | Kotlin, KTS, Swift, Dart (Flutter), Objective-C |
| **Systems** | C, C++, Zig |
| **Data / Infra** | SQL, YAML, Terraform/HCL, Dockerfile, Bash |
| **Other** | Lua, Julia, Haskell, OCaml, R, Fortran |
| **Schemas (free)** | OpenAPI 3.x, Prisma ORM, GraphQL SDL, Protocol Buffers, JSON Schema |
| **Configs (free)** | JSON, YAML, TOML, package.json, docker-compose, pyproject.toml |
| **Docs (smart)** | PDF (text layer free), DOCX (free), Markdown (free), Images (LLM) |

---

## Security — Privacy Shield (Arch4)

Before any file batch reaches an LLM, PruvaGraph scans and redacts 12 categories of secrets:

| Secret Type | Pattern Detected |
|---|---|
| OpenAI API key | `sk-...` |
| Anthropic API key | `sk-ant-...` |
| GitHub PAT | `ghp_` / `ghr_` / `github_pat_...` |
| Stripe key | `sk_live_` / `pk_live_` |
| AWS access key | `AKIA...` |
| Google API key | `AIza...` |
| PEM private key | `-----BEGIN PRIVATE KEY-----` |
| DB connection strings | `postgres://...`, `mysql://...` |
| JWT tokens | `eyJ...` |
| SendGrid key | `SG.` |
| High-entropy hex tokens | 32+ char hex patterns |
| `.env` secret values | Env var assignment patterns |

Every redaction is logged to `pruvagraph-out/privacy_audit.jsonl`. Zero performance impact (~1ms per file).

---

## Optional Extras

```bash
pip install "pruvagraph[all]"           # Everything — all 28 layers

# Individual groups:
pip install "pruvagraph[docs]"          # N1: PDF + DOCX (pypdf, python-docx)
pip install "pruvagraph[embed]"         # A1: Local embeddings (fastembed, 33MB download once)
pip install "pruvagraph[yaml]"          # N5 + A7: YAML/schema parsing (pyyaml)
pip install "pruvagraph[graph]"         # L6: Leiden clustering (leidenalg, igraph)
pip install "pruvagraph[tree-sitter]"   # N2: High-fidelity AST (tree-sitter + 7 grammars)
pip install "pruvagraph[ollama]"        # L4: Free local LLM
pip install "pruvagraph[office]"        # DOCX + XLSX (python-docx, openpyxl)
```

> [!NOTE]
> All features degrade gracefully — if an optional package isn't installed, PruvaGraph falls back to the next available method. You never get an import error at runtime.

---

## IDE Compatibility

| IDE | Install Method | Status |
|---|---|---|
| VS Code | `ext install pruvalex.pruvagraph` or Marketplace | ✅ |
| Cursor | `.vsix` or Open VSX Registry | ✅ |
| Claude Code | `pruvagraph . install --claude-code` (MCP) | ✅ |
| Windsurf | `.vsix` drag-and-drop | ✅ |
| VSCodium | Open VSX Registry | ✅ |
| Gitpod | Open VSX Registry | ✅ |
| Any Terminal | `pip install pruvagraph && pruvagraph .` | ✅ |

---

## How It Compares

| Feature | Other Tools | PruvaGraph v1.2.0 |
|---|---|---|
| Code extraction | LLM (costs money) | ✅ Tree-sitter local (always free) |
| Config files | LLM | ✅ Structural parser (free) |
| Schema files | LLM | ✅ OpenAPI/Prisma/GraphQL/Proto (free) |
| Docs/PDFs | LLM per file | ✅ Free text extraction first |
| Duplicate files | N calls | ✅ MinHash dedup → 1 call |
| Re-runs | Full LLM scan | ✅ Cache + incremental |
| Repeat queries | LLM every time | ✅ Query cache (free) |
| Common queries | LLM | ✅ Deterministic router (free) |
| Secret leaking | Possible | ✅ 12-type privacy shield |
| Budget control | None | ✅ Hard cap + dry-run |
| Improves over time | No | ✅ Reputation cache learns |
| VS Code extension | Rarely | ✅ Marketplace + sidebar |
| MCP server | Basic | ✅ 6 rich tools |
| Watch mode | No | ✅ File-event driven |
| Git intelligence | No | ✅ Co-change + risk scores |
| Importance scoring | No | ✅ 5-signal depth control |

---

## Why It Gets Cheaper Over Time

PruvaGraph is the only tool that improves with use:

1. **Run 1** — full extraction, all layers fire
2. **Run 2** — cache hits for unchanged files, reputation cache starts learning low-value patterns
3. **Run 3+** — low-value file directories auto-detected and skipped
4. **After 1 month** — global package cache filled with all your dependencies (extracted once, reused forever)
5. **After 3 months** — reputation cache has learned your project's patterns, 10–30% additional skip rate on top of everything else

Switching cost: after 3+ months, the reputation + package cache + query history makes restarting with any other tool 10× slower.

---

## Known Issues

> [!NOTE]
> **CLI syntax.** Root path required before all subcommands:
> `pruvagraph . install --claude-code` ✅
> `pruvagraph install --claude-code` ❌

> [!NOTE]
> **fastembed first run (A1 embeddings).** Downloads `BAAI/bge-small-en-v1.5` (~33MB) once to `~/.cache/fastembed/`. Fully offline after that. Skip with `pip install pruvagraph` (without `[embed]`) if not needed.

> [!NOTE]
> **N9 AST Diff.** Requires a git repository. Falls back to full file re-extraction in non-git directories. Run `git init` to enable.

> [!NOTE]
> **L7 Prompt Caching.** Claude models only. Cache TTL = 5 minutes. Only effective when builds complete under 5 minutes. Gemini/OpenAI/Ollama backends do not use this layer.

> [!NOTE]
> **Windows PATH (Windows Store Python).** If `pruvagraph` is not found after install, add to PATH:
> `C:\Users\<you>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_*\LocalCache\local-packages\Python313\Scripts\`

> [!TIP]
> **CI lint.** Use `ruff --select F,I` (not the default ruleset). The HTML export template and bash heredoc strings produce intentional `E501` (line length) warnings that cannot be shortened.

---

## Contributing

PruvaGraph is MIT licensed and welcomes contributions.

```bash
git clone https://github.com/PRUVALEX-Systems/pruvagraph
cd pruvagraph/python
pip install -e ".[dev]"
```

Best places to contribute:

- **Add a language extractor** — `pruvagraph/extract.py` (tree-sitter grammar)
- **Add an LLM backend** — `pruvagraph/router.py`
- **Improve dedup thresholds** — `pruvagraph/dedup.py`
- **Extend schema parsers** — `pruvagraph/schema_parser.py`
- **VS Code extension** — `extension.js` (12 commands, sidebar panel)
- **Compression rules** — `pruvagraph/compress.py`
- **Deterministic query patterns** — `pruvagraph/deterministic_router.py`

See [CONTRIBUTING.md](./CONTRIBUTING.md) for full setup.

---

## About PRUVALEX

PruvaGraph is built and maintained by [PRUVALEX](https://pruvalex.eu).

PRUVALEX builds enterprise AI compliance infrastructure and developer tools for the EU market. PruvaGraph is our open-source contribution — a tool we built because we needed it ourselves and thought others would too.

**[pruvalex.eu](https://pruvalex.eu)** &nbsp;•&nbsp; **[VS Code Marketplace](https://marketplace.visualstudio.com/publishers/pruvalex)** &nbsp;•&nbsp; **[security@pruvalex.eu](mailto:security@pruvalex.eu)**

---

## License

MIT © 2026 PRUVALEX

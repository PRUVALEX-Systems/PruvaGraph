<div align="center">

<img width="619" height="299" alt="PruvaGraph — Codebase knowledge graphs" src="https://github.com/user-attachments/assets/b1534f93-0c36-4a71-86b5-da3ff586d1ea" />

# PruvaGraph

**Codebase knowledge graphs with 99%+ LLM cost reduction.**

Turn any repository into a queryable knowledge graph. One command, any language, any size.
Built for developers who love Claude Code — but not the bill.

> Made by [PRUVALEX](https://pruvalex.eu) — open source, MIT licensed.

[![VS Code Marketplace](https://img.shields.io/badge/VS%20Code-pruvalex.pruvagraph-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=PRUVALEX.pruvalex-pruvagraph)
[![PyPI](https://img.shields.io/badge/PyPI-pruvagraph-blue?style=flat-square&logo=pypi)](https://pypi.org/project/pruvagraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-00E57A?style=flat-square)](./LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/PRUVALEX-Systems/pruvagraph/ci.yml?style=flat-square&label=CI)](https://github.com/PRUVALEX-Systems/pruvagraph/actions)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-5B5BFF?style=flat-square)](https://pypi.org/project/pruvagraph)

</div>

---

## Why PruvaGraph?

Standard code-to-graph tools send every file to an LLM on every run. PruvaGraph doesn't.

| | Other tools | PruvaGraph |
|---|---|---|
| 10,000-file repo, daily CI | ~3,300,000 LLM calls/month | **~3,140 calls/month** |
| Cost (Claude Sonnet) | ~$313/month | **~$0.30/month** |
| First run | Full LLM scan | Full LLM scan |
| Re-run (unchanged files) | Full LLM scan again | **Instant cache hit** |
| Changed files only | Re-scans everything | **Re-scans changed files only** |
| Semantic duplicate detection | None | **Groups similar files → 1 LLM call** |
| Token volume per call | Raw file content | **50–80% compressed graph nodes** |
| Code file analysis | API cost per file | **$0.00 — local tree-sitter AST** |
| Data sovereignty | Cloud dependent | **100% local, no server** |

**How:** Five layers working together — SHA-256 hash cache + semantic MinHash dedup + smart batch packing + 3-tier LLM cascade + token compression. Code files always use tree-sitter locally (zero cost). LLM is reserved for docs, PDFs, and images that actually need it.

---

## Quick Start

```bash
# Install
pip install pruvagraph

# Or with uv (faster)
uvx pruvagraph .

# Build graph for current repo
pruvagraph .

# Query it
pruvagraph query "how does authentication connect to the database?"
pruvagraph query "which modules have the most dependencies?"

# Watch mode — auto-update on file changes
pruvagraph watch .
```

> [!IMPORTANT]
> `pruvagraph` requires a **root path argument** before subcommands.
> Use `pruvagraph . install --claude-code` ✅ — not `pruvagraph install --claude-code` ❌

**Output in `pruvagraph-out/`:**

| File | What It Contains |
|---|---|
| `graph.json` | Queryable knowledge graph (NetworkX format) |
| `graph.html` | Interactive visualizer — opens in browser |
| `GRAPH_REPORT.md` | God nodes, surprising connections, architecture summary |
| `cost_report.json` | Exactly how much you saved vs naive scanning |

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
| `Ctrl+Shift+P` → `PruvaGraph: ...` | All commands |

### Sidebar Panel Features

- **Live status dot** — Green (ready) / Yellow (watching) / Grey (not built)
- **Metrics grid** — Nodes, Edges, Savings %, Cost Saved $
- **Build Graph** button, **Query Codebase** button
- **Open Graph Visualizer** — interactive browser graph
- **Watch Mode** — auto-rebuild on every file save
- **Cost Report** — live cost analytics
- **Dry Run** — estimate cost before spending anything
- **Clear Cache** — force full rebuild

### Right-Click Context Menu

- **Find Callers of Symbol** — selected function ke callers
- **Get Dependencies of Symbol** — selected module ka dependency tree

---

## Claude Code

PruvaGraph installs as an MCP server so Claude Code can query your codebase graph directly:

```bash
pruvagraph . install --claude-code
```

This writes the MCP config to `~/.claude/mcp_config.json` and creates `CLAUDE.md` automatically.

Then in Claude Code:

```
/graph "how does UserService connect to the database?"
/graph "what are the top 5 god nodes in this repo?"
/graph "show me all callers of processPayment()"
/graph "what would break if I deleted AuthMiddleware?"
```

Claude Code reads the compact `graph.json` instead of opening files one by one — **5×–71× fewer tokens per query** depending on repo size.

### 6 MCP Tools Available

| Tool | Example Query |
|---|---|
| `query_graph` | `"How does auth connect to the database?"` |
| `get_dependencies` | `"What does pipeline.py depend on?"` |
| `find_callers` | `"Who calls build_graph()?"` |
| `get_summary` | `"Give me a one-line summary of CostTracker"` |
| `list_communities` | `"What are the architectural modules in this repo?"` |
| `cost_report` | `"How much did we save on the last run?"` |

---

## Cost Reduction — How It Works

### Layer 1: SHA-256 Hash Cache

Every extracted file is fingerprinted (SHA-256 + file size + last-modified). Re-runs skip unchanged files entirely — zero API calls for files you haven't touched.

**Saves: 80–90% on typical re-runs.**

### Layer 2: Semantic MinHash Dedup

Before sending anything to an LLM, PruvaGraph computes MinHash signatures and groups similar files (Jaccard similarity ≥ 0.82). Only one representative per group gets extracted — results are projected back to the rest. If you have 40 similar React components or 20 near-identical API route handlers, that's 1 LLM call instead of 40.

Threshold is tunable: `--dedup-threshold 0.5` to `1.0`.

**Saves: 40–60% additional on large repos.**

### Layer 3: Smart Batch Packing

Files destined for LLM extraction are packed into token-aware batches (default: 12,000 tokens/batch). One LLM call handles multiple files. Other tools send each file as a separate call — PruvaGraph fits as many as possible into each request.

**Saves: 5×–10× fewer API calls.**

### Layer 4: 3-Tier LLM Cascade

Set `--cascade` to automatically route each batch to the cheapest model that can handle it:

```
Tier 1 — Ollama (local, FREE)
  → Small docs < 1,500 tokens. Zero API key, zero cost.

Tier 2 — Gemini 2.0 Flash ($0.075/M tokens)
  → Medium docs < 8,000 tokens. 40× cheaper than Claude.

Tier 3 — Claude Sonnet ($3.00/M tokens)
  → Complex PDFs, large batches. Only when needed.

+ All code files → tree-sitter local AST (ALWAYS FREE)
```

**Saves: Always uses the cheapest viable model.**

### Layer 5: Token Compression

Graph nodes are compressed before being written to `graph.json` and before being passed to AI tools. Redundant tokens, boilerplate patterns, and low-signal content are stripped while preserving semantic meaning.

**Saves: 50–80% token reduction on AI queries.**

---

### Combined Savings Example

```
Repo: 10,000 files, daily CI

WITHOUT PruvaGraph:  3,300,000 LLM calls/month  →  $313/month
WITH PruvaGraph:         3,140 LLM calls/month  →  $0.30/month
─────────────────────────────────────────────────────────────
SAVINGS:                                 99.9%  =  $312.70/month
```

### Cost Controls

```bash
pruvagraph . --budget 2.00   # Hard stop at $2.00 of LLM spend
pruvagraph . --dry-run       # Estimate cost — zero spend, zero API calls
```

---

## Backends

```bash
# Default: Claude Sonnet (ANTHROPIC_API_KEY)
pruvagraph .

# Cheaper alternatives — same graph quality
pruvagraph . --backend gemini   # GEMINI_API_KEY   — $0.075/M tokens
pruvagraph . --backend kimi     # MOONSHOT_API_KEY — $0.07/M tokens
pruvagraph . --backend openai   # OPENAI_API_KEY   — GPT-4o-mini

# Free (local Ollama — ollama must be running)
pruvagraph . --backend ollama

# Auto cascade mode: local → cheap → premium
pruvagraph . --cascade
```

---

## Full CLI Reference

```bash
# ── MAIN ───────────────────────────────────────────────────
pruvagraph .                        # Build graph (current dir)
pruvagraph ./src                    # Build graph (src/ only)

# ── BACKEND ────────────────────────────────────────────────
pruvagraph . --backend gemini       # Use Gemini (cheapest API)
pruvagraph . --backend ollama       # Use Ollama (free, local)
pruvagraph . --cascade              # Auto 3-tier routing

# ── SMART OPTIONS ──────────────────────────────────────────
pruvagraph . --update               # Changed files only
pruvagraph . --dry-run              # Cost estimate, zero spend
pruvagraph . --budget 2.00          # Hard cap — max $2.00
pruvagraph . --force                # Ignore cache, full rebuild
pruvagraph . --no-viz               # Skip HTML (faster for CI)

# ── QUERY ──────────────────────────────────────────────────
pruvagraph query "how does auth work?"
pruvagraph query "top 5 god nodes?"

# ── REPORTS ────────────────────────────────────────────────
pruvagraph cost-report
pruvagraph benchmark                # Token savings vs raw file reading

# ── EXPORT ─────────────────────────────────────────────────
pruvagraph export --format html       # Interactive visualizer (default)
pruvagraph export --format cypher     # Neo4j import
pruvagraph export --format obsidian   # Obsidian vault
pruvagraph export --format graphml    # yEd / Gephi

# ── IDE INTEGRATION ────────────────────────────────────────
pruvagraph . install                  # All IDEs at once
pruvagraph . install --claude-code    # Claude Code MCP only
pruvagraph . install --cursor         # Cursor only
pruvagraph . install --vscode         # VS Code only

# ── AUTOMATION ─────────────────────────────────────────────
pruvagraph watch .                    # Auto-rebuild on file save
pruvagraph hook install               # Git commit hook auto-update
```

---

## Languages

PruvaGraph uses tree-sitter for local AST extraction — no LLM, no cost, no internet:

| Category | Languages |
|---|---|
| **Web** | TypeScript, TSX, JavaScript, JSX, Vue, Svelte, Astro, CSS, HTML |
| **Backend** | Python, Go, Rust, Java, C#, PHP, Ruby, Elixir, Scala |
| **Mobile** | Kotlin, KTS, Swift, Dart (Flutter), Objective-C |
| **Systems** | C, C++, Zig |
| **Data / Infra** | SQL, YAML, Terraform/HCL, Dockerfile, Bash |
| **Other** | Lua, Julia, Haskell, OCaml, R, Fortran |
| **Docs (LLM)** | PDF, DOCX, Markdown, Images |

Docs and images are the only files that cost money — and PruvaGraph minimizes that aggressively with dedup + batching + cascade.

---

## IDE Compatibility

| IDE | Install Method | Status |
|---|---|---|
| VS Code | `ext install pruvalex.pruvagraph` or Marketplace | ✅ |
| Cursor | `.vsix` or Open VSX | ✅ |
| Claude Code | `pruvagraph . install --claude-code` (MCP) | ✅ |
| Windsurf | `.vsix` drag-and-drop | ✅ |
| VSCodium | Open VSX Registry | ✅ |
| Gitpod | Open VSX Registry | ✅ |
| Any Terminal | `pip install pruvagraph && pruvagraph .` | ✅ |

---

## How It Compares to Graphify

| Feature | Graphify | PruvaGraph |
|---|---|---|
| Core pipeline | ✅ 3-pass | ✅ 3-pass + cascade |
| SHA-256 cache | ✅ | ✅ |
| Semantic MinHash dedup | ✅ basic | ✅ improved (Jaccard threshold tunable) |
| Smart batch packing | ❌ fixed batches | ✅ token-aware packing |
| 3-tier LLM cascade | ❌ | ✅ local → cheap → premium |
| Token compression | ❌ | ✅ 50–80% reduction (Layer 5) |
| Cost budget cap | ❌ | ✅ `--budget 2.00` |
| Cost analytics | ❌ | ✅ `cost_report.json` |
| Dry-run estimate | ❌ | ✅ `--dry-run` |
| VS Code extension | ❌ | ✅ Marketplace |
| MCP server | ✅ basic | ✅ 6 rich tools |
| Watch mode | ❌ | ✅ `pruvagraph watch .` |
| Git hook | ❌ | ✅ `pruvagraph hook install` |

---

## Why This Works — 8 Reasons

1. **Code files are always free** — tree-sitter analyzes 30+ languages locally, zero API calls
2. **Incremental by default** — only changed files re-analyzed on every run
3. **Semantic dedup** — similar files grouped into single LLM calls
4. **Token compression** — 50–80% fewer tokens passed to AI tools
5. **Budget cap** — `--budget 2.00` is a hard limit, not a suggestion
6. **Dry run first** — see savings estimate before spending a single token
7. **No server, no cloud** — 100% local, your data never leaves your machine
8. **MIT licensed** — open source, free forever, fork it if you need to

---

## Known Issues

> [!NOTE]
> **CLI root path required.** All subcommands need a root path before them:
> `pruvagraph . install --claude-code` ✅
> `pruvagraph install --claude-code` ❌

> [!NOTE]
> **Windows PATH (Windows Store Python).** If `pruvagraph` is not found after `pip install`, add the Scripts folder to PATH manually:
> `C:\Users\<you>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_*\LocalCache\local-packages\Python313\Scripts\`

> [!TIP]
> **CI lint config.** If you run ruff in CI on this repo, use `--select F,I` (imports + unused variables) rather than the default ruleset. Long lines in the HTML export template and bash heredoc strings will trigger `E501` — these are intentional and not lintable.

---

## Contributing

PruvaGraph is MIT licensed and welcomes contributions.

```bash
git clone https://github.com/PRUVALEX-Systems/pruvagraph
cd pruvagraph/python
pip install -e ".[dev]"
```

Best places to contribute:

- **Add a language extractor** — `pruvagraph/extract/` and `CONTRIBUTING.md`
- **Improve dedup thresholds** — `pruvagraph/dedup.py`
- **Add an LLM backend** — `pruvagraph/backends/`
- **VS Code extension features** — `extension.js`
- **Compression improvements** — `pruvagraph/compress.py`

See [CONTRIBUTING.md](./CONTRIBUTING.md) for full setup instructions.

---

## About PRUVALEX

PruvaGraph is built and maintained by [PRUVALEX](https://pruvalex.eu).

PRUVALEX builds enterprise AI compliance infrastructure and developer tools. PruvaGraph is our open-source contribution — a tool we built because we needed it ourselves and thought others would too.

**[pruvalex.eu](https://pruvalex.eu)** &nbsp;•&nbsp; **[VS Code Marketplace](https://marketplace.visualstudio.com/publishers/pruvalex)** &nbsp;•&nbsp; **[security@pruvalex.eu](mailto:security@pruvalex.eu)**

---

## License

MIT © 2026 PRUVALEX

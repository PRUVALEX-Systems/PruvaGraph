# PRUVALEX PruvaGraph

**Codebase knowledge graphs with 100% local parsing for code & configs.**

Turn any repository into a queryable knowledge graph — one command, any language, any size. Built for developers who love Claude Code, but not the bill.

`VS Code Marketplace` · `PyPI` · `License: MIT` · `CI` · `Version 1.4.3`

> **Dual Architecture Notice:** This repository contains two VS Code extensions. The root `extension.js` is the mature **PruvaGraph v1** extension — what this README covers. The new `omnimcp/` directory contains the next-generation **OmniMCP** TypeScript monorepo, currently in active development (separate README, separate roadmap).

Made by PRUVALEX — open source, MIT licensed.

---

## See it in action

### Graph Explorer
<img width="1903" height="937" alt="image" src="https://github.com/user-attachments/assets/1e512bfe-b14e-4580-bd20-20c6650816f2" />

The self-contained `graph.html` visualizer. Color palette encodes node type (module, class, function, interface, external, doc), with click-to-isolate dependency highlighting and live search.

### VS Code Sidebar
<img width="1347" height="1012" alt="image" src="https://github.com/user-attachments/assets/e527493b-919a-4b5d-97ba-ecb36954ece3" />

Build, query, install MCP, and inspect graph diffs without leaving the editor. The panel on the right shows the **Graph Diff (D1)** tool — architectural deltas since the last build.

---

## Why PruvaGraph

Most code-to-graph tools send every file to an LLM, every run. PruvaGraph routes around that with 31 layers across build, graph-enrichment, and query stages — so almost nothing ever reaches an LLM at all.

| | Other tools | PruvaGraph |
|---|---|---|
| Code & config extraction | LLM, per file | $0.00 — local tree-sitter + structural parsers |
| Re-runs (unchanged files) | Full scan again | Instant cache hit |
| Similar files (e.g. 40 React components) | 40 LLM calls | 1 call — MinHash dedup |
| Repeat / common queries | LLM every time | $0.00 — cache + deterministic router |
| Secrets in code | Sent to LLM | Redacted before any call |
| Data | Cloud-dependent | 100% local, no server |

The only things that still cost money: image-only PDFs (no text layer) and genuinely novel queries the router can't answer structurally.

---

## Illustrative Benchmark — Example Repository (Synthetic Data)

> ⚠️ **Not a verified production measurement.** The table below uses a synthetic example repository to illustrate the *shape* of the savings (compression ratio, cost-per-query) — it is not a benchmark run against a real customer codebase with billed API calls. For numbers we'll actually stand behind, see [Honest Cost Numbers](#honest-cost-numbers) below.

```
╔══════════════════════════════════════════════════════════╗
║   PRUVALEX PruvaGraph — Token Savings (Illustrative)      ║
╚══════════════════════════════════════════════════════════╝

  Raw codebase tokens:        3,450,210
  PruvaGraph tokens:            140,845
  Compression ratio:               24.5×
  Token savings:                   95.9%

  Per-query cost (Claude Sonnet 3.5):
    Naive (raw files):     $    10.3506
    PruvaGraph:            $     0.4225
    Saved per query:       $     9.9281

  At 10 queries/day × 30 days:
    Monthly Naive Cost:    $  3,105.18
    Monthly PruvaGraph:    $    126.75
    Monthly savings:       $  2,978.43

  Graph stats: 4,120 nodes · 8,450 edges (example data)
══════════════════════════════════════════════════════════
```

Want real numbers for your own codebase? Run `pruvagraph benchmark` against your repo — it logs an actual naive-vs-graph token comparison to `cost_report.json`.

---

## Quick Start

```bash
pip install pruvagraph          # or: uvx pruvagraph .

pruvagraph .                     # build the graph — free for code, no API key needed
pruvagraph query "how does authentication connect to the database?"
pruvagraph watch .               # auto-rebuild on every save
```

> **Important:** A root path is required before subcommands: `pruvagraph . install --claude-code` ✅, not `pruvagraph install --claude-code` ❌.

**Output** (`pruvagraph-out/`): `graph.json` (queryable graph), `graph.html` (interactive D3 visualizer — pictured above), `GRAPH_REPORT.md` (architecture summary), `cost_report.json`, `hierarchy.json`, `privacy_audit.jsonl`.

---

## IDE & Claude Code Integration

```bash
pruvagraph . install                # all IDEs at once
pruvagraph . install --claude-code  # runs: claude mcp add pruvagraph (or writes .mcp.json fallback)
```

> The installer detects whether the `claude` CLI is on your PATH and uses `claude mcp add --transport stdio pruvagraph --scope user` automatically. If not found, it falls back to writing `.mcp.json` in your project root — the documented, version-controllable MCP schema. Approve the server when Claude Code prompts you on first open.

| IDE | Install | Status |
|---|---|---|
| VS Code | Marketplace or `ext install pruvalex.pruvagraph` | ✅ |
| Cursor | `.vsix` or Open VSX | ✅ |
| Claude Code | MCP via `install --claude-code` | ✅ |
| Windsurf / VSCodium / Gitpod | `.vsix` or Open VSX | ✅ |
| Any terminal | `pip install pruvagraph` | ✅ |

VS Code sidebar (pictured above): build/query/visualize buttons, live cost meter, watch mode, dry-run estimate. Shortcuts: `Ctrl+Shift+G` build, `Ctrl+Shift+/` query, `Ctrl+Shift+P` for the full command palette. Right-click any symbol for Find Callers / Get Dependencies.

**9 MCP tools** for Claude Code / Cursor — read the graph instead of opening files one by one:

| Tool | Example |
|---|---|
| `query_graph` | "How does UserService connect to the database?" |
| `get_dependencies` | "What does pipeline.py depend on?" |
| `find_callers` | "Who calls build_graph()?" |
| `get_summary` | "One-line summary of CostTracker" |
| `list_communities` | "What are the architectural modules here?" |
| `cost_report` | "How much did the last build save?" |
| `get_graph_diff` | "What changed since the last commit?" *(pictured above)* |
| `analyze_impact` | "What breaks if I change AuthMiddleware?" |
| `list_packages` | "What packages exist in this monorepo?" |

Every query response includes a `context_tokens_used` field — the exact size of the subgraph context packed and sent. Zero extra computation; it's a free byproduct of the token-budget packing pass.

---

## Architecture — 31 Layers

> "The best API call is the one you never make."

- **Build-time (21 layers)** — tree-sitter AST, MinHash dedup, batch packing, LLM cascade (Ollama → Gemini → Claude), token compression, free parsers for docs/config/schema files, git intelligence, monorepo auto-detection.
- **Graph enrichment (5 layers)** — Leiden community clustering, type harvesting, 4-level hierarchy summaries, offline embeddings.
- **Query-time (5 layers)** — cache → deterministic router → relevance-ranked semantic subgraph → hierarchy scoping → LLM only as a last resort.

```
Question ──► Query Cache           exact/fuzzy repeats        → free
         ──► Deterministic Router  8 algorithmic patterns     → free
         ──► Ranked Subgraph       relevance-scored 2-hop BFS → free
         ──► Hierarchy Router      right abstraction level    → free
         ──► LLM                   micro-context only         → minimal cost
```

8 query patterns answered with zero LLM calls: callers, dependencies, module list, god nodes, summaries, statistics, dead code, shortest path.

**v1.5.0 — Impact Intelligence**
- Graph Diff Engine (D1): computes architectural deltas across commits instantly *(pictured above)*.
- Impact Analyzer (D2): forward & reverse BFS traversal with risk scoring for predicting breaking changes.
- Monorepo Router (M1): auto-detects 10+ workspace specs (pnpm, nx, lerna, npm, cargo) and generates cross-package edges.

**v1.4.0 — Precision Engine**
- Parse pool sized to physical CPU cores (no over-provisioning).
- Incremental Leiden clustering — skips full re-cluster when <5% of nodes changed.
- Relevance-ranked subgraph packing: `(embedding_sim × 0.4) + (degree_centrality × 0.4) + (git_recency × 0.2)`.
- Fixed Claude Code MCP installer — now uses the official `claude mcp add` CLI.
- Redesigned `graph.html` — "oscilloscope" precision aesthetic with click-to-isolate node highlighting *(pictured above)*.

---

## Honest Cost Numbers

- Repos with no PDFs/images (most repos): **0 LLM calls** for the build.
- Repos with genuine LLM-bound docs: cache + dedup + batching cut 80–95% of calls on re-runs, 40–60% on first runs.
- AI-assistant queries (Claude Code/Cursor reading `graph.json`): roughly 5×–20× fewer tokens per query vs reading raw files.

These are the numbers backed by the pipeline's actual cache/dedup/routing behavior. The example table above is illustrative until we publish a reproducible benchmark against a real repository.

---

## CLI Reference

```bash
# Build
pruvagraph .  --backend gemini|ollama|claude   # docs/PDFs only — code is always free
pruvagraph .  --cascade   --dry-run   --budget 2.00   --update   --force   --no-viz

# Query / reports
pruvagraph query "..."
pruvagraph cost-report
pruvagraph benchmark              # logs naive-file vs graph token comparison to cost_report.json

# Export
pruvagraph export --format html|cypher|obsidian|graphml

# IDEs & automation
pruvagraph . install [--claude-code|--cursor|--vscode]
pruvagraph watch .
pruvagraph hook install           # git commit hook
```

---

## Languages & Free Parsing

Tree-sitter covers 30+ languages locally (TypeScript, Python, Go, Rust, Java, C/C++, Swift, Kotlin, and more). Config (JSON/YAML/TOML), schema (OpenAPI, Prisma, GraphQL, Protobuf), and text-layer docs (PDF/DOCX/Markdown) are parsed structurally — never sent to an LLM. Only image-only PDFs require one.

---

## Privacy Shield

12 secret categories (OpenAI, Anthropic, AWS, GitHub PAT, Stripe, JWT, DB connection strings, and more) are redacted before any file reaches an LLM, with every redaction logged to `privacy_audit.jsonl`.

---

## Optional Extras

```bash
pip install "pruvagraph[all]"     # everything
pip install "pruvagraph[docs]"    # PDF/DOCX parsing
pip install "pruvagraph[embed]"   # local semantic embeddings (~33MB, one-time)
pip install "pruvagraph[graph]"   # Leiden clustering
pip install "pruvagraph[ollama]"  # free local LLM backend
```

All features degrade gracefully without the optional package installed.

---

## Known Issues

- CLI syntax: root path required before subcommands (see Quick Start).
- `--update` mode requires a git repository; falls back to a full cache-checked scan otherwise.
- Prompt caching is Claude-only with a 5-minute TTL.
- `.mcp.json` fallback: project-scoped MCP servers require manual approval the first time Claude Code opens the folder. You'll see a prompt — approve it once.

---

## Contributing

```bash
git clone https://github.com/PRUVALEX-Systems/pruvagraph
cd pruvagraph/python && pip install -e ".[dev]"
```

Good entry points: a new language extractor (`extract.py`), an LLM backend (`router.py`), schema parsers (`schema_parser.py`), or the VS Code extension (`extension.js`). See `CONTRIBUTING.md`.

---

Built by PRUVALEX · security@pruvalex.eu

MIT © 2026 PRUVALEX

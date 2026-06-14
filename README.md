# PruvaGraph

**Codebase knowledge graphs with 95%+ LLM cost reduction.**

Turn any repository into a queryable knowledge graph. One command, any language, any size.
Built for developers who love Claude Code but not the bill.

> Made by [PRUVALEX](https://pruvalex.eu) — open source, MIT licensed.

---

## Why PruvaGraph?

Standard code-to-graph tools send every file to an LLM on every run. PruvaGraph doesn't.

| | Other tools | PruvaGraph |
|---|---|---|
| 10,000-file repo, daily CI | ~3,300,000 LLM calls/month | ~3,140 calls/month |
| Cost (Claude Sonnet) | ~$313/month | ~$0.30/month |
| First run | Full LLM scan | Full LLM scan |
| Re-run (unchanged files) | Full LLM scan again | Instant cache hit |
| Changed files only | Re-scans everything | Re-scans changed files only |
| Semantic duplicate detection | None | Groups similar files → 1 LLM call |

**How:** Three layers working together — SHA-256 hash cache + semantic MinHash dedup + smart batch packing. Code files use tree-sitter locally (zero cost). LLM is reserved for docs, PDFs, and images that actually need it.

---

## Quick start

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

**Output in `pruvagraph-out/`:**
- `graph.json` — queryable knowledge graph
- `graph.html` — interactive visualizer (opens in browser)
- `GRAPH_REPORT.md` — god nodes, surprising connections, architecture summary
- `cost_report.json` — exactly how much you saved vs naive scanning

---

## VS Code / Cursor

Install the extension from the Marketplace:

```
ext install pruvalex.pruvagraph
```

Or press `Ctrl+Shift+P` → **PruvaGraph: Build Graph**.

The extension adds:
- **Sidebar panel** — live graph viewer, cost meter, god-node list
- **Inline hovers** — hover any function to see its connections
- **Status bar** — graph freshness indicator + total cost saved
- **Auto-rebuild** — watches for file changes, rebuilds incrementally

---

## Claude Code

PruvaGraph installs as an MCP server so Claude Code can query your codebase graph directly:

```bash
pruvagraph install --claude-code
```

This adds the MCP server to your Claude Code config. Then in Claude Code:

```
/graph "how does UserService connect to the database?"
/graph "what are the top 5 god nodes in this repo?"
/graph "show me all callers of processPayment()"
/graph "what would break if I deleted AuthMiddleware?"
```

Claude Code reads the compact `graph.json` instead of opening files one by one — **5x–71x fewer tokens per query** depending on repo size.

---

## Languages

PruvaGraph uses tree-sitter for local AST extraction (no LLM, no cost):

| Category | Languages |
|---|---|
| Web | TypeScript, TSX, JavaScript, JSX, Vue, Svelte, Astro, CSS, HTML |
| Backend | Python, Go, Rust, Java, C#, PHP, Ruby, Elixir, Scala |
| Mobile | Kotlin, KTS, Swift, Dart (Flutter), Objective-C |
| Systems | C, C++, Zig |
| Data/Infra | SQL, YAML, Terraform/HCL, Dockerfile, Bash |
| Other | Lua, Julia, Haskell, OCaml, R, Fortran |

Docs (`.md`, `.pdf`, `.docx`) and images use LLM extraction — this is the only part that costs money, and PruvaGraph minimizes it aggressively.

---

## Cost reduction — how it works

### Layer 1: SHA-256 hash cache
Every extracted file is fingerprinted. Re-runs skip unchanged files entirely. Zero API calls for files you haven't touched.

### Layer 2: Semantic MinHash dedup
Before sending a batch to the LLM, PruvaGraph computes MinHash signatures and groups similar files (Jaccard ≥ 0.82). Only one representative per group gets extracted — results are projected back to the rest. Useful when you have 40 similar React components or 20 similar API route handlers.

### Layer 3: Smart batch packing
Files destined for LLM extraction are packed into batches by token count (default: 12,000 tokens/batch). One LLM call handles multiple files. Graphify sends each doc as a separate call; PruvaGraph fits as many as possible into each call.

### Layer 4: 3-tier LLM cascade (optional)
Set `--cascade` to route files through:
1. **Local (Ollama)** — for simple docs, zero cost
2. **Cheap cloud** (Gemini Flash, Kimi K2, GPT-4.1-mini) — for medium complexity
3. **Premium cloud** (Claude Sonnet) — only when confidence is low

Most files resolve at tier 1 or 2. Claude Sonnet is reserved for complex cases.

### Cost budget
Set a hard spending cap:
```bash
pruvagraph . --budget 2.00   # stop at $2.00 of LLM spend
pruvagraph . --dry-run       # estimate cost before spending anything
```

---

## Backends

```bash
# Default: Claude (ANTHROPIC_API_KEY)
pruvagraph .

# Cheaper alternatives (same graph quality)
pruvagraph . --backend gemini    # GEMINI_API_KEY
pruvagraph . --backend kimi      # MOONSHOT_API_KEY  
pruvagraph . --backend openai    # OPENAI_API_KEY

# Free (local Ollama — needs ollama running)
pruvagraph . --backend ollama

# Cascade mode (local → cheap → premium)
pruvagraph . --cascade
```

---

## Claude Code / Cursor / VS Code integration files

PruvaGraph writes integration files automatically:

```bash
pruvagraph install              # auto-detect IDE
pruvagraph install --vscode     # CLAUDE.md + .vscode/settings.json
pruvagraph install --cursor     # .cursor/rules/pruvagraph.mdc
pruvagraph install --claude-code # MCP server config
```

---

## Advanced

```bash
# Incremental update (changed files only)
pruvagraph . --update

# Focus on specific directory
pruvagraph ./src

# Export formats
pruvagraph export --format cypher   # Neo4j import
pruvagraph export --format obsidian # Obsidian vault
pruvagraph export --format graphml  # yEd / Gephi

# Cost report
pruvagraph cost-report

# Benchmark: tokens saved vs reading raw files
pruvagraph benchmark

# Git hook (auto-update on commit)
pruvagraph hook install
```

---

## How it compares to Graphify

PruvaGraph started as a fork of the ideas in Graphify and rebuilt the cost layer from scratch.

| Feature | Graphify | PruvaGraph |
|---|---|---|
| Core pipeline | ✅ 3-pass | ✅ 3-pass + cascade |
| SHA-256 cache | ✅ | ✅ |
| Semantic MinHash dedup | ✅ basic | ✅ improved (Jaccard threshold tunable) |
| Smart batch packing | ❌ fixed batches | ✅ token-aware packing |
| 3-tier LLM cascade | ❌ | ✅ local → cheap → premium |
| Cost budget cap | ❌ | ✅ `--budget 2.00` |
| Cost analytics | ❌ | ✅ `cost_report.json` |
| VS Code extension | ❌ | ✅ Marketplace |
| MCP server (rich) | ✅ basic | ✅ 8 tools |
| Dry-run cost estimate | ❌ | ✅ `--dry-run` |

---

## Contributing

PruvaGraph is MIT licensed and welcomes contributions. The best ways to contribute:

- **Add a language extractor** — see `packages/core/pruvagraph/extract/` and `CONTRIBUTING.md`
- **Improve dedup thresholds** — `packages/core/pruvagraph/dedup.py`
- **Add an LLM backend** — `packages/core/pruvagraph/backends/`
- **VS Code extension features** — `packages/vscode/`

See [CONTRIBUTING.md](./CONTRIBUTING.md) for setup instructions.

---

## About PRUVALEX

PruvaGraph is built and maintained by [PRUVALEX](https://pruvalex.eu).

PRUVALEX builds compliance tools for enterprise software teams. PruvaGraph is our open-source contribution to the developer community — a tool we built because we needed it ourselves and thought others would too.

---

## License

MIT © 2026 PRUVALEX

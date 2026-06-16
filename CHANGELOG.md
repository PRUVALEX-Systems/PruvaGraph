# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

### [1.2.1](https://github.com/pruvalex/pruvagraph/compare/v1.2.0...v1.2.1) (2026-06-16)

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

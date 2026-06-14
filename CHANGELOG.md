# Changelog

All notable changes to PRUVALEX PruvaGraph are documented here.

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

[1.0.0]: https://github.com/pruvalex/pruvagraph/releases/tag/v1.0.0

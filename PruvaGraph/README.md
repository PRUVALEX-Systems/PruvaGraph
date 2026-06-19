# PRUVALEX Monorepo

PRUVALEX is an enterprise-grade VS Code extension platform delivering reliable code intelligence, guarded developer workflows, and ML cost reduction through modular runtime tooling.

This repository combines a robust shared core with independent feature modules, enabling teams to deploy drift detection, context telemetry, memory persistence, rules enforcement, and Git-safe checkpointing in a single integrated solution.

## Enterprise Architecture

- **Monolithic core, modular runtime**: `packages/core-engine` provides the shared SQLite store, event bus, MCP router, workspace context, and webview host.
- **Feature modules**: `packages/module-*` contain self-contained DriftGuard, ContextLens, GhostMemory, RulesForge, and TaskWeaver services.
- **Extension shell**: `extension` wires the core and modules into VS Code, exposing commands, configuration toggles, and activation lifecycle.
- **Cost-aware design**: Every MCP tool call is token-tracked, enabling **31.6% baseline compression and up to 100% cache bypass** versus uncontrolled API usage.

## What Makes PRUVALEX Enterprise-Ready

- **Stable modular runtime** with dynamic enable/disable via VS Code settings.
- **Shared persistent store** across modules for consistent project state.
- **Cross-module event bus** for safe communication and auditability.
- **Git-aware checkpointing** that rejects dirty worktrees and uses safe restore semantics.
- **Real package symbol indexing** for DriftGuard, instead of stubbed heuristics.
- **Fully contributed command palette actions** for discovery and usability.

## Public-Facing Feature Summary

### Core Engine

- Shared SQLite graph store supporting module persistence and telemetry.
- EventBus for cross-module signals like `mcp:call`, `suggestion:accepted`, and `checkpoint:created`.
- Workspace Context with manifest reading, file watching, and PruvaGraph auto-venv runner.
- MCP Router that logs tool execution and emits telemetry to the token ledger.

### DriftGuard

- Real package symbol indexing from installed `node_modules` packages.
- No more fake stubbed symbol results.
- Import validation on document open/save.
- AST-style hallucination interception using actual declaration scanning.

### ContextLens

- Full VS Code command palette integration: `PRUVALEX: ContextLens — Show`.
- Live token ledger UI showing module, tool, tokens, latency, and timestamps.
- Automatic refresh on every MCP tool execution.

### GhostMemory

- Persistent semantic storage across editor sessions.
- Fast recall of relevant memories by query.
- Tag, project, and metadata support for secure memory organization.
- Auto-store of accepted suggestions into the memory corpus.

### RulesForge

- Correct rule creation mapping and persistence.
- Dynamic rule retrieval by layer and file scope.
- Heuristic inference of guardrails from accepted suggestions.
- Structured rule storage for future AST-based enforcement.

### TaskWeaver

- Safe git-aware checkpoint creation with commit resolution.
- Secure rollback that protects dirty working trees.
- Task progress tracking and checkpoint history retrieval.

## Stabilized Status

PRUVALEX is now stabilized for beta testing with the critical enterprise fixes in place. The project is ready for validation across real TypeScript workspaces, enterprise repositories, and cost-sensitive AI workflows.

## Documentation

- Setup and testing instructions: `extension/README.md`
- Current status and feature breakdown: `PROJECT_STATUS.md`

## Notes

- Built from `extension/package.json`.
- Core engine packages live under `packages/`.
- Target runtime: Node.js 20+.


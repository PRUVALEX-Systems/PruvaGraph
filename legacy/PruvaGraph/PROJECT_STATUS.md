# PRUVALEX Project Status

## Overview

PRUVALEX is now a stabilized enterprise-grade VS Code extension platform with a robust shared core and independently deployable feature modules.

This document details the currently available production-grade capabilities, the modules that are fully operational today, and the exact bug fixes that were applied to reach this milestone.

---

## Core Engine

### Available capabilities

- **Shared SQLite graph store**
  - Persistent module storage across `driftguard`, `ghostmemory`, `rulesforge`, `taskweaver`, and `token_ledger`
  - Implemented in `packages/core-engine/src/db/connection.ts`
- **EventBus**
  - Cross-module communication with typed events for `mcp:call`, `suggestion:accepted`, and `checkpoint:created`
  - Enables safe reactive workflows across modules
- **Workspace Context**
  - Reads workspace `package.json` and provides manifest metadata
  - Monitors workspace file changes via VS Code file system watchers
  - Initializes the PruvaGraph runner when a workspace is opened
- **PruvaGraph Auto-Venv Runner**
  - Creates isolated Python virtual environments per workspace
  - Installs or updates the PruvaGraph engine from local sources or PyPI
  - Runs local graph extraction safely with progress reporting
- **MCP Router and Token Ledger**
  - Registers local tool handlers for module APIs
  - Emits token-level usage data for each call
  - Records tokens, latency, module attribution, and server info

### Stabilization notes

- The core engine now auto-migrates its SQLite schema on activation.
- Token ledger writes are stable and persistent.
- Workspace context starts PruvaGraph automatically, reducing manual setup overhead.
- The extension now supports enterprise module toggles without needing a reload.

---

## Modules

### DriftGuard

#### What works today

- Real package API symbol indexing from installed packages in `node_modules`.
- Uses package metadata and declaration scanning, not stubbed data.
- Symbols are extracted from:
  - `types` / `typings` in `package.json`
  - `index.d.ts`
  - `index.js`
- Symbols are stored in `driftguard_index` with package path, version, and signature metadata.
- Unknown imports are surfaced as diagnostics on document open/save.

#### Enterprise-grade behavior

- No fake stubbed results.
- Actual package exports are indexed and stored.
- DriftGuard warns only when a symbol cannot be found in installed package declarations.

### ContextLens

#### What works today

- Command palette integration: `PRUVALEX: ContextLens � Show`
- Live token ledger UI panel for module-level telemetry
- Displays:
  - module name
  - tool name
  - tokens in/out
  - latency
  - timestamp
- Auto-refreshes on every MCP tool call via event subscriptions
- Uses the shared SQLite token ledger for persistence and auditing

#### Enterprise-grade behavior

- Fully exposed UX for visibility and accountability
- Telemetry is stored persistently for later analysis
- Module attribution prevents siloed cost reporting

### GhostMemory

#### What works today

- Persistent semantic memory storage in SQLite
- Exposes MCP tools:
  - `store_memory`
  - `recall_relevant`
  - `tag_memory`
- Supports project-scoped memories and tag metadata
- Auto-captures accepted suggestion events into memory
- Fast recall via SQL relevance matching

#### Enterprise-grade behavior

- Cross-session persistence is supported
- Memory entries are safely isolated by project
- Supports future expansion to richer semantic retrieval

### RulesForge

#### What works today

- Correct rule creation mapping saved into `rulesforge_rules`
- Exposes MCP tools:
  - `create_rule`
  - `get_applicable_rules`
  - `delete_rule`
- Rules include:
  - `rule_name`
  - `condition`
  - `action`
  - `layer`
  - `source`
- Can query applicable rules by file URI and layer
- Heuristic rule inference from accepted suggestions is enabled

#### Enterprise-grade behavior

- Rule definitions are structurally correct and actionable
- The engine avoids malformed rule persistence
- Rule storage is ready for future AST-based enforcement

### TaskWeaver

#### What works today

- Safe git-aware checkpoint creation
- Resolves requested refs to verified commit SHAs
- Exposes MCP tools:
  - `create_checkpoint`
  - `rollback_to_checkpoint`
  - `get_task_progress`
- Rollback validation includes clean worktree enforcement
- Rollback uses `git restore --source=<sha> -- .` to avoid destructive history changes

#### Enterprise-grade behavior

- Protects uncommitted work from accidental overwrite
- Ensures rollback only occurs in safe repo state
- Checkpoints are auditable and recoverable

---

## Extension UX

### Commands available

- `PRUVALEX: Initialize Graph`
- `PRUVALEX: ContextLens � Show`
- `PRUVALEX: DriftGuard Accept Fix`

### Configuration toggles

- `pruvagraph.modules.driftguard.enabled`
- `pruvagraph.modules.contextlens.enabled`
- `pruvagraph.modules.ghostmemory.enabled`
- `pruvagraph.modules.rulesforge.enabled`
- `pruvagraph.modules.taskweaver.enabled`

### Activation

- Extension activates on `onStartupFinished`
- Runtime module reconciliation occurs on settings changes
- Only enabled modules are instantiated, minimizing runtime overhead

---

## Change Log

- **RulesForge mapping fixed**: corrected rule creation so `rule_name`, `condition`, `action`, `layer`, and `source` are stored properly.
- **DriftGuard indexing upgraded**: removed stubbed symbol indexing and implemented actual package declaration scanning.
- **TaskWeaver safety enforced**: rollback now validates clean git state and uses safe restore semantics.
- **ContextLens exposed**: added proper command palette contribution for the ContextLens UI.

---

## QA readiness

This repo is ready for focused enterprise beta testing on the following scenarios:

1. Validate `DriftGuard` against real installed package APIs.
2. Confirm `ContextLens` command palette discovery and token telemetry accuracy.
3. Verify `GhostMemory` persistence and recall across sessions.
4. Test `RulesForge` rule creation, retrieval, and heuristic inference.
5. Confirm `TaskWeaver` checkpoint/rollback safety on clean vs dirty git trees.

For end-to-end testing instructions, follow `extension/README.md`.


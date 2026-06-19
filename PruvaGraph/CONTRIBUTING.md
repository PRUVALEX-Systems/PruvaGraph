# Contributing to PRUVALEX

Thank you for your interest in contributing! 

PRUVALEX uses a **monolithic core with modular architecture** (Hexagonal Architecture). 

## Architecture Overview
- **Single DB (`pruvagraph.db`)**: All data is stored in one SQLite database, using prefixed tables to avoid contention.
- **Hexagonal Ports**: Modules access services through strictly typed interfaces (`IGraphStore`, `IMCPTransport`, `IEventBus`).
- **PruvaGraph**: A Python engine bootstrapped automatically via Auto-Venv to provide AST and Graph intelligence.

## How to Add a New Module
1. Check the [Module Development Guide](docs/module-development-guide.md) for full instructions.
2. Create your module in `packages/module-<name>`.
3. Implement the `PRUVALEXModule` interface.
4. Prefix all database tables with your module ID (e.g., `yourmodule_entries`).
5. Register it in `extension/src/di/container.ts`.

## PR Requirements
- All module communication MUST go through `IEventBus`.
- NO direct DB imports (`better-sqlite3`). Use `IGraphStore.scope()`.
- Ensure benchmarks (`npm run bench`) pass before opening a PR.
- VSIX size must stay under 10MB limit.


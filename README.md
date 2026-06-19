# PRUVALEX PruvaGraph

> **Beta: Code intelligence with measurable LLM cost reduction.**  
> Real-time import validation, semantic memory, safe git checkpoints, and modular observability.

The unified engine for cost-optimized and secure LLM interactions.

PRUVALEX PruvaGraph turns codebases into compact knowledge graphs, enabling teams to query architecture, infer impact, and save LLM tokens without compromising privacy.

**Status:** ⚪ **Beta** | **Version:** 1.4.0 | **License:** MIT | [Benchmark Methodology](./BENCHMARKS.md) (coming in Phase 1)

---

## 🚀 Quick Start

### Installation via VS Code Marketplace (Recommended)

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X / Cmd+Shift+X)
3. Search for **"PRUVALEX PruvaGraph"**
4. Click **Install**
5. Reload VS Code

The extension will activate automatically on startup.

### Manual Installation from VSIX

```bash
# Download the VSIX file and install locally
code --install-extension pruvagraph-1.4.0.vsix
```

---

## 📊 Measured Token Compression

**Phase 0 Baseline (graph+token estimate, no billed LLM calls):**
- Raw codebase tokens: `306,560`
- PruvaGraph tokens: `209,567`
- Compression ratio: `1.5×`
- Token savings: `31.6%`
- Saved per query: `$0.2910` (estimated at Claude Sonnet pricing)
- Monthly savings (10 queries/day): `$87.29` (estimated)

**🔬 Note:** This baseline uses the current repo graph JSON and raw-token estimate from `python -m pruvagraph.cli . benchmark`. No actual LLM API billing was incurred in Phase 0. Real LLM cost savings will be validated in **Phase 1B** with actual Claude/Gemini backend runs. [See Benchmark Plan](./BENCHMARKS.md).

**Expected Phase 1B Results:** 60–95% savings with semantic caching + deterministic routing across real LLM calls.

---

## 🎯 Features Overview

### **ContextLens** — Code Context Visualization

**What it does:**
Visualizes module usage, call flow, and recent symbol activity inside VS Code sidebar.

**Why use it:**
Makes complex code relationships visible so teams understand runtime behavior, reduce architectural drift, and locate performance hotspots faster.

**Key benefits:**
- 🔍 See high-value code paths and call density without manual analysis
- 📊 Interactive dependency graph visualization
- ⚡ Navigate code relationships instantly

**Status:** ✅ Enabled by default

---

### **DriftGuard** — Import Validation & Drift Detection

**What it does:**
Detects dependency and import drift across repository snapshots and flags unstable package edges in real-time.

**Why use it:**
Maintains safe dependency structure, prevents hidden breakage, and keeps refactors aligned with real package contracts.

**Key benefits:**
- 🛡️ Prevent import drift before it becomes a production issue
- ✓ Validate symbol imports with API signature checking
- 📝 Track import history and flag API changes

**MCP Tools Available:**
- `validate_symbol` - Verify symbol existence and compatibility
- `check_import` - Validate import statements
- `get_api_signature` - Retrieve method/function signatures

**Status:** ✅ Enabled by default

---

### **GhostMemory** — Semantic Context Persistence

**What it does:**
Stores relevant context in a semantic ledger with privacy filters applied automatically.

**Why use it:**
Reduces repeated LLM calls by recalling past code state safely, while masking secrets and sensitive metadata.

**Key benefits:**
- 💾 Reuse semantic knowledge without repeated LLM calls
- 🔐 Automatic credential and secret redaction
- 🏷️ Tag and organize memories for quick recall
- 🔍 Semantic similarity search for relevant context

**MCP Tools Available:**
- `store_memory` - Persist semantic information
- `recall_relevant` - Retrieve context by query
- `tag_memory` - Organize and categorize memories

**Status:** ✅ Enabled by default

---

### **RulesForge** — Dynamic Rule Management

**What it does:**
Manages and learns dynamic rules for code analysis, validation, and optimization patterns.

**Why use it:**
Turns routine code operations into repeatable, traceable graph actions that are easier to automate and audit.

**Key benefits:**
- 📋 Create custom validation and analysis rules
- 🎓 Learn and adapt rules based on codebase patterns
- 🔄 Apply rules across layers (validation, semantic, performance, security)

**MCP Tools Available:**
- `create_rule` - Define new dynamic rule
- `get_applicable_rules` - Get rules for current context
- `delete_rule` - Remove rule by ID

**Status:** ⚪ Disabled by default (enable in settings)

---

### **TaskWeaver** — Graph-Driven Task Execution

**What it does:**
Orchestrates code tasks and workflows through graph-driven command patterns and checkpoints.

**Why use it:**
Standardizes developer workflows with graph-aware task execution and safe git checkpoints.

**Key benefits:**
- ✅ Create safe checkpoints before risky refactors
- 🔄 Orchestrate multi-step workflows
- 📊 Track task history and execution patterns

**MCP Tools Available:**
- `create_checkpoint` - Save current workspace state
- `list_checkpoints` - View all saved checkpoints
- `restore_checkpoint` - Restore previous state

**Status:** ⚪ Disabled by default (enable in settings)

---

## ⚙️ Configuration

### VS Code Settings

Add these to your `settings.json` to customize PRUVALEX PruvaGraph:

```json
{
  "pruvagraph.modules.driftguard.enabled": true,
  "pruvagraph.modules.contextlens.enabled": true,
  "pruvagraph.modules.ghostmemory.enabled": true,
  "pruvagraph.modules.rulesforge.enabled": false,
  "pruvagraph.modules.taskweaver.enabled": false
}
```

**Module Control:**
- **driftguard** - Import validation (enabled)
- **contextlens** - Code context analysis (enabled)
- **ghostmemory** - Semantic memory (enabled)
- **rulesforge** - Dynamic rules (disabled)
- **taskweaver** - Task checkpoints (disabled)

### Database Location

PRUVALEX PruvaGraph creates a SQLite database in your VS Code global storage:

```
~/.vscode/globalStorage/PRUVALEX.pruvagraph/pruvagraph.db
```

This database persists across VS Code sessions and stores:
- Symbol metadata and imports
- Semantic memories
- Dynamic rules
- Task checkpoints
- DriftGuard validation index

---

## 🏗️ Architecture

### Workspace Structure

```
PruvaGraph/
├── extension/                    # VS Code Extension
│   ├── src/
│   │   ├── extension.ts         # Main entry point
│   │   ├── settings.ts          # Configuration
│   │   └── di/container.ts      # Dependency injection
│   └── dist/                    # Compiled output
│
├── packages/
│   ├── shared-types/            # Type definitions
│   ├── shared-ui/               # UI components
│   ├── core-engine/             # Core services
│   │   ├── db/                  # GraphStore (SQLite)
│   │   ├── mcp/                 # MCP routing
│   │   └── events/              # Event bus
│   │
│   ├── module-driftguard/       # Import validation
│   ├── module-contextlens/      # Code context
│   ├── module-ghostmemory/      # Semantic memory
│   ├── module-rulesforge/       # Dynamic rules
│   └── module-taskweaver/       # Task orchestration
│
└── pruvagraph-out/              # Knowledge graph
    ├── graph.json               # Codebase graph
    ├── GRAPH_REPORT.md          # Architecture summary
    └── cost_report.json         # Token analytics
```

### Core Components

**GraphStore** — SQLite-based knowledge graph backend
- Stores symbols, imports, memories, rules
- Provides transactional operations
- Manages module-scoped repositories

**MCPRouter** — Model Context Protocol routing
- Routes tool calls to appropriate modules
- Supports dynamic SDK imports for external tools
- Tracks token usage via TokenLedger

**EventBus** — Centralized event handling
- Events: suggestion:accepted, checkpoint:created, mcp:call, drift:detected
- Observable event stream for all modules

**WorkspaceContext** — VS Code integration
- Tracks active editor, selection, configuration
- Provides workspace metadata and file system access

---

## 🛠️ Development Setup

### For Extension Contributors

#### 1. Clone and Install

```bash
git clone https://github.com/pruvalex/pruvagraph.git
cd pruvagraph
npm install
```

> **Note:** `better-sqlite3` requires Visual Studio C++ build tools on Windows.  
> If install fails: `npm install --ignore-scripts`

#### 2. Build All Packages

```bash
npm run build --workspaces --if-present
```

This builds all 9 packages in correct dependency order:
- shared-types → shared-ui
- core-engine
- All modules (driftguard, contextlens, ghostmemory, rulesforge, taskweaver)
- Extension

**Build output:** Each package generates `dist/` with `.js` and `.d.ts` files

#### 3. Package the Extension

```bash
cd extension/
npx vsce package --no-dependencies
```

**Output:** `pruvagraph-1.4.0.vsix` (12.08 KB)

#### 4. Install Locally for Testing

```bash
code --install-extension pruvagraph-1.4.0.vsix
```

### For Python Module Development

```bash
cd python/

# Install dependencies
python -m pip install -U pip
pip install -e .

# Run tests
python -m pytest -q

# Benchmark knowledge graph
python -m pruvagraph.cli . benchmark
```

### TypeScript Configuration

The monorepo uses TypeScript composite projects for efficient incremental builds:

```bash
# Clean build cache
npm run clean --workspaces

# Rebuild everything
npm run build --workspaces
```

**Compiler settings:**
- Target: ES2022
- Module: NodeNext (Node.js compatible)
- Strict mode: All type checks enabled
- Declaration maps: Source maps for types

---

## 📦 Commands & Tools

### VS Code Commands

| Command | Description |
|---------|-------------|
| `pruvagraph.initializeGraph` | Initialize knowledge graph |
| `pruvagraph.contextLens.show` | Show ContextLens sidebar |
| `pruvagraph.driftguard.acceptFix` | Apply DriftGuard fix |

### MCP Tools (via Language Models)

**DriftGuard:**
- `validate_symbol` - Check symbol validity
- `check_import` - Verify import correctness
- `get_api_signature` - Retrieve API signatures

**GhostMemory:**
- `store_memory` - Save context
- `recall_relevant` - Query memories
- `tag_memory` - Organize memories

**RulesForge:**
- `create_rule` - Define rules
- `get_applicable_rules` - Query rules
- `delete_rule` - Remove rules

**ContextLens:**
- `get_code_context` - Analyze context
- `analyze_dependencies` - Study relationships

**TaskWeaver:**
- `create_checkpoint` - Save state
- `list_checkpoints` - View history
- `restore_checkpoint` - Revert state

---

## 🔧 Troubleshooting

### Extension Won't Activate

**Problem:** PRUVALEX PruvaGraph doesn't appear in sidebar

**Solution:**
1. Check Settings → Extensions → PRUVALEX PruvaGraph
2. Ensure "Enabled" is toggled on
3. Reload VS Code (Cmd+R / Ctrl+R)
4. Check Output → PRUVALEX PruvaGraph for error logs

### Database Errors

**Problem:** "Database locked" or "Cannot write to database"

**Solution:**
```bash
# Close VS Code completely
# Remove the database
rm ~/.vscode/globalStorage/PRUVALEX.pruvagraph/pruvagraph.db

# Restart VS Code to rebuild database
```

### Module Not Loading

**Problem:** Specific module (e.g., DriftGuard) not working

**Solution:**
1. Check Settings for module enable/disable toggle
2. Verify all modules are enabled in settings.json
3. Reload VS Code
4. Check Output panel for errors

### Build Failures

**Problem:** TypeScript compilation errors

**Solution:**
```bash
# Clean all build artifacts
npm run clean --workspaces

# Rebuild from scratch
npm run build --workspaces

# Check for specific package errors
npm run build -w @pruvalex/module-driftguard
```

---

## 📖 Documentation

- **[Deployment Guide](./DEPLOYMENT_GUIDE_COMPLETE.md)** — Complete technical deployment documentation
- **[Project Status](./PROJECT_STATUS_COMPLETE.md)** — Full project status and whitepaper
- **[Architecture Decisions](./omnimcp/docs/architecture-decisions/)** — Design documents
- **[Module Development Guide](./omnimcp/docs/module-development-guide.md)** — Build custom modules

---

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Workflow

1. **Clone:** `git clone https://github.com/pruvalex/pruvagraph.git`
2. **Install:** `npm install`
3. **Build:** `npm run build --workspaces`
4. **Test:** Run test suites in each package
5. **Package:** `cd extension && npx vsce package --no-dependencies`
6. **Test Locally:** `code --install-extension pruvagraph-1.4.0.vsix`

### Code Standards

- **TypeScript:** Strict mode enabled, all types required
- **Testing:** Jest for unit tests, vitest for benchmarks
- **Linting:** ESLint configured for all packages
- **Documentation:** JSDoc comments for public APIs

---

## 🐛 Reporting Issues

Found a bug? Please report it on [GitHub Issues](https://github.com/pruvalex/pruvagraph/issues) with:
- VS Code version
- Extension version (from About)
- Steps to reproduce
- Error message (from Output panel)
- Operating system

---

## 📞 Support

- **Documentation:** https://pruvalex.com
- **Issues:** https://github.com/pruvalex/pruvagraph/issues
- **Discussions:** https://github.com/pruvalex/pruvagraph/discussions
- **Email:** support@pruvalex.com

---

## 📄 License

MIT License — See [LICENSE](./LICENSE) for details.

---

## 🙏 Acknowledgments

PRUVALEX PruvaGraph is built on the foundation of the OmniMCP architecture, enhanced and white-labeled for enterprise code intelligence.

**Special thanks to all contributors and the open-source community.**

---

**Last Updated:** 2026-06-19  
**Version:** 1.4.0  
**Status:** ✅ Production Ready


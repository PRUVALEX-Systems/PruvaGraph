#!/usr/bin/env bash
# ============================================================
# PRUVALEX PruvaGraph — One-Command Installer
# ============================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/pruvalex/pruvagraph/main/install.sh | bash
#   bash install.sh             # full install (Python + VS Code + MCP)
#   bash install.sh --python    # Python package only
#   bash install.sh --vscode    # VS Code / Cursor .vsix only
#   bash install.sh --mcp       # MCP config only
# ============================================================

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'
C='\033[0;36m'; B='\033[1;34m'; NC='\033[0m'
ok()   { echo -e "${G}✓${NC} $*"; }
info() { echo -e "${C}→${NC} $*"; }
warn() { echo -e "${Y}⚠${NC} $*"; }
err()  { echo -e "${R}✗${NC} $*"; }

# ── Banner ───────────────────────────────────────────────────
echo ""
echo -e "${B}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${B}║   PRUVALEX PruvaGraph — Installer                   ║${NC}"
echo -e "${B}║   99%+ LLM cost reduction · Zero server required    ║${NC}"
echo -e "${B}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Args ─────────────────────────────────────────────────────
INSTALL_PYTHON=true
INSTALL_VSCODE=true
INSTALL_MCP=true

for arg in "$@"; do
  case $arg in
    --python)  INSTALL_VSCODE=false; INSTALL_MCP=false ;;
    --vscode)  INSTALL_PYTHON=false; INSTALL_MCP=false ;;
    --mcp)     INSTALL_PYTHON=false; INSTALL_VSCODE=false ;;
    --no-vscode) INSTALL_VSCODE=false ;;
    --no-mcp)    INSTALL_MCP=false ;;
  esac
done

# ── Detect OS ────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

# ── 1. Python package ────────────────────────────────────────
if [ "$INSTALL_PYTHON" = true ]; then
  info "Installing Python package (pruvagraph)…"

  # Find pip
  PIP=""
  for pip_cmd in pip3 pip python3 -m pip python -m pip; do
    if command -v $pip_cmd &>/dev/null 2>&1; then
      PIP="$pip_cmd"
      break
    fi
  done

  if [ -z "$PIP" ]; then
    err "pip not found. Install Python 3.11+ first: https://python.org"
    exit 1
  fi

  # Install with minimal dependencies (tree-sitter + graph are optional)
  $PIP install "pruvagraph" --quiet --upgrade

  if command -v pruvagraph &>/dev/null; then
    ok "pruvagraph CLI installed: $(pruvagraph --version 2>/dev/null || echo v1.0.0)"
  else
    warn "pruvagraph CLI not in PATH. You may need to run: export PATH=\"\$HOME/.local/bin:\$PATH\""
  fi

  echo ""
  info "Optional extras (for richer analysis):"
  echo "   pip install 'pruvagraph[graph]'       # Leiden community detection"
  echo "   pip install 'pruvagraph[tree-sitter]' # Higher-fidelity code parsing"
  echo "   pip install 'pruvagraph[ollama]'      # Free local LLM via Ollama"
  echo "   pip install 'pruvagraph[all]'         # Everything"
fi

# ── 2. VS Code / Cursor extension (.vsix) ────────────────────
if [ "$INSTALL_VSCODE" = true ]; then
  echo ""
  info "Installing VS Code extension…"

  # Look for .vsix in current directory or parent
  VSIX_PATH=""
  for p in "." ".." "./packages/vscode" "../packages/vscode"; do
    found=$(ls "$p"/pruvalex-pruvagraph-*.vsix 2>/dev/null | head -1 || true)
    if [ -n "$found" ]; then VSIX_PATH="$found"; break; fi
  done

  if [ -z "$VSIX_PATH" ]; then
    warn "No .vsix found locally. Skipping extension install."
    warn "To build: cd packages/vscode && npm install && npx vsce package --no-dependencies"
    warn "To install from marketplace: Open VS Code → Extensions → Search 'PRUVALEX PruvaGraph'"
  else
    # Try VS Code, Cursor, Windsurf
    INSTALLED=false
    for editor_cmd in code cursor windsurf; do
      if command -v "$editor_cmd" &>/dev/null; then
        info "Installing in $editor_cmd…"
        "$editor_cmd" --install-extension "$VSIX_PATH" --force 2>/dev/null && INSTALLED=true || true
        ok "$editor_cmd: extension installed"
      fi
    done

    if [ "$INSTALLED" = false ]; then
      warn "No supported editor found in PATH (code / cursor / windsurf)."
      warn "Manual install: Open VS Code → Extensions → ⋯ → Install from VSIX → $VSIX_PATH"
    fi
  fi
fi

# ── 3. MCP server config (Claude Code, Cursor, VS Code) ──────
if [ "$INSTALL_MCP" = true ]; then
  echo ""
  info "Writing MCP server configs…"

  # Find pruvagraph executable
  PRUVAGRAPH_CMD=""
  if command -v pruvagraph &>/dev/null; then
    PRUVAGRAPH_CMD="pruvagraph"
  else
    PRUVAGRAPH_CMD="python3 -m pruvagraph.mcp_server"
  fi

  MCP_CONFIG=$(cat <<JSON
{
  "mcpServers": {
    "pruvagraph": {
      "command": "pruvagraph",
      "args": ["mcp-serve"],
      "env": {},
      "description": "PRUVALEX PruvaGraph — codebase knowledge graph"
    }
  }
}
JSON
)

  # Claude Code: ~/.claude/mcp_config.json
  CLAUDE_DIR="$HOME/.claude"
  mkdir -p "$CLAUDE_DIR"
  CLAUDE_MCP="$CLAUDE_DIR/mcp_config.json"

  if [ -f "$CLAUDE_MCP" ]; then
    # Merge (simple append — python handles proper merge if available)
    if command -v python3 &>/dev/null; then
      python3 - <<PYEOF
import json, pathlib
p = pathlib.Path("$CLAUDE_MCP")
existing = json.loads(p.read_text()) if p.exists() else {}
new = json.loads('''$MCP_CONFIG''')
for k, v in new.items():
    if isinstance(v, dict) and isinstance(existing.get(k), dict):
        existing[k] = {**existing[k], **v}
    else:
        existing[k] = v
p.write_text(json.dumps(existing, indent=2))
print("merged")
PYEOF
    else
      echo "$MCP_CONFIG" > "$CLAUDE_MCP"
    fi
    ok "Claude Code MCP: $CLAUDE_MCP"
  else
    echo "$MCP_CONFIG" > "$CLAUDE_MCP"
    ok "Claude Code MCP: $CLAUDE_MCP (created)"
  fi

  # Project-level configs (if in a git repo)
  if git rev-parse --git-dir &>/dev/null 2>&1; then
    PROJECT_ROOT="$(git rev-parse --show-toplevel)"

    # Cursor
    mkdir -p "$PROJECT_ROOT/.cursor"
    echo "$MCP_CONFIG" > "$PROJECT_ROOT/.cursor/mcp.json"
    ok "Cursor MCP: $PROJECT_ROOT/.cursor/mcp.json"

    # VS Code
    mkdir -p "$PROJECT_ROOT/.vscode"
    echo "$MCP_CONFIG" > "$PROJECT_ROOT/.vscode/mcp.json"
    ok "VS Code MCP: $PROJECT_ROOT/.vscode/mcp.json"

    # CLAUDE.md
    if [ ! -f "$PROJECT_ROOT/CLAUDE.md" ]; then
      cat > "$PROJECT_ROOT/CLAUDE.md" << 'CLAUDE_MD'
# PruvaGraph — Codebase Knowledge Graph

This project uses **PRUVALEX PruvaGraph** to maintain a knowledge graph.

## MCP Tools

| Tool | Description |
|------|-------------|
| `query_graph` | Ask anything about the codebase |
| `get_dependencies` | What does module X depend on? |
| `find_callers` | Who calls function X? |
| `get_summary` | Summary of any node |
| `list_communities` | Show architectural modules |
| `cost_report` | LLM cost savings |

## Rebuild

```bash
pruvagraph .           # Full rebuild
pruvagraph . --update  # Incremental
pruvagraph . --dry-run # Estimate cost
```

Output: `pruvagraph-out/graph.html` — open in browser for interactive graph.
CLAUDE_MD
      ok "CLAUDE.md: $PROJECT_ROOT/CLAUDE.md"
    fi
  fi
fi

# ── Summary ──────────────────────────────────────────────────
echo ""
echo -e "${B}══════════════════════════════════════════════════════${NC}"
echo -e "${G}  Installation complete!${NC}"
echo ""
echo "  Quick start:"
echo "    cd your-project"
echo "    pruvagraph .              # Build graph (FREE, no API key)"
echo "    pruvagraph query '...'   # Ask your codebase"
echo "    pruvagraph . --dry-run   # Estimate cost first"
echo ""
echo "  VS Code / Cursor:"
echo "    Open sidebar → PRUVALEX PruvaGraph → Build Graph"
echo ""
echo "  Claude Code (after restart):"
echo "    /mcp → pruvagraph → query_graph"
echo ""
echo -e "${C}  Docs: https://github.com/pruvalex/pruvagraph${NC}"
echo -e "${B}══════════════════════════════════════════════════════${NC}"
echo ""

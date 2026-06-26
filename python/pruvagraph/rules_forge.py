"""
pruvagraph.rules_forge — Context-aware dynamic AI rules engine (Phase 5).

Directly addresses the "Static AI rules (not context-aware)" pain point from
the gap analysis §2.1. Every competitor ships a single static `.cursorrules`
or `.clinerules` file. RulesForge makes rules context-aware by detecting what
kind of file is being worked on (via AST analysis) and returning only the rules
relevant to that layer.

Design decisions:
  - Classification: Python stdlib `ast` module — zero new dependencies
  - Rules storage: pruvagraph-out/rules.json (JSON file, stdlib)
  - Layers: api | ui | test | util | config | unknown
  - Default rules: shipped in-module (immutable, always present)
  - Learned rules: appended to rules.json._learned list (persistent, per-root)
  - Never raises — every public function returns a str or falls back to 'unknown'
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RULES_FILE_REL: str = "pruvagraph-out/rules.json"

# ---------------------------------------------------------------------------
# Default rules per layer (shipped in-module, never modified at runtime)
# ---------------------------------------------------------------------------

DEFAULT_RULES: dict[str, list[str]] = {
    "api": [
        "Always validate input data before processing",
        "Never expose internal stack traces in HTTP responses",
        "Use appropriate HTTP status codes (200/201/400/422/500)",
        "Document all endpoints with docstrings or OpenAPI descriptions",
    ],
    "ui": [
        "Keep UI components free of business logic",
        "Handle loading and error states explicitly",
        "Use consistent naming for event handlers (on_<event>)",
    ],
    "test": [
        "Use descriptive test names that explain the expected behaviour",
        "Arrange-Act-Assert structure for every test",
        "Avoid test interdependence — each test must run independently",
        "Mock external dependencies, never call real APIs in tests",
    ],
    "util": [
        "Functions should be pure where possible (no side effects)",
        "Document complex algorithms with inline comments",
        "Avoid module-level mutable state in utility modules",
    ],
    "config": [
        "Never hardcode secrets — use environment variables",
        "Provide sensible defaults for all optional config values",
        "Document the purpose and valid range of each setting",
    ],
    "unknown": [
        "Document the purpose of this module at the top of the file",
    ],
}

# ---------------------------------------------------------------------------
# Layer classification signals
# ---------------------------------------------------------------------------

_CONFIG_FILENAMES = {"config.py", "settings.py", "constants.py", "env.py", "conf.py"}

_API_IMPORTS = {
    "fastapi", "flask", "starlette", "aiohttp", "django",
    "sanic", "tornado", "falcon", "bottle", "quart",
}

_UI_IMPORTS = {
    "tkinter", "PyQt5", "PyQt6", "wx", "streamlit",
    "dash", "gradio", "panel", "bokeh", "kivy",
}

_TEST_IMPORTS = {"pytest", "unittest"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rules_path(root: str | Path) -> Path:
    return Path(root) / RULES_FILE_REL


def _load_rules(root: str | Path) -> dict:
    """Load rules.json or return a fresh skeleton."""
    path = _rules_path(root)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {layer: [] for layer in DEFAULT_RULES} | {"_learned": []}


def _save_rules(data: dict, root: str | Path) -> None:
    path = _rules_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_ast_imports(source: str) -> set[str]:
    """Return the set of top-level module names imported in a Python source string."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _infer_layer_from_diff(diff: str) -> str:
    """Best-effort: infer a layer from file paths mentioned in a diff header."""
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            path = line.split()[-1].lstrip("ab/")
            stem = Path(path).name.lower()
            if stem.startswith("test_") or stem.endswith("_test.py"):
                return "test"
            if stem in _CONFIG_FILENAMES:
                return "config"
    return "util"  # safe default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_file_layer(file_path: str | Path) -> str:
    """Classify a Python file's architectural layer using AST analysis.

    Returns one of: 'api' | 'ui' | 'test' | 'util' | 'config' | 'unknown'

    Never raises — returns 'unknown' for non-Python files, missing files,
    or any parse error.
    """
    path = Path(file_path)

    # Non-existent or non-Python file
    if not path.exists() or path.suffix != ".py":
        return "unknown"

    # Filename-based fast path
    stem = path.name.lower()
    if stem.startswith("test_") or stem.endswith("_test.py"):
        return "test"
    if path.name in _CONFIG_FILENAMES:
        return "config"

    # AST-based classification
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "unknown"

    imports = _get_ast_imports(source)

    if imports & _TEST_IMPORTS:
        return "test"
    if imports & _API_IMPORTS:
        return "api"
    if imports & _UI_IMPORTS:
        return "ui"

    # Empty or import-free Python file → util (not unknown; it's a valid module)
    return "util"


def get_applicable_rules(file_uri: str, root: str | Path = ".") -> str:
    """Return a formatted markdown block of rules applicable to the given file.

    Combines the immutable default rules for the detected layer with any rules
    that have been learned via learn_from_accept() for that layer.

    Handles non-existent files gracefully — returns 'unknown' layer rules.
    """
    layer = classify_file_layer(file_uri)
    defaults = DEFAULT_RULES.get(layer, DEFAULT_RULES["unknown"])

    # Load learned rules for this layer
    data = _load_rules(root)
    layer_learned: list[str] = [
        e["description"]
        for e in data.get("_learned", [])
        if e.get("layer") == layer
    ]

    lines = [
        f"### RulesForge — Rules for `{Path(file_uri).name}`",
        f"",
        f"**Layer detected:** `{layer}`",
        f"",
        f"**Default rules ({len(defaults)}):**",
    ]
    for rule in defaults:
        lines.append(f"- {rule}")

    if layer_learned:
        lines += [
            f"",
            f"**Learned rules ({len(layer_learned)}):**",
        ]
        for rule in layer_learned:
            lines.append(f"- {rule}")
    else:
        lines += [
            f"",
            f"*No learned rules yet for this layer. Use `learn_from_accept` to "
            f"capture patterns from accepted AI suggestions.*",
        ]

    return "\n".join(lines)


def learn_from_accept(
    diff: str,
    description: str,
    root: str | Path = ".",
) -> str:
    """Store a pattern learned from a developer-accepted AI suggestion.

    Infers the target layer from file paths in the diff header (falls back
    to 'util'). Appends an entry to the _learned list in rules.json.

    Returns a confirmation string showing the layer and total learned count.
    """
    layer = _infer_layer_from_diff(diff)
    now = datetime.now(timezone.utc).isoformat()

    data = _load_rules(root)
    if "_learned" not in data:
        data["_learned"] = []

    # Ensure all layer keys exist
    for key in DEFAULT_RULES:
        data.setdefault(key, [])

    entry = {
        "layer": layer,
        "description": description,
        "diff_snippet": diff[:200],  # store first 200 chars for audit trail
        "created_at": now,
    }
    data["_learned"].append(entry)
    _save_rules(data, root)

    total = len(data["_learned"])
    return (
        f"### RulesForge — Rule Learned\n\n"
        f"**Layer:** `{layer}`\n"
        f"**Description:** {description}\n"
        f"**Total learned rules:** {total}"
    )

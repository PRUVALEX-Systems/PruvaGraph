"""
PruvaGraph code extractor — Stage 1 of the pipeline (zero cost).

This is the Python counterpart of the VS Code extension's ``analyzer.js``:
a regex-based "AST-lite" parser covering 20+ languages. It needs no LLM,
no API key, and (unlike tree-sitter) no compiled grammars — so it always
works, on every platform, out of the box.

If ``tree-sitter`` + language grammars ARE installed, a future version can
swap in higher-fidelity parsing per-language while keeping this exact
return shape: ``{"nodes": [...], "edges": [...], "source_file": str, "lang": str}``.

Detects per file:
  - Imports / dependencies      -> "imports" edges
  - Classes / structs / enums   -> "class" nodes + "defines"/"extends" edges
  - Interfaces / types          -> "interface" nodes
  - Function / method signatures -> "function" nodes
  - External package usage      -> "external" stub nodes
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Language detection by extension (mirrors analyzer.js LANG_MAP)
# ──────────────────────────────────────────────────────────────────────────────

LANG_MAP: dict[str, str] = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript",
    ".py": "python", ".pyw": "python",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".swift": "swift",
    ".cs": "csharp",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".h": "cpp",
    ".c": "c",
    ".rb": "ruby",
    ".php": "php",
    ".vue": "vue",
    ".svelte": "svelte",
    ".dart": "dart",
    ".scala": "scala",
    ".zig": "zig",
    ".lua": "lua",
    ".r": "r", ".R": "r",
    ".sh": "bash", ".bash": "bash",
    ".yaml": "yaml", ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".css": "css", ".scss": "css", ".sass": "css", ".less": "css",
    ".html": "html", ".htm": "html",
    ".tf": "terraform", ".hcl": "terraform",
    ".sql": "sql",
}

# ──────────────────────────────────────────────────────────────────────────────
# Per-language regex patterns
# ──────────────────────────────────────────────────────────────────────────────
# Each entry maps to a list of regex strings. Capture group 1 is always the
# "primary" name; group 2 (when present) is a parent/base type.

_JS_IMPORTS = [
    r"""import\s+(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]""",
    r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""",
]

PATTERNS: dict[str, dict[str, list[str]]] = {
    "javascript": {
        "imports": _JS_IMPORTS,
        "classes": [r"class\s+(\w+)(?:\s+extends\s+(\w+))?"],
        "functions": [
            r"(?:function|const|let|var)\s+(\w+)\s*(?:=\s*(?:async\s+)?(?:\([^)]*\)|[\w]+)\s*=>|\()",
            r"(?:async\s+)?function\s+(\w+)\s*\(",
        ],
        "interfaces": [r"interface\s+(\w+)", r"type\s+(\w+)\s*="],
    },
    "typescript": {
        "imports": [
            r"""import\s+(?:type\s+)?(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]""",
            r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
        ],
        "classes": [r"class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+[\w,\s]+)?"],
        "functions": [
            r"(?:function|const|let|var)\s+(\w+)\s*(?:<[^>]*>)?\s*(?:=\s*(?:async\s+)?\(?|:\s*\w+\s*=)",
            r"(?:async\s+)?function\s+(\w+)\s*(?:<[^>]*>)?\s*\(",
        ],
        "interfaces": [
            r"interface\s+(\w+)",
            r"type\s+(\w+)\s*(?:<[^>]*>)?\s*=",
            r"enum\s+(\w+)",
        ],
    },
    "python": {
        "imports": [r"^import\s+([\w.]+)(?:\s+as\s+\w+)?", r"^from\s+([\w.]+)\s+import"],
        "classes": [r"^class\s+(\w+)(?:\s*\(([^)]*)\))?"],
        "functions": [r"^(?:async\s+)?def\s+(\w+)\s*\("],
        "interfaces": [],
    },
    "go": {
        "imports": [
            r'import\s+"([\w./]+)"',
            r'import\s+\w+\s+"([\w./]+)"',
        ],
        "classes": [r"type\s+(\w+)\s+struct", r"type\s+(\w+)\s+interface"],
        "functions": [r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\("],
        "interfaces": [r"type\s+(\w+)\s+interface"],
    },
    "rust": {
        "imports": [r"use\s+([\w:]+)(?:::\{[^}]+\}|::\*)?", r"extern\s+crate\s+(\w+)"],
        "classes": [r"(?:pub\s+)?struct\s+(\w+)", r"(?:pub\s+)?enum\s+(\w+)"],
        "functions": [r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"],
        "interfaces": [r"(?:pub\s+)?trait\s+(\w+)"],
    },
    "java": {
        "imports": [r"^import\s+([\w.]+)\s*;"],
        "classes": [
            r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?",
            r"(?:public|private|protected)?\s*interface\s+(\w+)",
        ],
        "functions": [r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*(?:throws[^{]*)?\{"],
        "interfaces": [r"interface\s+(\w+)"],
    },
    "kotlin": {
        "imports": [r"^import\s+([\w.]+)(?:\.\*)?"],
        "classes": [
            r"(?:data\s+|sealed\s+|abstract\s+|open\s+)?class\s+(\w+)",
            r"object\s+(\w+)",
            r"interface\s+(\w+)",
        ],
        "functions": [r"(?:fun|suspend\s+fun|private\s+fun|public\s+fun)\s+(\w+)"],
        "interfaces": [r"interface\s+(\w+)"],
    },
    "csharp": {
        "imports": [r"^using\s+([\w.]+)\s*;"],
        "classes": [
            r"(?:public|private|internal|protected)?\s*(?:abstract\s+|static\s+|sealed\s+)?class\s+(\w+)",
            r"(?:public|private|internal)?\s*interface\s+(\w+)",
        ],
        "functions": [r"(?:public|private|protected|internal|static|async|\s)+\w+\s+(\w+)\s*\([^)]*\)\s*\{"],
        "interfaces": [r"interface\s+(\w+)"],
    },
    "swift": {
        "imports": [r"^import\s+(\w+)"],
        "classes": [
            r"(?:public\s+|open\s+|private\s+|internal\s+)?(?:class|struct|enum|actor)\s+(\w+)",
            r"(?:public\s+)?protocol\s+(\w+)",
        ],
        "functions": [r"(?:public\s+|private\s+|internal\s+|open\s+)?(?:override\s+)?func\s+(\w+)"],
        "interfaces": [r"protocol\s+(\w+)"],
    },
    "dart": {
        "imports": [r"^import\s+'([^']+)'", r'^import\s+"([^"]+)"'],
        "classes": [r"(?:abstract\s+)?class\s+(\w+)", r"mixin\s+(\w+)"],
        "functions": [r"(?:Future<\w+>|void|String|int|bool|List|Map|\w+)\s+(\w+)\s*\([^)]*\)\s*(?:async\s*)?\{"],
        "interfaces": [],
    },
    "ruby": {
        "imports": [
            r"""require\s+['"]([^'"]+)['"]""",
            r"""require_relative\s+['"]([^'"]+)['"]""",
            r"include\s+(\w+)",
        ],
        "classes": [r"class\s+(\w+)(?:\s*<\s*(\w+))?", r"module\s+(\w+)"],
        "functions": [r"def\s+(?:self\.)?(\w+)"],
        "interfaces": [r"module\s+(\w+)"],
    },
    "vue": {
        "imports": _JS_IMPORTS,
        "classes": [r"""name:\s*['"](\w+)['"]"""],
        "functions": [],
        "interfaces": [],
    },
    "css": {
        "imports": [r"""@import\s+(?:url\s*\(\s*)?['"]?([^'"\s)]+)['"]?"""],
        "classes": [r"\.([\w-]+)\s*\{"],
        "functions": [],
        "interfaces": [],
    },
    "generic": {
        "imports": [r"""(?:import|include|require|use)\s+['"]?([^\s'"<>]+)['"]?"""],
        "classes": [r"(?:class|interface|struct|type)\s+(\w+)"],
        "functions": [r"(?:function|def|fn|func|method|fun)\s+(\w+)"],
        "interfaces": [],
    },
}

_NOISE_WORDS = {"if", "for", "while", "return", "new", "delete", "const", "let", "var"}
_MULTILINE_LANGS = {"python", "go", "java", "csharp", "kotlin", "ruby", "swift", "dart"}


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def get_lang(path: Path) -> str | None:
    """Return the PruvaGraph language id for *path*, or None if unsupported."""
    return LANG_MAP.get(path.suffix.lower())


def extract_code_file(path: Path) -> dict[str, Any]:
    """
    Extract a tiny knowledge-graph fragment from a single code file.

    Designed to run inside a ``ProcessPoolExecutor`` -- takes/returns only
    plain, picklable data.

    Returns:
        ``{"nodes": [...], "edges": [...], "source_file": str, "lang": str}``
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        content = ""

    ext = path.suffix.lower()
    lang = LANG_MAP.get(ext, "generic")
    patterns = PATTERNS.get(lang, PATTERNS["generic"])
    rel_path = str(path).replace("\\", "/")
    stem = path.stem

    flags_for = re.MULTILINE if lang in _MULTILINE_LANGS else 0

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()

    def add_node(node_id: str, label: str, ntype: str, **extra: Any) -> None:
        if node_id not in node_ids:
            node_ids.add(node_id)
            nodes.append({"id": node_id, "label": label, "type": ntype,
                           "file": rel_path, "lang": lang, **extra})

    def add_edge(source: str, target: str, relation: str = "imports") -> None:
        edges.append({"source": source, "target": target, "relation": relation})

    module_id = rel_path
    add_node(module_id, stem, "module", summary=f"{lang} module: {stem}", community=None)

    # -- Classes / structs / enums --------------------------------------------
    for pat in patterns.get("classes", []):
        for m in re.finditer(pat, content, flags_for):
            name = m.group(1)
            if not name or len(name) > 80:
                continue
            node_id = f"{rel_path}::{name}"
            add_node(node_id, name, "class", summary=f"{lang} class in {stem}")
            add_edge(module_id, node_id, "defines")
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                add_edge(node_id, m.group(2), "extends")

    # -- Interfaces / type aliases --------------------------------------------
    for pat in patterns.get("interfaces", []):
        for m in re.finditer(pat, content, flags_for):
            name = m.group(1)
            if not name or len(name) > 80:
                continue
            node_id = f"{rel_path}::{name}"
            add_node(node_id, name, "interface", summary=f"{lang} interface/type in {stem}")
            add_edge(module_id, node_id, "defines")

    # -- Functions / methods (capped to avoid noise on huge files) -----------
    func_count = 0
    for pat in patterns.get("functions", []):
        for m in re.finditer(pat, content, flags_for):
            name = m.group(1)
            if not name or len(name) > 80 or name in _NOISE_WORDS:
                continue
            node_id = f"{rel_path}::{name}"
            add_node(node_id, name, "function", summary=f"{lang} function in {stem}")
            add_edge(module_id, node_id, "defines")
            func_count += 1
            if func_count > 50:
                break
        if func_count > 50:
            break

    # -- Imports -> edges (+ external stub nodes) ----------------------------
    seen_imports: set[str] = set()
    for pat in patterns.get("imports", []):
        for m in re.finditer(pat, content, flags_for):
            imp = m.group(1)
            if not imp or len(imp) > 200 or imp in seen_imports:
                continue
            seen_imports.add(imp)

            target_id = _resolve_import(imp, path)
            add_edge(module_id, target_id, "imports")

            if not imp.startswith(".") and not imp.startswith("/"):
                pkg_name = _pkg_name(imp)
                add_node(target_id, pkg_name, "external", summary=f"External package: {pkg_name}")

    return {"nodes": nodes, "edges": edges, "source_file": rel_path, "lang": lang}


def is_code(path: Path) -> bool:
    return path.suffix.lower() in LANG_MAP


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _pkg_name(import_path: str) -> str:
    parts = import_path.split("/")
    if import_path.startswith("@"):
        return "/".join(parts[:2])
    return parts[0]


def _resolve_import(import_path: str, from_file: Path) -> str:
    if not import_path.startswith("."):
        return f"pkg:{_pkg_name(import_path)}"
    # Relative import -- resolve against the importing file's directory.
    base = (from_file.parent / import_path).resolve()
    try:
        return str(base.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(base).replace("\\", "/")

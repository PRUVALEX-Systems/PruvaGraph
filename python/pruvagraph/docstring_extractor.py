"""
N2 — Docstring / Comment Extractor

Extracts function/class docstrings as pre-computed summaries.
These summaries replace LLM-generated ones — same quality, zero cost.

Supports: Python, TypeScript/JS, Go, Rust, Java, Kotlin, Swift, PHP, C/C++.
Estimated savings: 50–90% of summary calls for well-documented codebases.
"""
from __future__ import annotations

import re
from pathlib import Path

# ── Language-specific extraction patterns ─────────────────────────────────────

def extract_docstrings(path: Path, lang: str) -> dict[str, str]:
    """
    Return {node_id: summary} for all documented symbols in the file.
    node_id format: "{path}::{symbol_name}"
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    extractor = _EXTRACTORS.get(lang)
    if extractor is None:
        return {}

    return extractor(str(path), content)


# ── Python ────────────────────────────────────────────────────────────────────

def _extract_python(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    # class/def + triple-quoted docstring
    pattern = re.compile(
        r'(?:^|\n)(?:async\s+)?(?:def|class)\s+(\w+)[^\n:]*:\s*\n'
        r'\s+(?:"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'\'\')',
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        name = m.group(1)
        doc  = m.group(2) or m.group(3) or ""
        clean = _clean_docstring(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    # Module-level docstring
    module_doc = re.match(r'\s*(?:"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'\'\')', content)
    if module_doc:
        doc = module_doc.group(1) or module_doc.group(2) or ""
        clean = _clean_docstring(doc)
        if clean:
            results[file_id] = clean

    return results


# ── TypeScript / JavaScript ───────────────────────────────────────────────────

def _extract_jsdoc(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    # /** ... */ before function/class/const
    pattern = re.compile(
        r"/\*\*\s*([\s\S]*?)\s*\*/\s*\n\s*"
        r"(?:export\s+)?(?:default\s+)?(?:async\s+)?"
        r"(?:function\s+(\w+)|class\s+(\w+)|const\s+(\w+)|(\w+)\s*[=:])",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        doc  = m.group(1) or ""
        name = m.group(2) or m.group(3) or m.group(4) or m.group(5)
        if not name:
            continue
        clean = _clean_jsdoc(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    # Single-line comments before arrow functions
    arrow_pattern = re.compile(
        r"//\s*(.+)\n\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(",
        re.MULTILINE,
    )
    for m in arrow_pattern.finditer(content):
        comment, name = m.group(1).strip(), m.group(2)
        if len(comment) > 15:
            results[f"{file_id}::{name}"] = comment[:150]

    return results


# ── Go ────────────────────────────────────────────────────────────────────────

def _extract_go(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    # Go doc comments: consecutive // lines before func/type
    pattern = re.compile(
        r"((?:^//[^\n]*\n)+)\s*(?:func|type)\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        comment_block = m.group(1)
        name = m.group(2)
        # Extract text from comment lines
        lines = [l.lstrip("/").strip() for l in comment_block.strip().split("\n")]
        doc = " ".join(l for l in lines if l)
        clean = _first_sentence(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    return results


# ── Rust ─────────────────────────────────────────────────────────────────────

def _extract_rust(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    # /// doc comments before pub fn / struct / enum / trait
    pattern = re.compile(
        r"((?:^///[^\n]*\n)+)\s*(?:pub(?:\([^)]*\))?\s+)?(?:fn|struct|enum|trait|impl)\s+(\w+)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        comment_block = m.group(1)
        name = m.group(2)
        lines = [l.lstrip("/").strip() for l in comment_block.strip().split("\n")]
        doc = " ".join(l for l in lines if l)
        clean = _first_sentence(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    return results


# ── Java / Kotlin ─────────────────────────────────────────────────────────────

def _extract_javadoc(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    pattern = re.compile(
        r"/\*\*\s*([\s\S]*?)\s*\*/\s*\n\s*"
        r"(?:@\w+\s+)*"
        r"(?:public|private|protected|internal|override)?\s*"
        r"(?:static|abstract|final|open|suspend)?\s*"
        r"(?:fun|class|interface|object|void|\w+)\s+(\w+)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        doc  = m.group(1)
        name = m.group(2)
        clean = _clean_jsdoc(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    return results


# ── Swift ─────────────────────────────────────────────────────────────────────

def _extract_swift(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    # Swift uses /// comments
    pattern = re.compile(
        r"((?:^///[^\n]*\n)+)\s*(?:public|private|internal|open|fileprivate)?\s*"
        r"(?:func|class|struct|enum|protocol|var|let)\s+(\w+)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        comment_block = m.group(1)
        name = m.group(2)
        lines = [l.lstrip("/").strip() for l in comment_block.strip().split("\n")]
        # Filter - Parameters, - Returns: lines
        doc_lines = [l for l in lines if l and not l.startswith("- ")]
        doc = " ".join(doc_lines)
        clean = _first_sentence(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    return results


# ── C / C++ ───────────────────────────────────────────────────────────────────

def _extract_c(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    # Doxygen-style /** or /* comments before function signatures
    pattern = re.compile(
        r"/\*[*!]\s*([\s\S]*?)\s*\*/\s*\n\s*"
        r"(?:static\s+|extern\s+|inline\s+)*"
        r"[\w\s*]+\s+(\w+)\s*\(",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        doc  = m.group(1)
        name = m.group(2)
        if name in ("if", "while", "for", "switch"):
            continue
        clean = _clean_jsdoc(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    return results


# ── PHP ───────────────────────────────────────────────────────────────────────

def _extract_php(file_id: str, content: str) -> dict[str, str]:
    results: dict[str, str] = {}

    pattern = re.compile(
        r"/\*\*\s*([\s\S]*?)\s*\*/\s*\n\s*"
        r"(?:public|private|protected|static)?\s*"
        r"(?:function|class)\s+(\w+)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        doc  = m.group(1)
        name = m.group(2)
        clean = _clean_jsdoc(doc)
        if clean and len(clean) > 10:
            results[f"{file_id}::{name}"] = clean

    return results


# ── Extractors dispatch table ─────────────────────────────────────────────────

_EXTRACTORS = {
    "python":     _extract_python,
    "typescript": _extract_jsdoc,
    "javascript": _extract_jsdoc,
    "tsx":        _extract_jsdoc,
    "jsx":        _extract_jsdoc,
    "go":         _extract_go,
    "rust":       _extract_rust,
    "java":       _extract_javadoc,
    "kotlin":     _extract_javadoc,
    "swift":      _extract_swift,
    "c":          _extract_c,
    "cpp":        _extract_c,
    "cs":         _extract_javadoc,
    "php":        _extract_php,
}


# ── Text cleaning helpers ─────────────────────────────────────────────────────

def _clean_docstring(text: str) -> str:
    """Clean Python docstring — first sentence only."""
    # Normalize whitespace
    text = re.sub(r"\n\s+", " ", text).strip()
    # Remove Args:, Returns:, Raises: sections
    text = re.sub(r"\s*(Args|Returns|Raises|Note|Example|See Also):[\s\S]*$", "", text, flags=re.I)
    return _first_sentence(text.strip())


def _clean_jsdoc(text: str) -> str:
    """Clean JSDoc / Javadoc comment — first sentence only."""
    # Remove leading * from each line
    text = re.sub(r"^\s*\*\s*", "", text, flags=re.MULTILINE)
    # Remove @param, @return, @throws tags
    text = re.sub(r"@\w+[^\n]*", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return _first_sentence(text)


def _first_sentence(text: str) -> str:
    """Return first sentence (up to 150 chars)."""
    text = text.strip()
    # Stop at first sentence-ending punctuation followed by space or end
    m = re.match(r"^([^.!?]{5,150}[.!?])", text)
    if m:
        return m.group(1).strip()
    # If no punctuation, return up to 120 chars
    return text[:120].strip() if len(text) > 10 else ""


# ── Extension → language mapping ─────────────────────────────────────────────

EXT_TO_LANG = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".jsx": "jsx", ".mjs": "javascript", ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".swift": "swift",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".cs": "cs",
    ".php": "php",
}


def get_lang(path: Path) -> str | None:
    return EXT_TO_LANG.get(path.suffix.lower())

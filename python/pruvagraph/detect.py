"""
File discovery + classification — Stage 0 of the PruvaGraph pipeline.

Walks the project root, skips noise directories (node_modules, .git, build
output, virtualenvs, the pruvagraph-out directory itself, ...), and tags
every remaining file as CODE / DOCUMENT / PAPER / IMAGE / OTHER.

- CODE files     → handled by extract.py (tree-sitter/regex, zero cost)
- DOCUMENT/PAPER/IMAGE → handled by llm_extract.py (LLM, batched + deduped)
- OTHER          → ignored entirely
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# File type classification
# ──────────────────────────────────────────────────────────────────────────────


class FileType(str, Enum):
    CODE = "code"
    DOCUMENT = "document"
    PAPER = "paper"
    IMAGE = "image"
    OTHER = "other"


# Mirrors analyzer.js LANG_MAP — anything PruvaGraph can parse for free.
CODE_EXTENSIONS: frozenset[str] = frozenset({
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx", ".mts",
    ".py", ".pyw",
    ".go",
    ".rs",
    ".java",
    ".kt", ".kts",
    ".swift",
    ".cs",
    ".cpp", ".cc", ".cxx", ".hpp", ".h",
    ".c",
    ".rb",
    ".php",
    ".vue",
    ".svelte",
    ".dart",
    ".scala",
    ".zig",
    ".lua",
    ".r", ".R",
    ".sh", ".bash",
    ".yaml", ".yml",
    ".json",
    ".toml",
    ".css", ".scss", ".sass", ".less",
    ".html", ".htm",
    ".tf", ".hcl",
    ".sql",
})

# Text documents — sent to LLM extraction (cheap/batched).
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".markdown", ".rst", ".txt", ".adoc", ".docx",
})

# PDFs get their own bucket — often need OCR / vision routing.
PAPER_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

# Images — diagrams, screenshots, architecture drawings.
IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
})

# Directories never worth walking into.
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset({
    "node_modules", ".git", "dist", "build", "out",
    "__pycache__", ".pruvagraph", "pruvagraph-out",
    ".venv", "venv", "env", ".env",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".next", ".nuxt", ".svelte-kit", "target", "vendor",
    ".idea", ".vscode-test", "coverage", ".tox", "egg-info",
})

# Hard cap so a single huge generated file doesn't blow up extraction.
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def classify(path: Path) -> FileType:
    """Classify a single file by extension."""
    ext = path.suffix.lower()
    if ext in CODE_EXTENSIONS:
        return FileType.CODE
    if ext in DOCUMENT_EXTENSIONS:
        return FileType.DOCUMENT
    if ext in PAPER_EXTENSIONS:
        return FileType.PAPER
    if ext in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    return FileType.OTHER


def collect_files(
    root: Path,
    exclude_dirs: frozenset[str] | None = None,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> list[tuple[Path, FileType]]:
    """
    Walk *root* and return ``[(path, FileType), ...]`` for every file worth
    analysing (CODE / DOCUMENT / PAPER / IMAGE). ``FileType.OTHER`` files and
    excluded directories are skipped entirely.

    Args:
        root:           Project root to scan.
        exclude_dirs:   Directory names to skip (defaults to
                         :data:`DEFAULT_EXCLUDE_DIRS`).
        max_size_bytes: Files larger than this are skipped (likely generated
                         artefacts, not useful for the graph).

    Returns:
        List of ``(absolute_path, FileType)`` tuples, sorted for determinism.
    """
    exclude = exclude_dirs if exclude_dirs is not None else DEFAULT_EXCLUDE_DIRS
    root = Path(root).resolve()
    results: list[tuple[Path, FileType]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place so os.walk doesn't descend.
        dirnames[:] = [d for d in dirnames if d not in exclude]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            ftype = classify(fpath)
            if ftype is FileType.OTHER:
                continue
            try:
                if fpath.stat().st_size > max_size_bytes:
                    continue
            except OSError:
                continue
            results.append((fpath, ftype))

    results.sort(key=lambda pair: str(pair[0]))
    return results


def summarize(files: list[tuple[Path, FileType]]) -> dict[str, int]:
    """Quick counts per FileType — handy for progress reporting."""
    counts: dict[str, int] = {}
    for _, ftype in files:
        counts[ftype.value] = counts.get(ftype.value, 0) + 1
    return counts

"""
N9 — AST Diff / Patch Updates

Uses git diff to identify WHICH functions changed in a file,
allowing partial re-extraction instead of full file re-analysis.

Current: file changed → re-extract ENTIRE file (expensive)
New:     file changed → only re-extract changed functions (cheap)

Estimated savings: 60–80% token reduction on incremental builds.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def get_changed_functions(path: Path, root: Path) -> list[str] | None:
    """
    Return list of function/class names changed in this file since HEAD.
    Returns None if we can't determine (→ full re-extract fallback).
    Returns [] if no changes detected.

    Uses git diff hunk headers which contain the enclosing function name:
      @@ -10,7 +10,7 @@ def my_function():
    """
    try:
        rel_path = path.relative_to(root)
    except ValueError:
        return None

    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", str(rel_path)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None  # git not available

    diff_output = result.stdout
    if not diff_output:
        return []  # No changes

    # Git diff hunk header: @@ -L,N +L,N @@ context
    # The context part (after the last @@) contains the enclosing symbol
    hunk_headers = re.findall(r"^@@[^@]+@@\s*(.*)$", diff_output, re.MULTILINE)

    func_names: list[str] = []
    for header in hunk_headers:
        # Match: def foo / class Foo / func foo / function foo / fn foo
        m = re.search(
            r"(?:def|class|func|function|fn|sub|proc)\s+(\w+)",
            header,
        )
        if m:
            func_names.append(m.group(1))

    return func_names or None  # None = could not parse → full re-extract


def get_changed_files(root: Path, since: str = "HEAD") -> list[Path]:
    """
    Return list of files changed since a given git ref.
    Used by --update mode to identify which files need re-extraction.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", since],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return [root / l for l in lines if (root / l).exists()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def get_untracked_files(root: Path) -> list[Path]:
    """Return new untracked files (not yet committed)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return [root / l for l in lines if (root / l).exists()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def should_full_reextract(path: Path, root: Path, threshold: int = 5) -> bool:
    """
    Returns True if full re-extraction is needed.
    Returns False if partial (function-level) update is sufficient.

    Heuristic: >threshold changed functions = full re-extract anyway.
    """
    changed = get_changed_functions(path, root)
    if changed is None:
        return True   # Can't determine → safe to full re-extract
    if len(changed) == 0:
        return False  # No changes at all
    return len(changed) > threshold


def get_git_file_hash(path: Path, root: Path) -> str | None:
    """
    Get the git object hash (SHA1) for a file as it exists in HEAD.
    More reliable than mtime for incremental detection.
    """
    try:
        rel = path.relative_to(root)
        result = subprocess.run(
            ["git", "hash-object", str(rel)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def is_git_repo(root: Path) -> bool:
    """Check if root is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root,
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

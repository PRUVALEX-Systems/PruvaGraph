"""
DriftGuard — validate AI-suggested imports against your actual environment.

Catches hallucinated or wrong-version API calls before they reach your editor
by introspecting the real Python environment (importlib.metadata + dir()).

Public API:
    index_installed_packages(root)          → dict[str, str]
    validate_import(module, symbol, root)   → ValidationResult
    scan_ai_suggestion(diff_text, root)     → list[ValidationResult]

Usage via MCP (Claude Code / Cursor):
    validate_import(module="pandas", symbol="read_csv")
    scan_suggestion(diff="...")

Usage via CLI:
    pruvagraph validate-import pandas read_csv
"""
from __future__ import annotations

import difflib
import importlib
import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of validating a single import."""
    valid: bool
    module: str
    symbol: str | None
    actual_version: str | None
    suggestion: str | None
    severity: str  # "error" | "warning" | "info"


# ---------------------------------------------------------------------------
# 1. index_installed_packages
# ---------------------------------------------------------------------------

def index_installed_packages(root: Path) -> dict[str, str]:
    """
    Return {package_name: version} for every installed distribution.

    Uses importlib.metadata which reads from the current Python environment.
    The `root` parameter is accepted for interface consistency with other
    PruvaGraph functions but is not used for package discovery (Python
    packages are environment-scoped, not project-scoped).
    """
    result: dict[str, str] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        version = dist.metadata["Version"]
        if name and version:
            result[name] = version
    return result


# ---------------------------------------------------------------------------
# 2. validate_import
# ---------------------------------------------------------------------------

def _get_module_version(module_name: str) -> str | None:
    """Try to find the installed version for a module."""
    # Map top-level module name to distribution name
    top_level = module_name.split(".")[0]
    try:
        return importlib.metadata.version(top_level)
    except importlib.metadata.PackageNotFoundError:
        pass
    # stdlib modules won't have a distribution — return sentinel
    try:
        mod = importlib.import_module(top_level)
        if mod is not None:
            return "stdlib"
    except Exception:
        pass
    return None


def validate_import(
    module_name: str,
    symbol: str | None,
    root: Path,
) -> ValidationResult:
    """
    Validate that ``module_name`` (and optionally ``symbol``) actually exists
    in the current Python environment.

    Returns a ValidationResult with:
      - valid=True   if module+symbol are importable
      - valid=False  with a suggestion if symbol is close to a real name
      - valid=False  with "not installed" if the module doesn't exist at all
    """
    # --- Try importing the module ---
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        return ValidationResult(
            valid=False,
            module=module_name,
            symbol=symbol,
            actual_version=None,
            suggestion=f"Module '{module_name}' not found — package may not be installed.",
            severity="error",
        )
    except Exception as exc:
        # Module exists but crashes on import (e.g. missing C extension)
        return ValidationResult(
            valid=False,
            module=module_name,
            symbol=symbol,
            actual_version=None,
            suggestion=f"Module '{module_name}' failed to import: {exc}",
            severity="error",
        )

    version = _get_module_version(module_name)

    # --- Module-only check (no symbol) ---
    if symbol is None:
        return ValidationResult(
            valid=True,
            module=module_name,
            symbol=None,
            actual_version=version,
            suggestion=None,
            severity="info",
        )

    # --- Check symbol existence ---
    if hasattr(mod, symbol):
        return ValidationResult(
            valid=True,
            module=module_name,
            symbol=symbol,
            actual_version=version,
            suggestion=None,
            severity="info",
        )

    # --- Symbol not found — try fuzzy match ---
    available = dir(mod)
    # Filter to public names for better suggestions
    public_names = [n for n in available if not n.startswith("_")]
    matches = difflib.get_close_matches(symbol, public_names, n=3, cutoff=0.6)

    suggestion: str | None = None
    if matches:
        suggestion = f"Did you mean '{matches[0]}'?"
        if len(matches) > 1:
            suggestion += f" (also: {', '.join(matches[1:])})"
    else:
        suggestion = (
            f"Symbol '{symbol}' not found in {module_name}"
            + (f" v{version}" if version and version != "stdlib" else "")
            + "."
        )

    return ValidationResult(
        valid=False,
        module=module_name,
        symbol=symbol,
        actual_version=version,
        suggestion=suggestion,
        severity="warning",
    )


# ---------------------------------------------------------------------------
# 3. scan_ai_suggestion
# ---------------------------------------------------------------------------

# Match added lines in a diff that contain import statements
_IMPORT_RE = re.compile(
    r"^\+\s*(?:"
    r"from\s+([\w.]+)\s+import\s+([\w*]+)"  # from X import Y
    r"|"
    r"import\s+([\w.]+)"                      # import X
    r")",
    re.MULTILINE,
)


def scan_ai_suggestion(
    diff_text: str,
    root: Path,
) -> list[ValidationResult]:
    """
    Parse a unified diff for added import lines and validate each one.

    Only examines lines starting with '+' (additions).
    Returns a list of ValidationResult — includes BOTH valid and invalid
    results for completeness, but callers typically filter to invalid only.
    """
    if not diff_text.strip():
        return []

    results: list[ValidationResult] = []
    seen: set[tuple[str, str | None]] = set()

    for match in _IMPORT_RE.finditer(diff_text):
        # Group 1,2 = from X import Y  |  Group 3 = import X
        if match.group(1):
            module_name = match.group(1)
            symbol = match.group(2)
            if symbol == "*":
                symbol = None  # 'from X import *' — just check the module
        else:
            module_name = match.group(3)
            symbol = None

        key = (module_name, symbol)
        if key in seen:
            continue
        seen.add(key)

        result = validate_import(module_name, symbol, root)
        results.append(result)

    return results

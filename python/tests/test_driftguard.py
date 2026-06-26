"""
Tests for pruvagraph.driftguard — DriftGuard MVP.

Written TEST-FIRST (Phase 2 discipline): these tests define the contract
that driftguard.py must satisfy.

Coverage:
  - index_installed_packages: reads real env, returns dict[str, str]
  - validate_import: valid symbol, renamed/typo'd symbol, unknown package
  - scan_ai_suggestion: flags bad imports in diffs, ignores removals, empty diff
  - ValidationResult dataclass shape
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Import module under test
# ---------------------------------------------------------------------------

from pruvagraph.driftguard import (
    ValidationResult,
    index_installed_packages,
    scan_ai_suggestion,
    validate_import,
)


# ===========================================================================
# 1. ValidationResult dataclass
# ===========================================================================

class TestValidationResult:
    def test_dataclass_fields(self):
        r = ValidationResult(
            valid=True,
            module="json",
            symbol="loads",
            actual_version="stdlib",
            suggestion=None,
            severity="info",
        )
        assert r.valid is True
        assert r.module == "json"
        assert r.symbol == "loads"
        assert r.actual_version == "stdlib"
        assert r.suggestion is None
        assert r.severity == "info"

    def test_invalid_result_has_suggestion(self):
        r = ValidationResult(
            valid=False,
            module="json",
            symbol="loasd",
            actual_version="stdlib",
            suggestion="Did you mean 'loads'?",
            severity="warning",
        )
        assert r.valid is False
        assert "loads" in r.suggestion


# ===========================================================================
# 2. index_installed_packages
# ===========================================================================

class TestIndexInstalledPackages:
    def test_reads_real_env(self, tmp_path):
        """Must return a dict with at least pytest and networkx (both are
        installed in this test environment)."""
        pkgs = index_installed_packages(tmp_path)
        assert isinstance(pkgs, dict)
        # Normalize names to lowercase for comparison
        lower_pkgs = {k.lower(): v for k, v in pkgs.items()}
        assert "pytest" in lower_pkgs, f"pytest not found in {list(lower_pkgs.keys())[:10]}"
        assert "networkx" in lower_pkgs, f"networkx not found in {list(lower_pkgs.keys())[:10]}"

    def test_versions_are_strings(self, tmp_path):
        pkgs = index_installed_packages(tmp_path)
        for name, version in list(pkgs.items())[:5]:
            assert isinstance(version, str), f"{name} version is {type(version)}, expected str"
            assert len(version) > 0, f"{name} has empty version string"

    def test_returns_nonempty(self, tmp_path):
        pkgs = index_installed_packages(tmp_path)
        assert len(pkgs) > 0, "No packages found — this should never happen in a test env"


# ===========================================================================
# 3. validate_import — valid symbol
# ===========================================================================

class TestValidateImportValid:
    def test_stdlib_module_valid(self, tmp_path):
        """json.loads is a stdlib function that always exists."""
        result = validate_import("json", "loads", tmp_path)
        assert result.valid is True
        assert result.module == "json"
        assert result.symbol == "loads"

    def test_module_only_no_symbol(self, tmp_path):
        """validate_import('json', None) should succeed — module exists."""
        result = validate_import("json", None, tmp_path)
        assert result.valid is True

    def test_installed_package_valid(self, tmp_path):
        """pytest.raises is a real symbol in an installed package."""
        result = validate_import("pytest", "raises", tmp_path)
        assert result.valid is True
        assert result.actual_version is not None


# ===========================================================================
# 4. validate_import — renamed/typo'd symbol
# ===========================================================================

class TestValidateImportRenamed:
    def test_typo_returns_suggestion(self, tmp_path):
        """json.loasd doesn't exist but is close to json.loads."""
        result = validate_import("json", "loasd", tmp_path)
        assert result.valid is False
        assert result.suggestion is not None
        assert "loads" in result.suggestion

    def test_completely_wrong_symbol(self, tmp_path):
        """json.xyzzy_does_not_exist — too far from any real name."""
        result = validate_import("json", "xyzzy_does_not_exist_abcdef", tmp_path)
        assert result.valid is False


# ===========================================================================
# 5. validate_import — unknown package
# ===========================================================================

class TestValidateImportUnknown:
    def test_nonexistent_package(self, tmp_path):
        result = validate_import("this_package_does_not_exist_xyz_42", None, tmp_path)
        assert result.valid is False
        assert result.suggestion is not None
        assert "not installed" in result.suggestion.lower() or "not found" in result.suggestion.lower()

    def test_nonexistent_submodule(self, tmp_path):
        result = validate_import("os.nonexistent_submodule_xyz", None, tmp_path)
        assert result.valid is False


# ===========================================================================
# 6. scan_ai_suggestion
# ===========================================================================

class TestScanAiSuggestion:
    def test_flags_removed_method(self, tmp_path):
        """A diff that adds 'from json import loasd' should flag it."""
        diff = (
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1,3 +1,4 @@\n"
            " import os\n"
            "+from json import loasd\n"
            " \n"
            " def main():\n"
        )
        results = scan_ai_suggestion(diff, tmp_path)
        assert len(results) >= 1
        bad = [r for r in results if not r.valid]
        assert len(bad) >= 1
        assert bad[0].module == "json"
        assert bad[0].symbol == "loasd"

    def test_valid_import_returns_empty(self, tmp_path):
        """A diff with a valid import should return no invalid results."""
        diff = (
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1,3 +1,4 @@\n"
            " import os\n"
            "+from json import loads\n"
            " \n"
        )
        results = scan_ai_suggestion(diff, tmp_path)
        # All results should be valid (or empty list)
        bad = [r for r in results if not r.valid]
        assert len(bad) == 0

    def test_ignores_removed_lines(self, tmp_path):
        """Lines starting with '-' are removals, not additions — skip them."""
        diff = (
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-from json import loasd\n"
            "+from json import loads\n"
            " \n"
        )
        results = scan_ai_suggestion(diff, tmp_path)
        bad = [r for r in results if not r.valid]
        assert len(bad) == 0, "Should not flag removed lines"

    def test_empty_diff(self, tmp_path):
        results = scan_ai_suggestion("", tmp_path)
        assert results == []

    def test_plain_import_statement(self, tmp_path):
        """'import json' (no 'from') should be validated too."""
        diff = (
            "+import this_package_does_not_exist_xyz_42\n"
        )
        results = scan_ai_suggestion(diff, tmp_path)
        bad = [r for r in results if not r.valid]
        assert len(bad) >= 1

    def test_multiple_imports(self, tmp_path):
        """Multiple added imports — both should be checked."""
        diff = (
            "+from json import loads\n"
            "+from json import loasd\n"
        )
        results = scan_ai_suggestion(diff, tmp_path)
        bad = [r for r in results if not r.valid]
        assert len(bad) >= 1
        assert any(r.symbol == "loasd" for r in bad)

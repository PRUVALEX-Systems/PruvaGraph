"""
Tests for M1 — Monorepo Router (monorepo.py).

Covers:
  - detect_monorepo() → None for single-repo
  - pnpm-workspace.yaml detection
  - nx.json detection
  - lerna.json detection
  - rush.json detection (with // comments)
  - npm/yarn workspaces in package.json
  - Python monorepo (≥2 subdirs with pyproject.toml)
  - Generic detection (packages/ or apps/ with ≥2 subdirs)
  - find_cross_package_edges() import scanning
  - PackageInfo language detection (python / javascript / mixed / unknown)
  - _make_package() name extraction from package.json and pyproject.toml
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pruvagraph.monorepo import (
    MonorepoLayout,
    PackageInfo,
    _make_package,
    detect_monorepo,
    find_cross_package_edges,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    _write(path, json.dumps(data))


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — None for single-repo
# ──────────────────────────────────────────────────────────────────────────────

class TestSingleRepo:
    def test_empty_dir_returns_none(self, tmp_path):
        assert detect_monorepo(tmp_path) is None

    def test_single_package_json_not_workspaces(self, tmp_path):
        _write_json(tmp_path / "package.json", {"name": "my-app", "version": "1.0.0"})
        assert detect_monorepo(tmp_path) is None

    def test_single_pyproject_returns_none(self, tmp_path):
        _write(tmp_path / "pyproject.toml", '[project]\nname = "myapp"\n')
        assert detect_monorepo(tmp_path) is None


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — pnpm
# ──────────────────────────────────────────────────────────────────────────────

class TestPnpm:
    def test_pnpm_workspace_yaml_detected(self, tmp_path):
        # Create workspace file
        _write(tmp_path / "pnpm-workspace.yaml", "packages:\n  - packages/*\n")
        # Create packages
        for pkg in ["pkg-a", "pkg-b"]:
            _write_json(tmp_path / "packages" / pkg / "package.json",
                        {"name": pkg, "version": "1.0.0"})

        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "pnpm"
        pkg_names = {p.name for p in layout.packages}
        assert "pkg-a" in pkg_names
        assert "pkg-b" in pkg_names

    def test_pnpm_without_packages_dir_returns_none(self, tmp_path):
        _write(tmp_path / "pnpm-workspace.yaml", "packages:\n  - packages/*\n")
        # No packages/ dir created → no packages found
        layout = detect_monorepo(tmp_path)
        # Either None or empty packages list
        assert layout is None or len(layout.packages) == 0


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — Nx
# ──────────────────────────────────────────────────────────────────────────────

class TestNx:
    def test_nx_json_with_apps_dir_detected(self, tmp_path):
        _write_json(tmp_path / "nx.json", {"version": 2})
        for app in ["web", "api"]:
            _write_json(tmp_path / "apps" / app / "package.json",
                        {"name": f"@myorg/{app}", "version": "0.0.1"})

        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "nx"
        assert len(layout.packages) >= 2


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — Lerna
# ──────────────────────────────────────────────────────────────────────────────

class TestLerna:
    def test_lerna_json_detected(self, tmp_path):
        _write_json(tmp_path / "lerna.json", {"version": "1.0.0", "packages": ["packages/*"]})
        for pkg in ["core", "utils"]:
            _write_json(tmp_path / "packages" / pkg / "package.json",
                        {"name": f"@scope/{pkg}", "version": "1.0.0"})

        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "lerna"

    def test_lerna_default_packages_glob(self, tmp_path):
        """Lerna defaults to packages/* if 'packages' key is missing."""
        _write_json(tmp_path / "lerna.json", {"version": "2.0.0"})
        for pkg in ["alpha", "beta"]:
            _write_json(tmp_path / "packages" / pkg / "package.json",
                        {"name": pkg, "version": "1.0.0"})
        layout = detect_monorepo(tmp_path)
        assert layout is not None


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — Rush (with // comments)
# ──────────────────────────────────────────────────────────────────────────────

class TestRush:
    def test_rush_json_with_comments_parsed(self, tmp_path):
        rush_content = """{
  // Rush workspace
  "rushVersion": "5.90.0",
  "projects": [
    { "packageName": "@myorg/lib", "projectFolder": "lib" },
    { "packageName": "@myorg/app", "projectFolder": "app" }
  ]
}"""
        _write(tmp_path / "rush.json", rush_content)
        (tmp_path / "lib").mkdir()
        (tmp_path / "app").mkdir()

        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "rush"
        pkg_names = {p.name for p in layout.packages}
        assert "@myorg/lib" in pkg_names
        assert "@myorg/app" in pkg_names


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — npm/yarn workspaces
# ──────────────────────────────────────────────────────────────────────────────

class TestNpmWorkspaces:
    def test_npm_workspaces_array_detected(self, tmp_path):
        _write_json(tmp_path / "package.json", {
            "name": "root",
            "workspaces": ["packages/*"]
        })
        for pkg in ["frontend", "backend"]:
            _write_json(tmp_path / "packages" / pkg / "package.json",
                        {"name": pkg, "version": "1.0.0"})

        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "npm-workspaces"

    def test_npm_workspaces_object_form(self, tmp_path):
        """Yarn uses {"workspaces": {"packages": [...]}} form."""
        _write_json(tmp_path / "package.json", {
            "name": "root",
            "workspaces": {"packages": ["packages/*"]}
        })
        for pkg in ["a", "b"]:
            _write_json(tmp_path / "packages" / pkg / "package.json",
                        {"name": pkg, "version": "0.1.0"})

        layout = detect_monorepo(tmp_path)
        assert layout is not None


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — Python
# ──────────────────────────────────────────────────────────────────────────────

class TestPythonMonorepo:
    def test_two_pyproject_tomls_detected(self, tmp_path):
        for pkg in ["core", "cli"]:
            _write(tmp_path / pkg / "pyproject.toml",
                   f'[project]\nname = "{pkg}"\nversion = "0.1.0"\n')

        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "python"
        pkg_names = {p.name for p in layout.packages}
        assert "core" in pkg_names
        assert "cli"  in pkg_names

    def test_single_pyproject_not_python_monorepo(self, tmp_path):
        _write(tmp_path / "core" / "pyproject.toml",
               '[project]\nname = "core"\nversion = "0.1.0"\n')
        layout = detect_monorepo(tmp_path)
        # Only 1 package → not a Python monorepo
        assert layout is None or layout.tool != "python"

    def test_setup_py_also_detected(self, tmp_path):
        _write(tmp_path / "pkg_a" / "setup.py", "from setuptools import setup\nsetup(name='pkg_a')")
        _write(tmp_path / "pkg_b" / "setup.py", "from setuptools import setup\nsetup(name='pkg_b')")
        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "python"


# ──────────────────────────────────────────────────────────────────────────────
# detect_monorepo — Generic
# ──────────────────────────────────────────────────────────────────────────────

class TestGenericMonorepo:
    def test_packages_dir_with_two_subdirs_detected(self, tmp_path):
        (tmp_path / "packages" / "alpha").mkdir(parents=True)
        (tmp_path / "packages" / "beta").mkdir(parents=True)
        layout = detect_monorepo(tmp_path)
        assert layout is not None
        assert layout.tool == "generic"

    def test_one_subdir_not_enough(self, tmp_path):
        (tmp_path / "packages" / "solo").mkdir(parents=True)
        # Only 1 sub-package → not enough for generic monorepo
        layout = detect_monorepo(tmp_path)
        assert layout is None or len(layout.packages) < 2


# ──────────────────────────────────────────────────────────────────────────────
# find_cross_package_edges
# ──────────────────────────────────────────────────────────────────────────────

class TestCrossPackageEdges:
    def _make_packages(self, tmp_path) -> list[PackageInfo]:
        """Create two packages where pkg_a imports from pkg_b."""
        (tmp_path / "pkg_a").mkdir()
        (tmp_path / "pkg_b").mkdir()
        _write(tmp_path / "pkg_a" / "main.py",
               "from pkg_b import helper\nimport pkg_b.utils")
        _write(tmp_path / "pkg_b" / "helper.py", "def helper(): pass")
        return [
            PackageInfo(name="pkg_a", root=tmp_path / "pkg_a", language="python"),
            PackageInfo(name="pkg_b", root=tmp_path / "pkg_b", language="python"),
        ]

    def test_python_import_creates_cross_edge(self, tmp_path):
        packages = self._make_packages(tmp_path)
        edges = find_cross_package_edges(packages)
        assert ("pkg_a", "pkg_b", "imports_from") in edges

    def test_no_cross_imports_returns_empty(self, tmp_path):
        (tmp_path / "pkg_a").mkdir()
        (tmp_path / "pkg_b").mkdir()
        _write(tmp_path / "pkg_a" / "main.py", "x = 1\n")
        _write(tmp_path / "pkg_b" / "lib.py", "y = 2\n")
        packages = [
            PackageInfo(name="pkg_a", root=tmp_path / "pkg_a", language="python"),
            PackageInfo(name="pkg_b", root=tmp_path / "pkg_b", language="python"),
        ]
        edges = find_cross_package_edges(packages)
        assert edges == []

    def test_edges_are_unique(self, tmp_path):
        (tmp_path / "pkg_a").mkdir()
        (tmp_path / "pkg_b").mkdir()
        # Multiple imports of pkg_b from pkg_a
        _write(tmp_path / "pkg_a" / "main.py",
               "from pkg_b import a\nfrom pkg_b import b\nimport pkg_b.c")
        packages = [
            PackageInfo(name="pkg_a", root=tmp_path / "pkg_a", language="python"),
            PackageInfo(name="pkg_b", root=tmp_path / "pkg_b", language="python"),
        ]
        edges = find_cross_package_edges(packages)
        # Should only have one edge, not three
        assert edges.count(("pkg_a", "pkg_b", "imports_from")) == 1


# ──────────────────────────────────────────────────────────────────────────────
# PackageInfo — language and name detection
# ──────────────────────────────────────────────────────────────────────────────

class TestPackageInfo:
    def test_js_package_language_detected(self, tmp_path):
        _write_json(tmp_path / "pkg" / "package.json", {"name": "my-lib", "version": "1.0.0"})
        info = _make_package(tmp_path / "pkg")
        assert info.language == "javascript"
        assert info.name == "my-lib"

    def test_python_package_language_detected(self, tmp_path):
        _write(tmp_path / "pkg" / "pyproject.toml",
               '[project]\nname = "mylib"\nversion = "0.1.0"\n')
        info = _make_package(tmp_path / "pkg")
        assert info.language == "python"
        assert info.name == "mylib"

    def test_mixed_language_both_files(self, tmp_path):
        _write_json(tmp_path / "pkg" / "package.json", {"name": "hybrid"})
        _write(tmp_path / "pkg" / "pyproject.toml",
               '[project]\nname = "hybrid-py"\n')
        info = _make_package(tmp_path / "pkg")
        assert info.language == "mixed"

    def test_unknown_language_empty_dir(self, tmp_path):
        (tmp_path / "pkg").mkdir()
        info = _make_package(tmp_path / "pkg")
        assert info.language == "unknown"
        assert info.name == "pkg"  # falls back to dirname

    def test_name_overridden_by_arg(self, tmp_path):
        (tmp_path / "pkg").mkdir()
        info = _make_package(tmp_path / "pkg", name="custom-name")
        assert info.name == "custom-name"

    def test_setup_py_name_extracted(self, tmp_path):
        _write(tmp_path / "pkg" / "setup.py",
               "from setuptools import setup\nsetup(name='extracted-name', version='1.0')")
        info = _make_package(tmp_path / "pkg")
        assert info.name == "extracted-name"


# ──────────────────────────────────────────────────────────────────────────────
# MonorepoLayout.summary()
# ──────────────────────────────────────────────────────────────────────────────

class TestMonorepoLayout:
    def test_summary_contains_tool_and_count(self, tmp_path):
        layout = MonorepoLayout(
            root=tmp_path,
            tool="pnpm",
            packages=[
                PackageInfo(name="a", root=tmp_path / "a", language="javascript"),
                PackageInfo(name="b", root=tmp_path / "b", language="javascript"),
            ],
        )
        summary = layout.summary()
        assert "pnpm" in summary
        assert "2" in summary

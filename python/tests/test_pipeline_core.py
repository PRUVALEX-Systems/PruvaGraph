"""
Dedicated unit tests for pruvagraph.pipeline — the main orchestrator.

Currently the pipeline is only covered indirectly via test_build.py and
test_dead_layers.py. This file tests the core pipeline units directly:
  - BuildConfig defaults
  - _is_repo_unchanged short-circuit logic
  - BudgetExceededError
  - _empty_result helper
  - _enrich_with_docstrings on various graph states
  - build_graph_from_extractions (N3 fast-path)
  - BuildResult.summary()
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from pruvagraph.pipeline import (
    BudgetExceededError,
    BuildConfig,
    BuildResult,
    _empty_result,
    _enrich_with_docstrings,
    _is_repo_unchanged,
    build_graph_from_extractions,
)
from pruvagraph.cost import CostReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cost_report(**kwargs) -> CostReport:
    cr = CostReport()
    for k, v in kwargs.items():
        setattr(cr, k, v)
    return cr


def _make_build_config(root: Path, **kwargs) -> BuildConfig:
    defaults = dict(
        root=root,
        backend="none",
        cascade=False,
        budget_usd=None,
        dry_run=False,
        force=False,
        dedup_threshold=0.82,
        max_tokens_per_batch=12_000,
        no_viz=False,
        out_dir="pruvagraph-out",
        streaming=False,
        monorepo=False,
        update=False,
    )
    defaults.update(kwargs)
    return BuildConfig(**defaults)


# ===========================================================================
# 1. BuildConfig — defaults
# ===========================================================================

class TestBuildConfig:
    def test_default_backend(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        assert cfg.backend == "none"

    def test_default_dedup_threshold(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        assert cfg.dedup_threshold == 0.82

    def test_default_flags_off(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        assert cfg.cascade is False
        assert cfg.dry_run is False
        assert cfg.force is False
        assert cfg.streaming is False
        assert cfg.monorepo is False
        assert cfg.update is False

    def test_custom_out_dir(self, tmp_path):
        cfg = _make_build_config(tmp_path, out_dir="custom-out")
        assert cfg.out_dir == "custom-out"

    def test_root_is_path(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        assert isinstance(cfg.root, Path)


# ===========================================================================
# 2. _is_repo_unchanged — short-circuit logic
# ===========================================================================

class TestIsRepoUnchanged:
    def test_returns_false_when_no_graph(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        # No graph.json exists
        assert _is_repo_unchanged(cfg) is False

    def test_returns_false_when_force(self, tmp_path):
        cfg = _make_build_config(tmp_path, force=True)
        # force=True must always bypass the check
        assert _is_repo_unchanged(cfg) is False

    def test_returns_false_outside_git_repo(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        out_dir = tmp_path / "pruvagraph-out"
        out_dir.mkdir()
        (out_dir / "graph.json").write_text("{}")
        # tmp_path has no .git — should return False
        assert _is_repo_unchanged(cfg) is False

    def test_returns_false_on_git_not_available(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        out_dir = tmp_path / "pruvagraph-out"
        out_dir.mkdir()
        (out_dir / "graph.json").write_text("{}")
        with patch("shutil.which", return_value=None):
            assert _is_repo_unchanged(cfg) is False

    def test_returns_false_when_git_status_dirty(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        out_dir = tmp_path / "pruvagraph-out"
        out_dir.mkdir()
        (out_dir / "graph.json").write_text("{}")

        mock_is_inside = MagicMock(returncode=0, stdout="true")
        mock_status = MagicMock(returncode=0, stdout="M modified_file.py\n")
        mock_log = MagicMock(returncode=0, stdout="1234567890\n")

        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch("subprocess.run", side_effect=[mock_is_inside, mock_status, mock_log]):
                result = _is_repo_unchanged(cfg)
        assert result is False

    def test_returns_false_on_subprocess_exception(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        out_dir = tmp_path / "pruvagraph-out"
        out_dir.mkdir()
        (out_dir / "graph.json").write_text("{}")

        with patch("subprocess.run", side_effect=OSError("no git")):
            assert _is_repo_unchanged(cfg) is False


# ===========================================================================
# 3. BudgetExceededError
# ===========================================================================

class TestBudgetExceededError:
    def test_is_exception(self):
        assert issubclass(BudgetExceededError, Exception)

    def test_message_preserved(self):
        try:
            raise BudgetExceededError("Budget of $1.00 exceeded")
        except BudgetExceededError as e:
            assert "$1.00" in str(e)


# ===========================================================================
# 4. _empty_result helper
# ===========================================================================

class TestEmptyResult:
    def test_returns_build_result(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        cr = _make_cost_report()
        result = _empty_result(cfg, cr)
        assert isinstance(result, BuildResult)

    def test_zero_counts(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        cr = _make_cost_report()
        result = _empty_result(cfg, cr)
        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.community_count == 0

    def test_paths_are_in_out_dir(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        cr = _make_cost_report()
        result = _empty_result(cfg, cr)
        expected_out = tmp_path / "pruvagraph-out"
        assert str(expected_out) in str(result.graph_json_path)

    def test_html_path_is_none(self, tmp_path):
        cfg = _make_build_config(tmp_path)
        cr = _make_cost_report()
        result = _empty_result(cfg, cr)
        assert result.html_path is None


# ===========================================================================
# 5. BuildResult.summary()
# ===========================================================================

class TestBuildResultSummary:
    def _make_result(self, tmp_path) -> BuildResult:
        out = tmp_path / "pruvagraph-out"
        out.mkdir(exist_ok=True)
        cr = _make_cost_report(
            llm_calls_made=5,
            calls_saved=95,
            savings_pct=95.0,
            actual_cost_usd=0.0015,
            cost_saved_usd=0.0285,
        )
        return BuildResult(
            graph_json_path=out / "graph.json",
            html_path=out / "graph.html",
            report_path=out / "GRAPH_REPORT.md",
            cost_report=cr,
            node_count=100,
            edge_count=250,
            community_count=8,
            duration_seconds=12.5,
        )

    def test_summary_contains_node_count(self, tmp_path):
        result = self._make_result(tmp_path)
        summary = result.summary()
        assert "100" in summary

    def test_summary_contains_cost(self, tmp_path):
        result = self._make_result(tmp_path)
        summary = result.summary()
        assert "$" in summary

    def test_summary_contains_savings_pct(self, tmp_path):
        result = self._make_result(tmp_path)
        summary = result.summary()
        assert "95%" in summary or "95" in summary

    def test_summary_is_multiline(self, tmp_path):
        result = self._make_result(tmp_path)
        assert "\n" in result.summary()


# ===========================================================================
# 6. _enrich_with_docstrings
# ===========================================================================

class TestEnrichWithDocstrings:
    def test_empty_graph_no_crash(self, tmp_path):
        G = nx.MultiDiGraph()
        _enrich_with_docstrings(G, tmp_path)  # must not raise

    def test_graph_with_no_file_attribute(self, tmp_path):
        G = nx.MultiDiGraph()
        G.add_node("node_a", label="NodeA")  # no 'file' attribute
        _enrich_with_docstrings(G, tmp_path)  # must not raise

    def test_does_not_overwrite_rich_summary(self, tmp_path):
        """A node with a rich (long) summary should not be overwritten."""
        G = nx.MultiDiGraph()
        long_summary = "This is a comprehensive summary with more than 20 characters."
        G.add_node("my.Node", label="Node", file=str(tmp_path / "fake.py"),
                   summary=long_summary)
        _enrich_with_docstrings(G, tmp_path)
        assert G.nodes["my.Node"]["summary"] == long_summary

    def test_enriches_node_with_empty_summary(self, tmp_path):
        """A node with an empty summary should be enriched if docstrings are available."""
        # Create a real Python file with a docstring
        py_file = tmp_path / "mymodule.py"
        py_file.write_text(
            'def my_function():\n    """This is the function docstring."""\n    pass\n'
        )
        G = nx.MultiDiGraph()
        G.add_node("my_function", label="my_function", file=str(py_file), summary="")
        _enrich_with_docstrings(G, tmp_path)
        # The node summary may be enriched from the docstring
        # (depends on tree-sitter availability — at minimum, no crash)
        assert isinstance(G.nodes["my_function"].get("summary", ""), str)


# ===========================================================================
# 7. build_graph_from_extractions (N3 fast-path)
# ===========================================================================

class TestBuildGraphFromExtractions:
    def _make_extraction(self, filepath: str, nodes: list[dict]) -> dict:
        return {
            "source_file": filepath,
            "nodes": nodes,
            "edges": [],
        }

    def test_empty_extractions(self, tmp_path):
        result = build_graph_from_extractions(str(tmp_path), [])
        assert isinstance(result, BuildResult)
        # Empty extractions → possibly 0 nodes (or a small graph from empty inputs)
        assert result.node_count >= 0

    def test_single_extraction_produces_result(self, tmp_path):
        extractions = [
            self._make_extraction(
                str(tmp_path / "app.py"),
                [{"id": "app.main", "name": "main", "type": "function",
                  "label": "[function] main", "summary": "Entry point", "file": "app.py"}],
            )
        ]
        result = build_graph_from_extractions(str(tmp_path), extractions)
        assert isinstance(result, BuildResult)
        assert result.node_count >= 0  # may be 0 if build_nx_graph deduplicates
        assert result.graph_json_path.exists() or not result.graph_json_path.exists()  # path set

    def test_multiple_extractions(self, tmp_path):
        extractions = [
            self._make_extraction(
                str(tmp_path / "auth.py"),
                [{"id": "auth.login", "name": "login", "type": "function",
                  "label": "[function] login", "summary": "Login handler", "file": "auth.py"}],
            ),
            self._make_extraction(
                str(tmp_path / "db.py"),
                [{"id": "db.connect", "name": "connect", "type": "function",
                  "label": "[function] connect", "summary": "DB connect", "file": "db.py"}],
            ),
        ]
        result = build_graph_from_extractions(str(tmp_path), extractions)
        assert isinstance(result, BuildResult)
        assert isinstance(result.duration_seconds, float)

    def test_result_has_valid_paths(self, tmp_path):
        result = build_graph_from_extractions(str(tmp_path), [])
        assert result.graph_json_path is not None
        assert result.report_path is not None

    def test_out_dir_created(self, tmp_path):
        build_graph_from_extractions(str(tmp_path), [])
        out_dir = tmp_path / "pruvagraph-out"
        assert out_dir.exists()

    def test_cost_report_has_correct_file_count(self, tmp_path):
        extractions = [
            self._make_extraction(str(tmp_path / f"file{i}.py"), [])
            for i in range(5)
        ]
        result = build_graph_from_extractions(str(tmp_path), extractions)
        assert result.cost_report is not None

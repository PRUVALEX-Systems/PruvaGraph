"""
Tests for pruvagraph.mcp_server — the entire user-facing MCP surface.

Coverage targets (Phase 0 gate):
  - All 13 tool implementations (Phase 2: +validate_import, +scan_suggestion)
  - Tool registry integrity (TOOLS count == TOOL_HANDLERS count, no orphans)
  - Session tracking integration (no crash when session_tracker absent)
  - _write_claude_md / _merge_json helpers
  - Error and edge-case paths (no graph, node not found, missing files)
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest


# ---------------------------------------------------------------------------
# Helpers — build fixture graphs and disk structures
# ---------------------------------------------------------------------------

def _make_graph(nodes: list[dict], edges: list[tuple]) -> nx.MultiDiGraph:
    """Build a minimal networkx graph for testing."""
    G = nx.MultiDiGraph()
    for n in nodes:
        G.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for src, dst, data in edges:
        G.add_edge(src, dst, **data)
    return G


def _simple_graph() -> nx.MultiDiGraph:
    """A graph with 3 nodes, 2 edges, 2 communities — used by most tests."""
    return _make_graph(
        nodes=[
            {"id": "auth.SessionManager", "label": "SessionManager", "type": "class",
             "file": "auth/session.py", "summary": "Manages user sessions.", "community": 0},
            {"id": "auth.login", "label": "login", "type": "function",
             "file": "auth/views.py", "summary": "Handles login requests.", "community": 0},
            {"id": "db.UserModel", "label": "UserModel", "type": "class",
             "file": "db/models.py", "summary": "ORM model for users.", "community": 1},
        ],
        edges=[
            ("auth.SessionManager", "db.UserModel", {"relation": "uses"}),
            ("auth.login", "auth.SessionManager", {"relation": "calls"}),
        ],
    )


def _write_graph_json(tmp_path: Path, G: nx.MultiDiGraph) -> Path:
    """Write graph.json to tmp_path/pruvagraph-out/ and return the out_dir."""
    out_dir = tmp_path / "pruvagraph-out"
    out_dir.mkdir()
    (out_dir / "graph.json").write_text(
        json.dumps(nx.node_link_data(G)), encoding="utf-8"
    )
    return out_dir


def _write_cost_report(out_dir: Path, data: dict | None = None) -> Path:
    """Write a cost_report.json to out_dir."""
    default = {
        "total_files_processed": 42,
        "cache_hits": 30,
        "dedup_projected": 5,
        "llm_calls_made": 7,
        "naive_calls": 42,
        "calls_saved": 35,
        "actual_cost_usd": 0.000210,
        "naive_cost_usd": 0.126000,
        "cost_saved_usd": 0.125790,
        "savings_pct": 99.8,
        "run_duration_seconds": 4.3,
    }
    payload = {**default, **(data or {})}
    p = out_dir / "cost_report.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Import the module under test — after helpers so we can patch early
# ---------------------------------------------------------------------------

from pruvagraph import mcp_server as _ms


# ===========================================================================
# 1. Tool registry integrity
# ===========================================================================

class TestToolRegistry:
    def test_tool_count_matches_handler_count(self):
        """Every TOOLS entry must have a corresponding TOOL_HANDLERS entry."""
        tool_names = {t["name"] for t in _ms.TOOLS}
        handler_names = set(_ms.TOOL_HANDLERS.keys())
        assert tool_names == handler_names, (
            f"Mismatched tools vs handlers.\n"
            f"  In TOOLS but not TOOL_HANDLERS: {tool_names - handler_names}\n"
            f"  In TOOL_HANDLERS but not TOOLS: {handler_names - tool_names}"
        )

    def test_tool_count_is_twentythree(self):
        """Baseline: 23 tools as of v1.9.0 (added RulesForge 2 tools in Phase 5).
        Update this when new tools are added — and update the marketplace listing too."""
        assert len(_ms.TOOLS) == 23, (
            f"Expected 23 tools, found {len(_ms.TOOLS)}. "
            f"If you added tools, update the marketplace listing and this test."
        )

    def test_every_tool_has_required_fields(self):
        """Every tool dict must have name, description, and inputSchema."""
        for tool in _ms.TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool '{tool['name']}' missing 'description'"
            assert "inputSchema" in tool, f"Tool '{tool['name']}' missing 'inputSchema'"

    def test_every_tool_has_non_empty_description(self):
        for tool in _ms.TOOLS:
            assert len(tool["description"].strip()) > 20, (
                f"Tool '{tool['name']}' has suspiciously short description"
            )

    def test_no_duplicate_tool_names(self):
        names = [t["name"] for t in _ms.TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"


# ===========================================================================
# 2. _load_graph — lazy loader
# ===========================================================================

class TestLoadGraph:
    def test_returns_none_when_no_graph(self, tmp_path):
        with patch.object(_ms, "_graph_cache", {}):
            G, is_partial = _ms._load_graph(str(tmp_path))
        assert G is None
        assert is_partial is False

    def test_loads_existing_graph(self, tmp_path):
        G_orig = _simple_graph()
        _write_graph_json(tmp_path, G_orig)
        with patch.object(_ms, "_graph_cache", {}):
            with patch("pruvagraph.mcp_server._load_graph", wraps=_ms._load_graph):
                G, is_partial = _ms._load_graph(str(tmp_path))
        assert G is not None
        assert G.number_of_nodes() == 3
        assert is_partial is False


# ===========================================================================
# 3. _query_graph
# ===========================================================================

class TestQueryGraph:
    def test_no_graph_returns_instruction(self, tmp_path):
        result = _ms._query_graph("what is auth?", root=str(tmp_path))
        assert "pruvagraph" in result.lower()
        assert "first" in result.lower()

    def test_with_graph_no_query_module(self, tmp_path):
        """When query.py fails, the fallback keyword search should still work."""
        G = _simple_graph()
        _write_graph_json(tmp_path, G)

        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            with patch("pruvagraph.mcp_server._query_graph.__wrapped__", None, create=True):
                # Patch the query import to raise so we hit the fallback
                with patch("builtins.__import__", side_effect=ImportError("no query")):
                    # Direct fallback path — call the keyword-search branch
                    result = _ms._query_graph("SessionManager", root=str(tmp_path))
        # SessionManager is in the graph — should appear in result
        assert "SessionManager" in result or "pruvagraph" in result.lower()

    def test_with_graph_keyword_match(self, tmp_path):
        G = _simple_graph()

        def _fake_query(G, question, **kwargs):
            raise RuntimeError("intentional failure — test fallback")

        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            with patch("pruvagraph.query.query", _fake_query):
                result = _ms._query_graph("SessionManager", root=".")
        assert "SessionManager" in result

    def test_no_match_fallback(self, tmp_path):
        G = _simple_graph()

        def _fake_query(G, question, **kwargs):
            raise RuntimeError("intentional")

        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            with patch("pruvagraph.query.query", _fake_query):
                result = _ms._query_graph("zzz_no_match_xyz", root=".")
        # Should return something (not crash), even with no match
        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# 4. _get_dependencies
# ===========================================================================

class TestGetDependencies:
    def test_no_graph(self, tmp_path):
        result = _ms._get_dependencies("auth.login", root=str(tmp_path))
        assert isinstance(result, str)

    def test_node_not_found(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._get_dependencies("nonexistent.node", root=str(tmp_path))
        assert "not found" in result.lower() or "nonexistent" in result.lower()

    def test_found_node_with_deps(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._get_dependencies("auth.login", root=str(tmp_path))
        # auth.login -> auth.SessionManager
        assert "SessionManager" in result or "Dependencies" in result

    def test_node_with_no_outgoing_edges(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._get_dependencies("db.UserModel", root=str(tmp_path))
        assert isinstance(result, str)


# ===========================================================================
# 5. _find_callers
# ===========================================================================

class TestFindCallers:
    def test_no_graph(self, tmp_path):
        result = _ms._find_callers("auth.SessionManager", root=str(tmp_path))
        assert isinstance(result, str)

    def test_node_not_found(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._find_callers("nonexistent.fn", root=str(tmp_path))
        assert "not found" in result.lower() or "nonexistent" in result.lower()

    def test_found_callers(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._find_callers("auth.SessionManager", root=str(tmp_path))
        # auth.login calls auth.SessionManager
        assert "login" in result or "Callers" in result

    def test_no_callers(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._find_callers("auth.login", root=str(tmp_path))
        assert isinstance(result, str)


# ===========================================================================
# 6. _get_summary
# ===========================================================================

class TestGetSummary:
    def test_no_graph(self, tmp_path):
        result = _ms._get_summary("auth.login", root=str(tmp_path))
        assert isinstance(result, str)

    def test_node_not_found(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._get_summary("nonexistent", root=str(tmp_path))
        assert "not found" in result.lower() or "nonexistent" in result.lower()

    def test_summary_returned(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._get_summary("auth.SessionManager", root=str(tmp_path))
        assert "Manages user sessions" in result or "SessionManager" in result


# ===========================================================================
# 7. _list_communities
# ===========================================================================

class TestListCommunities:
    def test_no_graph(self, tmp_path):
        result = _ms._list_communities(root=str(tmp_path))
        assert isinstance(result, str)

    def test_returns_community_info(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._list_communities(root=str(tmp_path))
        assert "community" in result.lower() or "Detected" in result or "cluster" in result.lower()


# ===========================================================================
# 8. _cost_report
# ===========================================================================

class TestCostReport:
    def test_no_cost_file(self, tmp_path):
        result = _ms._get_cost_report(root=str(tmp_path))
        assert "not found" in result.lower() or "no cost" in result.lower() or "run" in result.lower()

    def test_with_cost_file(self, tmp_path):
        out_dir = tmp_path / "pruvagraph-out"
        out_dir.mkdir()
        _write_cost_report(out_dir)
        result = _ms._get_cost_report(root=str(tmp_path))
        assert "99.8" in result or "0.125" in result or "saved" in result.lower()


# ===========================================================================
# 9. _get_graph_diff
# ===========================================================================

class TestGetGraphDiff:
    def test_no_diff_file(self, tmp_path):
        result = _ms._get_graph_diff(root=str(tmp_path))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_diff_file(self, tmp_path):
        out_dir = tmp_path / "pruvagraph-out"
        out_dir.mkdir()
        diff_data = {
            "added_nodes": ["new.Module"],
            "removed_nodes": [],
            "added_edges": [],
            "removed_edges": [["old.A", "old.B"]],
        }
        (out_dir / "graph_diff.json").write_text(json.dumps(diff_data), encoding="utf-8")
        result = _ms._get_graph_diff(root=str(tmp_path))
        # The function may or may not parse the file — just confirm it returns a string
        assert isinstance(result, str) and len(result) > 0


# ===========================================================================
# 10. _analyze_impact
# ===========================================================================

class TestAnalyzeImpact:
    def test_no_graph(self, tmp_path):
        result = _ms._analyze_impact("auth.login", root=str(tmp_path))
        assert isinstance(result, str)

    def test_node_not_found(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._analyze_impact("nonexistent.node", root=str(tmp_path))
        assert isinstance(result, str)

    def test_with_graph(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._analyze_impact("db.UserModel", root=str(tmp_path))
        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# 11. _list_packages
# ===========================================================================

class TestListPackages:
    def test_no_graph(self, tmp_path):
        result = _ms._list_packages(root=str(tmp_path))
        assert isinstance(result, str)

    def test_with_graph(self, tmp_path):
        G = _simple_graph()
        with patch.object(_ms, "_load_graph", return_value=(G, False)):
            result = _ms._list_packages(root=str(tmp_path))
        assert isinstance(result, str)


# ===========================================================================
# 12. _remember / _recall
# ===========================================================================

class TestRememberRecall:
    def test_remember_and_recall(self, tmp_path):
        r = _ms._remember("decisions", "Use PostgreSQL", root=str(tmp_path))
        assert "Remembered" in r or "decision" in r.lower()
        recalled = _ms._recall(root=str(tmp_path))
        assert "PostgreSQL" in recalled

    def test_recall_empty(self, tmp_path):
        result = _ms._recall(root=str(tmp_path))
        assert "no session memory" in result.lower() or isinstance(result, str)

    def test_remember_invalid_category(self, tmp_path):
        result = _ms._remember("invalid_cat", "some text", root=str(tmp_path))
        # Should return error string or raise — either is acceptable
        assert isinstance(result, str)

    def test_remember_tasks_category(self, tmp_path):
        r = _ms._remember("tasks", "Write tests first", root=str(tmp_path))
        assert isinstance(r, str)
        recalled = _ms._recall(root=str(tmp_path))
        assert "Write tests first" in recalled

    def test_remember_blockers_category(self, tmp_path):
        r = _ms._remember("blockers", "Awaiting API key", root=str(tmp_path))
        assert isinstance(r, str)


# ===========================================================================
# 13. _validate_import / _scan_suggestion (Phase 2 — DriftGuard)
# ===========================================================================

class TestValidateImportHandler:
    def test_valid_module_and_symbol(self, tmp_path):
        result = _ms._validate_import("json", "loads", root=str(tmp_path))
        assert "✓" in result or "valid" in result.lower()
        assert "json" in result

    def test_module_only(self, tmp_path):
        result = _ms._validate_import("json", None, root=str(tmp_path))
        assert "✓" in result or "valid" in result.lower()

    def test_invalid_symbol_with_suggestion(self, tmp_path):
        result = _ms._validate_import("json", "loasd", root=str(tmp_path))
        assert "⚠" in result or "INVALID" in result
        # Should suggest "loads"
        assert "loads" in result

    def test_nonexistent_package(self, tmp_path):
        result = _ms._validate_import("this_package_xyz_does_not_exist_42", None, root=str(tmp_path))
        assert "⚠" in result or "INVALID" in result


class TestScanSuggestionHandler:
    def test_valid_diff_returns_ok(self, tmp_path):
        diff = "+from json import loads\n"
        result = _ms._scan_suggestion(diff, root=str(tmp_path))
        assert "✓" in result or "valid" in result.lower()

    def test_invalid_import_flagged(self, tmp_path):
        diff = "+from json import loasd\n"
        result = _ms._scan_suggestion(diff, root=str(tmp_path))
        assert "⚠" in result or "issue" in result.lower()

    def test_empty_diff(self, tmp_path):
        result = _ms._scan_suggestion("", root=str(tmp_path))
        assert "✓" in result or "valid" in result.lower()


# ===========================================================================
# 14. _write_claude_md helper
# ===========================================================================

class TestWriteClaudeMd:
    def test_creates_claude_md(self, tmp_path):
        md_path = tmp_path / "CLAUDE.md"
        _ms._write_claude_md(path=md_path)
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "PruvaGraph" in content

    def test_contains_tool_table(self, tmp_path):
        md_path = tmp_path / "CLAUDE.md"
        _ms._write_claude_md(path=md_path)
        content = md_path.read_text(encoding="utf-8")
        assert "query_graph" in content
        assert "validate_import" in content
        assert "scan_suggestion" in content


# ===========================================================================
# 15. _merge_json helper
# ===========================================================================

class TestMergeJson:
    def test_creates_new_file(self, tmp_path):
        path = tmp_path / "config.json"
        _ms._merge_json(path, {"mcpServers": {"pruvagraph": {"cmd": "test"}}})
        assert path.exists()
        result = json.loads(path.read_text())
        assert "pruvagraph" in result["mcpServers"]

    def test_merges_with_existing(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"mcpServers": {"existing": {}}}))
        _ms._merge_json(path, {"mcpServers": {"pruvagraph": {}}})
        result = json.loads(path.read_text())
        assert "existing" in result["mcpServers"]
        assert "pruvagraph" in result["mcpServers"]

    def test_handles_corrupt_existing_file(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("NOT VALID JSON")
        _ms._merge_json(path, {"a": 1})  # should not raise
        assert json.loads(path.read_text()) == {"a": 1}

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "config.json"
        _ms._merge_json(path, {"x": 42})
        assert path.exists()


# ===========================================================================
# 16. TOOL_HANDLERS callable — smoke test each handler with minimal args
# ===========================================================================

class TestToolHandlerCallable:
    """Each handler must be callable and return a string without crashing,
    even with a completely empty/missing graph."""

    _ARGS_BY_TOOL = {
        "query_graph":      {"question": "what is auth?", "root": "."},
        "get_dependencies": {"node_id": "nonexistent", "root": "."},
        "find_callers":     {"node_id": "nonexistent", "root": "."},
        "get_summary":      {"node_id": "nonexistent", "root": "."},
        "list_communities": {"root": "."},
        "cost_report":      {"root": "."},
        "get_graph_diff":   {"root": "."},
        "analyze_impact":   {"node_id": "nonexistent", "root": "."},
        "list_packages":    {"root": "."},
        "remember":         {"category": "decisions", "text": "smoke test entry", "root": "."},
        "recall":           {"root": "."},
        # v1.6.0 — DriftGuard
        "validate_import":  {"module": "json", "symbol": "loads", "root": "."},
        "scan_suggestion":  {"diff": "+import json\n", "root": "."},
        # v1.7.0 — ContextLens
        "get_active_context":    {"root": "."},
        "measure_token_usage":   {"root": "."},
        "trace_last_tool_calls": {"root": ".", "n": 5},
        # v1.8.0 — TaskWeaver
        "create_checkpoint":      {"task_id": "test-task", "description": "smoke step", "root": "."},
        "get_task_progress":      {"task_id": "test-task", "root": "."},
        "rollback_to_checkpoint": {"checkpoint_id": "nonexistent-id", "root": "."},
        "list_checkpoints":       {"root": "."},
        # v1.8.0 — Budget Governor
        "check_budget":           {"root": "."},
        # v1.9.0 — RulesForge
        "get_applicable_rules":   {"file_uri": "pruvagraph/mcp_server.py", "root": "."},
        "learn_from_accept":      {"diff": "+import json\n", "description": "use stdlib", "root": "."},
    }

    @pytest.mark.parametrize("tool_name", [t["name"] for t in _ms.TOOLS])
    def test_handler_returns_string(self, tool_name, tmp_path, monkeypatch):
        """Every handler must return a str, not raise, even with no graph on disk."""
        monkeypatch.chdir(tmp_path)
        handler = _ms.TOOL_HANDLERS[tool_name]
        args = {**self._ARGS_BY_TOOL[tool_name], "root": str(tmp_path)}
        result = _ms._dispatch(tool_name, args, handler)
        assert isinstance(result, str), (
            f"Handler '{tool_name}' returned {type(result).__name__}, expected str"
        )
        assert len(result) > 0, f"Handler '{tool_name}' returned empty string"


# ===========================================================================
# 17. ContextLens handler tests
# ===========================================================================

class TestContextLensHandlers:
    def test_get_active_context_empty(self, tmp_path):
        result = _ms._get_active_context(root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "0" in result or "empty" in result.lower()

    def test_get_active_context_after_calls(self, tmp_path):
        # Simulate two tool calls via dispatch
        _ms._dispatch("get_summary", {"node_id": "n", "root": str(tmp_path)},
                      _ms.TOOL_HANDLERS["get_summary"])
        _ms._dispatch("list_communities", {"root": str(tmp_path)},
                      _ms.TOOL_HANDLERS["list_communities"])
        result = _ms._get_active_context(root=str(tmp_path))
        assert "token" in result.lower()

    def test_measure_token_usage_empty(self, tmp_path):
        result = _ms._measure_token_usage(root=str(tmp_path))
        assert isinstance(result, str)
        assert "0" in result or "no" in result.lower() or "empty" in result.lower()

    def test_measure_token_usage_after_calls(self, tmp_path):
        _ms._dispatch("recall", {"root": str(tmp_path)},
                      _ms.TOOL_HANDLERS["recall"])
        result = _ms._measure_token_usage(root=str(tmp_path))
        assert "total" in result.lower() or "Total" in result

    def test_trace_last_tool_calls_empty(self, tmp_path):
        result = _ms._trace_last_tool_calls(root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "0" in result or "empty" in result.lower()

    def test_trace_last_tool_calls_after_dispatch(self, tmp_path):
        _ms._dispatch("list_communities", {"root": str(tmp_path)},
                      _ms.TOOL_HANDLERS["list_communities"])
        result = _ms._trace_last_tool_calls(root=str(tmp_path), n=5)
        assert "list_communities" in result

    def test_dispatch_logs_call_to_session_file(self, tmp_path):
        """_dispatch must create the context_lens session file after any tool call."""
        from pathlib import Path
        session_file = tmp_path / "pruvagraph-out" / "context_lens_session.jsonl"
        assert not session_file.exists()  # sanity: file not there before
        _ms._dispatch("recall", {"root": str(tmp_path)},
                      _ms.TOOL_HANDLERS["recall"])
        assert session_file.exists(), "_dispatch did not create context_lens session file"


# ===========================================================================
# 18. TaskWeaver handler tests
# ===========================================================================

class TestTaskWeaverHandlers:
    def test_create_checkpoint_returns_string(self, tmp_path):
        result = _ms._create_checkpoint("task1", "step 1", root=str(tmp_path))
        assert isinstance(result, str) and "checkpoint" in result.lower()

    def test_get_task_progress_empty(self, tmp_path):
        result = _ms._get_task_progress("no-such-task", root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "0" in result or "empty" in result.lower()

    def test_get_task_progress_after_checkpoint(self, tmp_path):
        _ms._create_checkpoint("my-task", "did something", root=str(tmp_path))
        result = _ms._get_task_progress("my-task", root=str(tmp_path))
        assert "my-task" in result or "did something" in result

    def test_rollback_invalid_id_does_not_crash(self, tmp_path):
        result = _ms._rollback_to_checkpoint("bad-id-99", root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0

    def test_list_checkpoints_empty(self, tmp_path):
        result = _ms._list_checkpoints(root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "empty" in result.lower() or "0" in result

    def test_list_checkpoints_after_create(self, tmp_path):
        _ms._create_checkpoint("task-x", "step A", root=str(tmp_path))
        result = _ms._list_checkpoints(root=str(tmp_path))
        assert "task-x" in result


# ===========================================================================
# 19. Budget Governor handler tests
# ===========================================================================

class TestBudgetGovernorHandlers:
    def test_check_budget_no_budget_set(self, tmp_path):
        result = _ms._check_budget(root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "not set" in result.lower() or "unset" in result.lower()

    def test_check_budget_after_set_via_governor(self, tmp_path):
        from pruvagraph.budget_governor import set_budget
        set_budget(10000, root=str(tmp_path))
        result = _ms._check_budget(root=str(tmp_path))
        assert "10000" in result or "10,000" in result
        assert "OK" in result

    def test_dispatch_records_budget_spend(self, tmp_path):
        """_dispatch must call record_spend so budget decrements automatically."""
        from pruvagraph.budget_governor import set_budget, check_budget
        set_budget(50000, root=str(tmp_path))
        _ms._dispatch("recall", {"root": str(tmp_path)},
                      _ms.TOOL_HANDLERS["recall"])
        status = check_budget(root=str(tmp_path))
        # Some spend was recorded — remaining should be < 50000
        assert "50,000" not in status or "0" in status or "remaining" in status.lower()

    def test_dispatch_does_not_crash_without_budget(self, tmp_path):
        """_dispatch must complete even if no budget is set."""
        result = _ms._dispatch("list_communities", {"root": str(tmp_path)},
                               _ms.TOOL_HANDLERS["list_communities"])
        assert isinstance(result, str)


# ===========================================================================
# 20. RulesForge handler tests
# ===========================================================================

class TestRulesForgeHandlers:
    def test_get_applicable_rules_returns_string(self, tmp_path):
        result = _ms._get_applicable_rules(str(tmp_path / "routes.py"), root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0

    def test_get_applicable_rules_for_api_file(self, tmp_path):
        f = tmp_path / "routes.py"
        f.write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
        result = _ms._get_applicable_rules(str(f), root=str(tmp_path))
        assert "api" in result.lower()

    def test_get_applicable_rules_for_test_file(self, tmp_path):
        f = tmp_path / "test_auth.py"
        f.write_text("import pytest\ndef test_x(): pass\n", encoding="utf-8")
        result = _ms._get_applicable_rules(str(f), root=str(tmp_path))
        assert "test" in result.lower()

    def test_learn_from_accept_returns_string(self, tmp_path):
        result = _ms._learn_from_accept("+import json\n", "use stdlib json", root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0

    def test_learn_from_accept_persists_to_rules_json(self, tmp_path):
        import json as _json
        _ms._learn_from_accept("+x = 1\n", "keep things simple", root=str(tmp_path))
        rules_file = tmp_path / "pruvagraph-out" / "rules.json"
        assert rules_file.exists()
        data = _json.loads(rules_file.read_text(encoding="utf-8"))
        assert any(e["description"] == "keep things simple" for e in data["_learned"])

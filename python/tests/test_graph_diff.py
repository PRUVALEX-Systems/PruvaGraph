"""
Tests for D1 — Graph Diff Engine (graph_diff.py).

Covers:
  - First build (G_old = None) → all nodes as added
  - Clean diff (identical graphs) → is_empty() == True
  - Added nodes / removed nodes / changed nodes
  - Edge delta detection
  - save_diff / load_diff round-trip
  - Storage: delta-only (no full graph snapshot)
  - format() output for empty and non-empty diffs
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import networkx as nx
import pytest

from pruvagraph.graph_diff import (
    GraphDiff,
    compute_diff,
    load_diff,
    load_previous_graph,
    save_diff,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _make_graph(nodes: dict, edges: list[tuple]) -> nx.MultiDiGraph:
    """
    Build a minimal MultiDiGraph.
    nodes: {node_id: {"label": ..., "type": ..., "summary": ...}}
    edges: [(src, tgt, {"relation": ...})]
    """
    G = nx.MultiDiGraph()
    for nid, attrs in nodes.items():
        G.add_node(nid, **attrs)
    for src, tgt, attrs in edges:
        G.add_edge(src, tgt, **attrs)
    return G


@pytest.fixture()
def base_graph():
    return _make_graph(
        {
            "auth":    {"label": "AuthService", "type": "class",    "summary": "Handles auth"},
            "session": {"label": "SessionMgr",  "type": "class",    "summary": "Session mgmt"},
            "db":      {"label": "DBClient",    "type": "class",    "summary": "DB access"},
        },
        [
            ("auth",    "session", {"relation": "uses"}),
            ("session", "db",      {"relation": "calls"}),
        ],
    )


# ──────────────────────────────────────────────────────────────────────────────
# compute_diff — first build
# ──────────────────────────────────────────────────────────────────────────────

class TestFirstBuild:
    def test_none_old_returns_all_nodes_as_added(self, base_graph):
        diff = compute_diff(G_old=None, G_new=base_graph)
        assert sorted(diff.added_nodes) == ["auth", "db", "session"]
        assert diff.removed_nodes == []
        assert diff.changed_nodes == []

    def test_none_old_summary_mentions_first_build(self, base_graph):
        diff = compute_diff(G_old=None, G_new=base_graph)
        assert "first build" in diff.diff_summary

    def test_none_old_is_not_empty(self, base_graph):
        diff = compute_diff(G_old=None, G_new=base_graph)
        assert not diff.is_empty()


# ──────────────────────────────────────────────────────────────────────────────
# compute_diff — clean (no change)
# ──────────────────────────────────────────────────────────────────────────────

class TestCleanDiff:
    def test_identical_graphs_produces_empty_diff(self, base_graph):
        # Duplicate the graph to simulate "no change since last build"
        diff = compute_diff(G_old=base_graph, G_new=base_graph)
        assert diff.is_empty()

    def test_empty_diff_summary_says_no_changes(self, base_graph):
        diff = compute_diff(G_old=base_graph, G_new=base_graph)
        assert "no changes" in diff.diff_summary


# ──────────────────────────────────────────────────────────────────────────────
# compute_diff — node changes
# ──────────────────────────────────────────────────────────────────────────────

class TestNodeChanges:
    def test_added_node_detected(self, base_graph):
        G_new = base_graph.copy()
        G_new.add_node("cache", label="CacheLayer", type="class", summary="Caching")
        diff = compute_diff(base_graph, G_new)
        assert "cache" in diff.added_nodes
        assert diff.removed_nodes == []

    def test_removed_node_detected(self, base_graph):
        G_new = base_graph.copy()
        G_new.remove_node("db")
        diff = compute_diff(base_graph, G_new)
        assert "db" in diff.removed_nodes
        assert diff.added_nodes == []

    def test_changed_summary_detected(self, base_graph):
        G_new = base_graph.copy()
        G_new.nodes["auth"]["summary"] = "CHANGED summary"
        diff = compute_diff(base_graph, G_new)
        assert "auth" in diff.changed_nodes

    def test_changed_type_detected(self, base_graph):
        G_new = base_graph.copy()
        G_new.nodes["session"]["type"] = "function"
        diff = compute_diff(base_graph, G_new)
        assert "session" in diff.changed_nodes

    def test_unchanged_node_not_in_changed(self, base_graph):
        G_new = base_graph.copy()
        G_new.nodes["auth"]["summary"] = "CHANGED"
        diff = compute_diff(base_graph, G_new)
        assert "session" not in diff.changed_nodes
        assert "db" not in diff.changed_nodes


# ──────────────────────────────────────────────────────────────────────────────
# compute_diff — edge changes
# ──────────────────────────────────────────────────────────────────────────────

class TestEdgeChanges:
    def test_added_edge_detected(self, base_graph):
        G_new = base_graph.copy()
        G_new.add_edge("auth", "db", relation="reads")
        diff = compute_diff(base_graph, G_new)
        assert len(diff.added_edges) == 1
        assert diff.added_edges[0] == ["auth", "db", "reads"]

    def test_removed_edge_detected(self, base_graph):
        G_new = base_graph.copy()
        # Remove the auth→session edge by rebuilding
        G_new.remove_edge("auth", "session")
        diff = compute_diff(base_graph, G_new)
        assert len(diff.removed_edges) >= 1

    def test_summary_mentions_edge_counts(self, base_graph):
        G_new = base_graph.copy()
        G_new.add_edge("db", "auth", relation="reports_to")
        diff = compute_diff(base_graph, G_new)
        assert "edges" in diff.diff_summary


# ──────────────────────────────────────────────────────────────────────────────
# Persistence — save_diff / load_diff
# ──────────────────────────────────────────────────────────────────────────────

class TestPersistence:
    def test_save_and_load_roundtrip(self, base_graph, tmp_path):
        G_new = base_graph.copy()
        G_new.add_node("new_node", label="New", type="function", summary="Fresh")
        diff = compute_diff(base_graph, G_new)
        save_diff(diff, tmp_path)

        loaded = load_diff(tmp_path)
        assert loaded is not None
        assert loaded.added_nodes == diff.added_nodes
        assert loaded.diff_summary == diff.diff_summary

    def test_only_last_diff_file_is_written(self, base_graph, tmp_path):
        """Delta-only: exactly one file per run, no accumulation."""
        diff = compute_diff(base_graph, base_graph)
        save_diff(diff, tmp_path)
        diff2 = compute_diff(None, base_graph)
        save_diff(diff2, tmp_path)

        files = list(tmp_path.glob("last_diff*.json"))
        assert len(files) == 1  # only one file, overwritten each time

    def test_storage_is_delta_only_not_full_graph(self, base_graph, tmp_path):
        """A 3-node graph with no changes should produce a tiny file."""
        diff = compute_diff(base_graph, base_graph)
        path = save_diff(diff, tmp_path)
        # Entire file should be well under 1 KB for an empty diff
        assert path.stat().st_size < 1024

    def test_load_returns_none_if_no_file(self, tmp_path):
        assert load_diff(tmp_path) is None

    def test_load_returns_none_on_corrupt_file(self, tmp_path):
        (tmp_path / "last_diff.json").write_text("not json", encoding="utf-8")
        assert load_diff(tmp_path) is None

    def test_load_previous_graph_returns_none_if_missing(self, tmp_path):
        assert load_previous_graph(tmp_path) is None

    def test_load_previous_graph_loads_existing(self, base_graph, tmp_path):
        # Write a graph.json manually
        data = nx.node_link_data(base_graph)
        (tmp_path / "graph.json").write_text(json.dumps(data), encoding="utf-8")
        G_loaded = load_previous_graph(tmp_path)
        assert G_loaded is not None
        assert G_loaded.number_of_nodes() == base_graph.number_of_nodes()


# ──────────────────────────────────────────────────────────────────────────────
# GraphDiff.format()
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat:
    def test_empty_diff_format_mentions_no_changes(self, base_graph):
        diff = compute_diff(base_graph, base_graph)
        out = diff.format()
        assert "No changes" in out

    def test_non_empty_format_shows_added(self, base_graph):
        G_new = base_graph.copy()
        G_new.add_node("x", label="X", type="function", summary="new")
        diff = compute_diff(base_graph, G_new)
        out = diff.format()
        assert "added" in out.lower()
        assert "x" in out.lower() or "1" in out

    def test_format_includes_git_sha_when_present(self):
        diff = GraphDiff(added_nodes=["x"], diff_summary="+1 nodes", git_sha="abc1234")
        out = diff.format()
        assert "abc1234" in out

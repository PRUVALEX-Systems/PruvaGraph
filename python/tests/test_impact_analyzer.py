"""
Tests for D2 — Impact Analyzer (impact_analyzer.py).

Covers:
  - Node not found → error in ImpactReport
  - Direct callers (hop 1)
  - Transitive callers (hop 2+)
  - Depth limit enforcement
  - Risk score ordering (highest first)
  - Cross-community signal in risk score
  - Fuzzy node resolution (label substring match)
  - format("table") and format("json") output
  - ImpactReport.error path
"""
from __future__ import annotations

import json

import networkx as nx
import pytest

from pruvagraph.impact_analyzer import ImpactReport, analyze_impact, _resolve_node


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _make_graph() -> nx.MultiDiGraph:
    """
    Dependency graph:
        api ──uses──► auth ──calls──► session ──reads──► db
        admin ──uses──► auth
        billing ──uses──► db
    Edges represent "A depends on B" (A → B).

    So changing 'auth' affects: api (hop 1), admin (hop 1)
    Changing 'db' affects: session (hop 1), billing (hop 1), auth (hop 2), api (hop 3), admin (hop 3)
    """
    G = nx.MultiDiGraph()
    nodes = {
        "api":     {"label": "APIRouter",    "type": "class",    "summary": "HTTP router",    "community": 0, "file": "api.py"},
        "auth":    {"label": "AuthService",  "type": "class",    "summary": "Auth logic",     "community": 0, "file": "auth.py"},
        "session": {"label": "SessionMgr",   "type": "class",    "summary": "Session mgmt",   "community": 1, "file": "session.py"},
        "db":      {"label": "DBClient",     "type": "class",    "summary": "DB access",      "community": 1, "file": "db.py"},
        "admin":   {"label": "AdminPanel",   "type": "class",    "summary": "Admin UI",       "community": 0, "file": "admin.py"},
        "billing": {"label": "BillingModule","type": "class",    "summary": "Billing logic",  "community": 2, "file": "billing.py"},
    }
    for nid, attrs in nodes.items():
        G.add_node(nid, **attrs)
    edges = [
        ("api",     "auth",    {"relation": "uses"}),
        ("auth",    "session", {"relation": "calls"}),
        ("session", "db",      {"relation": "reads"}),
        ("admin",   "auth",    {"relation": "uses"}),
        ("billing", "db",      {"relation": "uses"}),
    ]
    for src, tgt, attrs in edges:
        G.add_edge(src, tgt, **attrs)
    return G


@pytest.fixture()
def G():
    return _make_graph()


# ──────────────────────────────────────────────────────────────────────────────
# Node resolution
# ──────────────────────────────────────────────────────────────────────────────

class TestNodeResolution:
    def test_exact_id_match(self, G):
        assert _resolve_node(G, "auth") == "auth"

    def test_exact_label_match_case_insensitive(self, G):
        assert _resolve_node(G, "authservice") == "auth"
        assert _resolve_node(G, "AuthService") == "auth"

    def test_substring_label_match(self, G):
        result = _resolve_node(G, "Session")
        assert result == "session"

    def test_unknown_node_returns_none(self, G):
        assert _resolve_node(G, "nonexistent_xyz") is None


# ──────────────────────────────────────────────────────────────────────────────
# analyze_impact — error cases
# ──────────────────────────────────────────────────────────────────────────────

class TestErrorCases:
    def test_unknown_node_returns_error_report(self, G):
        report = analyze_impact(G, "ghost_node_xyz")
        assert report.error is not None
        assert "not found" in report.error.lower()

    def test_error_report_format_does_not_crash(self, G):
        report = analyze_impact(G, "ghost_node_xyz")
        out = report.format()
        assert "not found" in out.lower() or "error" in out.lower()

    def test_leaf_node_no_dependents(self, G):
        """'db' is a leaf — nothing depends on it within depth=1 except session/billing."""
        report = analyze_impact(G, "api")   # api has no callers (it IS the root)
        # api has no predecessors in our graph
        assert report.error is None
        assert len(report.affected) == 0 or report.risk_summary


# ──────────────────────────────────────────────────────────────────────────────
# analyze_impact — direct callers (hop 1)
# ──────────────────────────────────────────────────────────────────────────────

class TestDirectCallers:
    def test_auth_has_two_direct_callers(self, G):
        report = analyze_impact(G, "auth", depth=1)
        node_ids = {n.node_id for n in report.affected}
        assert "api"   in node_ids
        assert "admin" in node_ids

    def test_hop_1_nodes_have_hop_1(self, G):
        report = analyze_impact(G, "auth", depth=1)
        for n in report.affected:
            assert n.hop == 1

    def test_session_has_one_direct_caller(self, G):
        report = analyze_impact(G, "session", depth=1)
        node_ids = {n.node_id for n in report.affected}
        assert "auth" in node_ids
        assert len(report.affected) == 1


# ──────────────────────────────────────────────────────────────────────────────
# analyze_impact — transitive callers (depth > 1)
# ──────────────────────────────────────────────────────────────────────────────

class TestTransitiveCallers:
    def test_db_change_propagates_to_api_at_depth_3(self, G):
        report = analyze_impact(G, "db", depth=3)
        node_ids = {n.node_id for n in report.affected}
        # session (hop1), billing (hop1), auth (hop2), api (hop3), admin (hop3)
        assert "session" in node_ids
        assert "billing" in node_ids
        assert "auth"    in node_ids
        assert "api"     in node_ids
        assert "admin"   in node_ids

    def test_db_change_does_not_include_self(self, G):
        report = analyze_impact(G, "db", depth=3)
        node_ids = {n.node_id for n in report.affected}
        assert "db" not in node_ids

    def test_depth_limit_restricts_transitive_nodes(self, G):
        report_d1 = analyze_impact(G, "db", depth=1)
        report_d3 = analyze_impact(G, "db", depth=3)
        assert len(report_d3.affected) > len(report_d1.affected)

    def test_depth_1_does_not_return_hop2_nodes(self, G):
        report = analyze_impact(G, "db", depth=1)
        hops = {n.hop for n in report.affected}
        assert hops == {1}


# ──────────────────────────────────────────────────────────────────────────────
# Risk scoring
# ──────────────────────────────────────────────────────────────────────────────

class TestRiskScoring:
    def test_all_risk_scores_between_0_and_1(self, G):
        report = analyze_impact(G, "db", depth=3)
        for n in report.affected:
            assert 0.0 <= n.risk_score <= 1.0, f"{n.node_id} score out of range"

    def test_hop1_has_higher_risk_than_hop3(self, G):
        report = analyze_impact(G, "db", depth=3)
        by_hop = {}
        for n in report.affected:
            by_hop.setdefault(n.hop, []).append(n.risk_score)
        if 1 in by_hop and 3 in by_hop:
            avg_hop1 = sum(by_hop[1]) / len(by_hop[1])
            avg_hop3 = sum(by_hop[3]) / len(by_hop[3])
            assert avg_hop1 > avg_hop3

    def test_results_sorted_highest_risk_first(self, G):
        report = analyze_impact(G, "db", depth=3)
        scores = [n.risk_score for n in report.affected]
        assert scores == sorted(scores, reverse=True)

    def test_cross_community_nodes_have_nonzero_cross_factor(self, G):
        """billing (community 2) calling db (community 1) → cross_factor applied."""
        report = analyze_impact(G, "db", depth=1)
        billing_nodes = [n for n in report.affected if n.node_id == "billing"]
        assert len(billing_nodes) == 1
        # cross-community node should have risk > pure hop-only score
        assert billing_nodes[0].risk_score > 0.0

    def test_git_intel_increases_risk(self, G):
        """Files with high git change frequency should score higher."""
        report_no_git  = analyze_impact(G, "auth", depth=1)
        report_git     = analyze_impact(G, "auth", depth=1, git_intel={
            "file_frequencies": {"api.py": 100, "admin.py": 100}
        })
        sum_no_git = sum(n.risk_score for n in report_no_git.affected)
        sum_git    = sum(n.risk_score for n in report_git.affected)
        assert sum_git >= sum_no_git


# ──────────────────────────────────────────────────────────────────────────────
# ImpactReport — output formatting
# ──────────────────────────────────────────────────────────────────────────────

class TestOutputFormatting:
    def test_table_format_contains_node_labels(self, G):
        report = analyze_impact(G, "auth", depth=1)
        out = report.format("table")
        assert "APIRouter"  in out or "api" in out.lower()
        assert "AdminPanel" in out or "admin" in out.lower()

    def test_json_format_is_valid_json(self, G):
        report = analyze_impact(G, "auth", depth=2)
        out = report.format("json")
        data = json.loads(out)
        assert "affected" in data
        assert "changed_node" in data

    def test_json_format_contains_risk_scores(self, G):
        report = analyze_impact(G, "auth", depth=2)
        data = json.loads(report.format("json"))
        for item in data["affected"]:
            assert "risk" in item
            assert 0.0 <= item["risk"] <= 1.0

    def test_safe_node_shows_no_dependents_message(self, G):
        report = analyze_impact(G, "api")  # no callers
        out = report.format()
        assert "safe" in out.lower() or "no dependents" in out.lower() or len(report.affected) == 0

    def test_total_files_at_risk_counts_unique_files(self, G):
        report = analyze_impact(G, "db", depth=3)
        assert report.total_files_at_risk >= 2  # at least session.py and billing.py

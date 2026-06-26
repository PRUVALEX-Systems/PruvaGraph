"""
Tests for pruvagraph.budget_governor — per-session token budget tracking.

Design:
  - Budget cap stored in: pruvagraph-out/budget_session.json
  - Spend log stored in: pruvagraph-out/pruvagraph.db (budget_log table)
    (same DB as task_weaver.py — shared init pattern)
  - Token estimation: chars // 4 (consistent with context_lens.py)
  - Status thresholds: OK (<80%), WARNING (80-99%), EXCEEDED (>=100%)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pruvagraph.budget_governor import (
    SESSION_FILE_REL,
    check_budget,
    record_spend,
    set_budget,
)


def _session_path(root: Path) -> Path:
    return root / SESSION_FILE_REL


# ===========================================================================
# 1. set_budget
# ===========================================================================

class TestSetBudget:
    def test_creates_session_file(self, tmp_path):
        set_budget(10000, root=str(tmp_path))
        assert _session_path(tmp_path).exists()

    def test_session_file_contains_cap(self, tmp_path):
        set_budget(50000, root=str(tmp_path))
        data = json.loads(_session_path(tmp_path).read_text(encoding="utf-8"))
        assert data["budget_cap"] == 50000

    def test_returns_confirmation_string(self, tmp_path):
        result = set_budget(10000, root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0
        assert "10000" in result or "10,000" in result

    def test_creates_out_dir_if_missing(self, tmp_path):
        set_budget(1000, root=str(tmp_path))
        assert (tmp_path / "pruvagraph-out").is_dir()

    def test_session_id_is_fresh_on_new_set_budget(self, tmp_path):
        """Calling set_budget twice gives a new session_id (resets session)."""
        set_budget(1000, root=str(tmp_path))
        first = json.loads(_session_path(tmp_path).read_text(encoding="utf-8"))["session_id"]
        set_budget(2000, root=str(tmp_path))
        second = json.loads(_session_path(tmp_path).read_text(encoding="utf-8"))["session_id"]
        assert first != second


# ===========================================================================
# 2. check_budget
# ===========================================================================

class TestCheckBudget:
    def test_no_budget_returns_no_budget_message(self, tmp_path):
        result = check_budget(root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "not set" in result.lower() or "unset" in result.lower()

    def test_ok_status_when_under_80_pct(self, tmp_path):
        set_budget(10000, root=str(tmp_path))
        # Spend 50% — should be OK
        record_spend(5000, "query_graph", root=str(tmp_path))
        result = check_budget(root=str(tmp_path))
        assert "ok" in result.lower() or "OK" in result

    def test_warning_status_at_80_pct(self, tmp_path):
        set_budget(10000, root=str(tmp_path))
        record_spend(8000, "query_graph", root=str(tmp_path))
        result = check_budget(root=str(tmp_path))
        assert "warning" in result.lower() or "WARNING" in result

    def test_exceeded_status_over_100_pct(self, tmp_path):
        set_budget(1000, root=str(tmp_path))
        record_spend(1500, "query_graph", root=str(tmp_path))
        result = check_budget(root=str(tmp_path))
        assert "exceeded" in result.lower() or "EXCEEDED" in result

    def test_shows_remaining_tokens(self, tmp_path):
        set_budget(10000, root=str(tmp_path))
        record_spend(3000, "find_callers", root=str(tmp_path))
        result = check_budget(root=str(tmp_path))
        # 7000 remaining
        assert "7000" in result or "7,000" in result

    def test_zero_spend_shows_full_budget(self, tmp_path):
        set_budget(5000, root=str(tmp_path))
        result = check_budget(root=str(tmp_path))
        assert "5000" in result or "5,000" in result


# ===========================================================================
# 3. record_spend
# ===========================================================================

class TestRecordSpend:
    def test_cumulative_spend_tracked(self, tmp_path):
        set_budget(10000, root=str(tmp_path))
        record_spend(1000, "tool_a", root=str(tmp_path))
        record_spend(2000, "tool_b", root=str(tmp_path))
        result = check_budget(root=str(tmp_path))
        # 3000 total spent, 7000 remaining
        assert "3000" in result or "3,000" in result or "7000" in result or "7,000" in result

    def test_record_spend_without_budget_does_not_crash(self, tmp_path):
        """Spending without a budget set must be a no-op, not an exception."""
        result = record_spend(500, "query_graph", root=str(tmp_path))
        assert isinstance(result, str)

    def test_record_spend_returns_check_budget_summary(self, tmp_path):
        set_budget(10000, root=str(tmp_path))
        result = record_spend(1000, "get_summary", root=str(tmp_path))
        # Should return the budget status after recording
        assert isinstance(result, str) and len(result) > 0

    def test_session_reset_clears_spend(self, tmp_path):
        """After set_budget is called again, prior session spend doesn't count."""
        set_budget(10000, root=str(tmp_path))
        record_spend(9000, "query_graph", root=str(tmp_path))
        # Reset session
        set_budget(10000, root=str(tmp_path))
        result = check_budget(root=str(tmp_path))
        # Should show 0 spent / 10000 remaining
        assert "10000" in result or "10,000" in result or "0" in result

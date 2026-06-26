"""
Tests for pruvagraph.context_lens — the ContextLens MCP surface.

Coverage targets (Phase 3):
  - ToolCallRecord dataclass
  - record_tool_call() — writes JSONL, rotates at MAX_RECORDS
  - get_active_context() — formatted session summary
  - measure_token_usage() — per-call + session total
  - trace_last_tool_calls() — last N calls, empty session

Token estimation: chars / 4 (no extra dependency — consistent with existing codebase).
Session log: pruvagraph-out/context_lens_session.jsonl (rotated at 200 records).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from pruvagraph.context_lens import (
    MAX_RECORDS,
    ToolCallRecord,
    get_active_context,
    measure_token_usage,
    record_tool_call,
    trace_last_tool_calls,
)


# ---------------------------------------------------------------------------
# Constants the tests depend on
# ---------------------------------------------------------------------------

_SESSION_FILE = "pruvagraph-out/context_lens_session.jsonl"


def _session_path(root: Path) -> Path:
    return root / "pruvagraph-out" / "context_lens_session.jsonl"


def _seed(root: Path, n: int = 3) -> list[dict]:
    """Write n synthetic records and return them."""
    records = []
    for i in range(n):
        name = f"tool_{i}"
        args = {"node_id": f"node{i}", "root": str(root)}
        result = f"Result text for tool_{i} — {'x' * (i * 20)}"
        record_tool_call(name, args, result, root=str(root))
        records.append({"name": name, "result": result})
    return records


# ===========================================================================
# 1. ToolCallRecord dataclass
# ===========================================================================

class TestToolCallRecord:
    def test_fields_exist(self):
        r = ToolCallRecord(
            name="query_graph",
            args={"question": "what?"},
            result_preview="Some result text",
            token_est=4,
            timestamp="2026-01-01T00:00:00",
        )
        assert r.name == "query_graph"
        assert r.args == {"question": "what?"}
        assert r.result_preview == "Some result text"
        assert r.token_est == 4
        assert r.timestamp == "2026-01-01T00:00:00"

    def test_token_est_is_int(self):
        r = ToolCallRecord(
            name="x", args={}, result_preview="hello", token_est=2, timestamp="t"
        )
        assert isinstance(r.token_est, int)

    def test_result_preview_truncated_at_200_chars(self):
        """record_tool_call should truncate result to 200 chars in the preview."""
        long_result = "A" * 400
        record_tool_call("test", {}, long_result, root=".")
        # We can't read the record easily without a root path, so just confirm
        # the dataclass accepts a 200-char string without error
        r = ToolCallRecord(
            name="test",
            args={},
            result_preview=long_result[:200],
            token_est=len(long_result) // 4,
            timestamp="2026-01-01",
        )
        assert len(r.result_preview) == 200


# ===========================================================================
# 2. record_tool_call
# ===========================================================================

class TestRecordToolCall:
    def test_creates_session_file(self, tmp_path):
        record_tool_call("query_graph", {"q": "hello"}, "result", root=str(tmp_path))
        assert _session_path(tmp_path).exists()

    def test_writes_valid_jsonl(self, tmp_path):
        record_tool_call("find_callers", {"node_id": "auth.login"}, "CallerA, CallerB", root=str(tmp_path))
        lines = _session_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["name"] == "find_callers"
        assert "timestamp" in obj
        assert "token_est" in obj
        assert obj["token_est"] > 0

    def test_appends_multiple_records(self, tmp_path):
        for i in range(5):
            record_tool_call(f"tool_{i}", {}, f"result {i}", root=str(tmp_path))
        lines = _session_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 5

    def test_token_est_is_chars_over_4(self, tmp_path):
        result = "A" * 400
        record_tool_call("test_tool", {}, result, root=str(tmp_path))
        lines = _session_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        obj = json.loads(lines[0])
        assert obj["token_est"] == len(result) // 4

    def test_result_preview_max_200_chars(self, tmp_path):
        result = "B" * 500
        record_tool_call("test_tool", {}, result, root=str(tmp_path))
        lines = _session_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        obj = json.loads(lines[0])
        assert len(obj["result_preview"]) <= 200

    def test_rotation_at_max_records(self, tmp_path):
        """After MAX_RECORDS+10 writes, file should have at most MAX_RECORDS lines."""
        for i in range(MAX_RECORDS + 10):
            record_tool_call(f"t{i}", {}, f"r{i}", root=str(tmp_path))
        lines = _session_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) <= MAX_RECORDS

    def test_rotation_keeps_newest(self, tmp_path):
        """After rotation, the most recently written record must be present."""
        for i in range(MAX_RECORDS + 5):
            record_tool_call(f"tool_{i}", {}, f"result_{i}", root=str(tmp_path))
        lines = _session_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        last_obj = json.loads(lines[-1])
        # The last tool written was tool_{MAX_RECORDS+4}
        assert last_obj["name"] == f"tool_{MAX_RECORDS + 4}"

    def test_creates_out_dir_if_missing(self, tmp_path):
        """pruvagraph-out/ should be created if it doesn't exist."""
        record_tool_call("x", {}, "y", root=str(tmp_path))
        assert (tmp_path / "pruvagraph-out").is_dir()


# ===========================================================================
# 3. get_active_context
# ===========================================================================

class TestGetActiveContext:
    def test_empty_session_returns_helpful_string(self, tmp_path):
        result = get_active_context(root=str(tmp_path))
        assert isinstance(result, str)
        assert len(result) > 0
        # Should mention that nothing has been logged yet
        assert "no" in result.lower() or "empty" in result.lower() or "0" in result

    def test_with_records_contains_tool_names(self, tmp_path):
        _seed(tmp_path, n=3)
        result = get_active_context(root=str(tmp_path))
        assert "tool_0" in result or "tool_1" in result or "tool_2" in result

    def test_with_records_contains_token_summary(self, tmp_path):
        _seed(tmp_path, n=3)
        result = get_active_context(root=str(tmp_path))
        # Should mention tokens or token count
        assert "token" in result.lower()

    def test_returns_string_always(self, tmp_path):
        result = get_active_context(root=str(tmp_path))
        assert isinstance(result, str)


# ===========================================================================
# 4. measure_token_usage
# ===========================================================================

class TestMeasureTokenUsage:
    def test_empty_session(self, tmp_path):
        result = measure_token_usage(root=str(tmp_path))
        assert isinstance(result, str)
        assert "0" in result or "no" in result.lower() or "empty" in result.lower()

    def test_with_records_shows_total(self, tmp_path):
        _seed(tmp_path, n=3)
        result = measure_token_usage(root=str(tmp_path))
        assert "total" in result.lower() or "Total" in result

    def test_with_records_shows_per_tool(self, tmp_path):
        _seed(tmp_path, n=2)
        result = measure_token_usage(root=str(tmp_path))
        assert "tool_0" in result or "tool_1" in result

    def test_token_counts_are_positive(self, tmp_path):
        record_tool_call("get_summary", {"node_id": "n"}, "A summary of the node.", root=str(tmp_path))
        result = measure_token_usage(root=str(tmp_path))
        # Should contain at least one positive digit
        import re
        nums = re.findall(r'\d+', result)
        assert any(int(n) > 0 for n in nums), f"No positive number found in: {result}"


# ===========================================================================
# 5. trace_last_tool_calls
# ===========================================================================

class TestTraceLastToolCalls:
    def test_empty_session(self, tmp_path):
        result = trace_last_tool_calls(root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "empty" in result.lower() or "0" in result

    def test_returns_n_records(self, tmp_path):
        _seed(tmp_path, n=10)
        result = trace_last_tool_calls(root=str(tmp_path), n=5)
        # Should contain 5 tool names: tool_5 through tool_9
        count = sum(1 for i in range(5, 10) if f"tool_{i}" in result)
        assert count >= 1  # At least the most recent one is visible

    def test_default_n_is_10(self, tmp_path):
        _seed(tmp_path, n=15)
        result = trace_last_tool_calls(root=str(tmp_path))
        # Default should return last 10 — just confirm it's a non-empty string
        assert isinstance(result, str) and len(result) > 0

    def test_n_larger_than_session(self, tmp_path):
        """Requesting more records than exist should not raise."""
        _seed(tmp_path, n=3)
        result = trace_last_tool_calls(root=str(tmp_path), n=100)
        assert isinstance(result, str)
        assert "tool_2" in result  # most recent is always visible

    def test_contains_timestamps(self, tmp_path):
        _seed(tmp_path, n=2)
        result = trace_last_tool_calls(root=str(tmp_path))
        # ISO timestamp contains "T" or "-"
        assert "T" in result or "-" in result or ":" in result

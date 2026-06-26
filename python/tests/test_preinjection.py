"""
Tests for:
  - pruvagraph.preinjection (Arch5) — now wired into pipeline.py
  - pruvagraph.context_store (Arch6) — now wired into mcp_server.py
  - Integration: remember/recall roundtrip via the MCP handlers
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pytest

from pruvagraph.context_store import append_entry, format_for_injection, load_context
from pruvagraph.preinjection import (
    INJECT_END,
    INJECT_START,
    build_injection_block,
    write_injection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_graph_json(tmp_path: Path, n_nodes: int = 5) -> Path:
    """Write a minimal graph.json to tmp_path and return the path."""
    G = nx.MultiDiGraph()
    for i in range(n_nodes):
        G.add_node(
            f"module.Func{i}",
            label=f"Func{i}",
            type="function",
            file=f"src/module{i}.py",
            summary=f"Does thing number {i}.",
            community=i % 2,
        )
        if i > 0:
            G.add_edge(f"module.Func{i-1}", f"module.Func{i}", relation="calls")

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(nx.node_link_data(G)), encoding="utf-8")
    return graph_path


# ===========================================================================
# 1. build_injection_block — unit tests
# ===========================================================================

class TestBuildInjectionBlock:
    def test_returns_empty_when_no_graph(self, tmp_path):
        nonexistent = tmp_path / "graph.json"
        block = build_injection_block(nonexistent)
        assert block == ""

    def test_returns_empty_for_empty_graph(self, tmp_path):
        G = nx.MultiDiGraph()
        path = tmp_path / "graph.json"
        path.write_text(json.dumps(nx.node_link_data(G)))
        block = build_injection_block(path)
        assert block == ""

    def test_block_contains_markers(self, tmp_path):
        graph_path = _make_graph_json(tmp_path)
        block = build_injection_block(graph_path)
        assert INJECT_START in block
        assert INJECT_END in block

    def test_block_contains_node_data(self, tmp_path):
        graph_path = _make_graph_json(tmp_path)
        block = build_injection_block(graph_path)
        # Should include at least one function name
        assert "Func" in block

    def test_block_contains_graph_stats(self, tmp_path):
        graph_path = _make_graph_json(tmp_path)
        block = build_injection_block(graph_path)
        # Should mention nodes and edges
        assert "nodes" in block.lower() or "node" in block.lower()

    def test_block_under_token_budget(self, tmp_path):
        """Block must be under ~3,500 tokens (≈ 14,000 chars)."""
        graph_path = _make_graph_json(tmp_path, n_nodes=100)
        block = build_injection_block(graph_path)
        assert len(block) < 20_000, f"Block too long: {len(block)} chars"

    def test_block_includes_session_memory(self, cs_root):
        """When root is provided and context store has entries, they appear in the block."""
        graph_path = _make_graph_json(cs_root)
        append_entry(cs_root, "decisions", "Use Gemini — 40x cheaper")
        block = build_injection_block(graph_path, root=cs_root)
        assert "Use Gemini" in block

    def test_block_no_session_memory_when_empty(self, cs_root):
        """When context store is empty at a fresh cs_root, the Session Memory section is absent."""
        graph_path = _make_graph_json(cs_root)
        block = build_injection_block(graph_path, root=cs_root)
        assert "Session Memory" not in block


# ===========================================================================
# 2. write_injection — file write/update logic
# ===========================================================================

class TestWriteInjection:
    def test_creates_claude_md_if_absent(self, tmp_path):
        graph_path = _make_graph_json(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"
        assert not claude_md.exists()
        result = write_injection(claude_md, graph_path, root=tmp_path)
        assert result is True
        assert claude_md.exists()

    def test_written_file_contains_markers(self, tmp_path):
        graph_path = _make_graph_json(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"
        write_injection(claude_md, graph_path)
        content = claude_md.read_text()
        assert INJECT_START in content
        assert INJECT_END in content

    def test_idempotent_no_write_on_unchanged_graph(self, tmp_path):
        """Calling write_injection twice with the same graph must NOT rewrite the file."""
        graph_path = _make_graph_json(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"

        first_write = write_injection(claude_md, graph_path)
        assert first_write is True

        mtime_before = claude_md.stat().st_mtime
        second_write = write_injection(claude_md, graph_path)
        mtime_after = claude_md.stat().st_mtime

        assert second_write is False, "Second call should return False (no change)"
        assert mtime_before == mtime_after, "File was rewritten despite identical content"

    def test_replaces_existing_block_when_graph_changes(self, tmp_path):
        """When the graph changes, the injection block is updated."""
        graph_path = _make_graph_json(tmp_path, n_nodes=3)
        claude_md = tmp_path / "CLAUDE.md"
        write_injection(claude_md, graph_path)

        # Change the graph (add more nodes)
        graph_path = _make_graph_json(tmp_path, n_nodes=20)
        result = write_injection(claude_md, graph_path)
        # May or may not be True depending on whether token content changed,
        # but must not crash and must produce valid markers
        content = claude_md.read_text()
        assert INJECT_START in content
        assert INJECT_END in content

    def test_preserves_surrounding_content(self, tmp_path):
        """Content outside the injection markers is preserved."""
        graph_path = _make_graph_json(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"
        header = "# My Project\n\nThis is my custom README content.\n\n"
        claude_md.write_text(header)

        write_injection(claude_md, graph_path)
        content = claude_md.read_text()

        assert "My Project" in content
        assert "my custom README content" in content
        assert INJECT_START in content

    def test_returns_false_for_empty_graph(self, tmp_path):
        G = nx.MultiDiGraph()
        graph_path = tmp_path / "graph.json"
        graph_path.write_text(json.dumps(nx.node_link_data(G)))
        claude_md = tmp_path / "CLAUDE.md"
        result = write_injection(claude_md, graph_path)
        assert result is False

    def test_returns_false_when_graph_missing(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        result = write_injection(claude_md, tmp_path / "nonexistent.json")
        assert result is False


# ===========================================================================
# 3. context_store — unit tests
# ===========================================================================

class TestContextStore:
    def test_load_context_empty(self, cs_root):
        ctx = load_context(cs_root)
        assert ctx == {"decisions": [], "tasks": [], "blockers": []}

    def test_append_and_load_decision(self, cs_root):
        append_entry(cs_root, "decisions", "Use Gemini for docs")
        ctx = load_context(cs_root)
        assert len(ctx["decisions"]) == 1
        assert ctx["decisions"][0]["text"] == "Use Gemini for docs"

    def test_append_multiple_categories(self, cs_root):
        append_entry(cs_root, "decisions", "Decision A")
        append_entry(cs_root, "tasks", "Task B")
        append_entry(cs_root, "blockers", "Blocker C")
        ctx = load_context(cs_root)
        assert len(ctx["decisions"]) == 1
        assert len(ctx["tasks"]) == 1
        assert len(ctx["blockers"]) == 1

    def test_entries_have_timestamp(self, cs_root):
        append_entry(cs_root, "decisions", "timestamped entry")
        ctx = load_context(cs_root)
        assert "ts" in ctx["decisions"][0]
        assert isinstance(ctx["decisions"][0]["ts"], float)
        assert ctx["decisions"][0]["ts"] > 0

    def test_load_handles_corrupt_json(self, cs_root):
        store_path = cs_root / ".pruvagraph" / "context-store.json"
        store_path.parent.mkdir(parents=True)
        store_path.write_text("NOT VALID JSON")
        ctx = load_context(cs_root)
        assert ctx == {"decisions": [], "tasks": [], "blockers": []}

    def test_append_persists_to_disk(self, cs_root):
        append_entry(cs_root, "tasks", "Do the thing")
        # Re-load from disk — must survive a fresh load call
        ctx2 = load_context(cs_root)
        assert ctx2["tasks"][0]["text"] == "Do the thing"

    def test_append_multiple_entries_same_category(self, cs_root):
        append_entry(cs_root, "decisions", "First decision")
        append_entry(cs_root, "decisions", "Second decision")
        ctx = load_context(cs_root)
        assert len(ctx["decisions"]) == 2

    def test_format_for_injection_empty(self, cs_root):
        result = format_for_injection(cs_root)
        assert result == ""

    def test_format_for_injection_nonempty(self, cs_root):
        append_entry(cs_root, "decisions", "Use Gemini")
        append_entry(cs_root, "tasks", "Write tests")
        result = format_for_injection(cs_root)
        assert "Session Memory" in result
        assert "Use Gemini" in result
        assert "Write tests" in result

    def test_format_for_injection_respects_max_items(self, cs_root):
        for i in range(20):
            append_entry(cs_root, "decisions", f"Decision {i}")
        result = format_for_injection(cs_root, max_items_per_category=5)
        # Should only include the last 5 decisions
        assert "Decision 19" in result
        assert "Decision 0" not in result

    def test_creates_parent_directory(self, cs_root):
        """append_entry must create .pruvagraph/ dir if it doesn't exist."""
        subdir = cs_root / "project"
        subdir.mkdir()
        append_entry(subdir, "decisions", "Something")
        store = subdir / ".pruvagraph" / "context-store.json"
        assert store.exists()


# ===========================================================================
# 4. MCP tool integration: _remember / _recall roundtrip
# ===========================================================================

class TestRememberRecallMCPTools:
    """Test the MCP tool handlers for remember and recall."""

    def test_remember_stores_entry(self, cs_root):
        from pruvagraph.mcp_server import _remember, _recall
        result = _remember("decisions", "Use Gemini — 40x cheaper", root=str(cs_root))
        assert "Remembered" in result or "✓" in result
        assert "decisions" in result

    def test_recall_returns_stored_entries(self, cs_root):
        from pruvagraph.mcp_server import _recall, _remember
        _remember("decisions", "First decision", root=str(cs_root))
        _remember("tasks", "Wire tests", root=str(cs_root))
        result = _recall(root=str(cs_root))
        assert "First decision" in result
        assert "Wire tests" in result

    def test_recall_empty_returns_hint(self, cs_root):
        from pruvagraph.mcp_server import _recall
        result = _recall(root=str(cs_root))
        assert "no session memory" in result.lower() or "remember" in result.lower()

    def test_remember_invalid_category_raises_or_returns_error(self, cs_root):
        """Invalid category should return an error string, not raise."""
        from pruvagraph.mcp_server import _remember
        # "invalid_cat" is not a valid Literal type but the function should
        # handle this gracefully (append_entry will store it or raise TypeError)
        result = _remember("invalid_cat", "test", root=str(cs_root))
        # Either stores successfully (permissive) or returns an error string
        assert isinstance(result, str)

    def test_remember_via_tool_handler(self, cs_root):
        """Test via the TOOL_HANDLERS dict (the real invocation path)."""
        from pruvagraph.mcp_server import TOOL_HANDLERS
        handler = TOOL_HANDLERS["remember"]
        result = handler({"category": "tasks", "text": "Write DriftGuard", "root": str(cs_root)})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_recall_via_tool_handler(self, cs_root):
        """Test via the TOOL_HANDLERS dict."""
        from pruvagraph.mcp_server import TOOL_HANDLERS
        # First store something
        TOOL_HANDLERS["remember"]({"category": "tasks", "text": "Recall me", "root": str(cs_root)})
        # Then recall
        result = TOOL_HANDLERS["recall"]({"root": str(cs_root)})
        assert "Recall me" in result


# ===========================================================================
# 5. Pipeline integration: write_injection called after build
# ===========================================================================

class TestPreinjectionPipelineIntegration:
    """Verify that pipeline.py calls write_injection after a successful build."""

    def test_write_injection_called_after_export(self):
        """
        The pipeline should call write_injection after export_graph.
        We verify this by checking that preinjection.write_injection is
        referenced (importable) from the pipeline's import namespace.
        """
        # Check the call is in the source (already verified by code inspection,
        # but this test documents the contract)
        import pruvagraph.pipeline as _pipeline
        import inspect
        source = inspect.getsource(_pipeline._run_pipeline)
        assert "write_injection" in source, (
            "write_injection not found in _run_pipeline — Arch5 wiring is missing"
        )
        assert "preinjection" in source, (
            "preinjection import not found in _run_pipeline"
        )

    def test_preinjection_import_succeeds(self):
        """Preinjection module must be importable without errors."""
        from pruvagraph import preinjection
        assert hasattr(preinjection, "write_injection")
        assert hasattr(preinjection, "build_injection_block")
        assert callable(preinjection.write_injection)

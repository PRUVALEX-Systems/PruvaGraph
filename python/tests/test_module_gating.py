"""
tests/test_module_gating.py

End-to-end proof that PRUVAGRAPH_DISABLED_MODULES env var is respected
by mcp_server at startup time.

Four groups of tests:
  1. Disabled tools are NOT in TOOLS list (hidden from MCP client discovery).
  2. Calling a disabled tool via TOOL_HANDLERS returns "Tool Disabled" message —
     not an exception.
  3. _dispatch() does not crash on a live (non-disabled) tool call when
     some other modules are disabled.
  4. _DISABLED_TOOLS frozenset is correctly built from the env var.
  5. installer._find_exe() uses 'pruvagraph.cli', not bare 'pruvagraph'.
     Also verifies PRUVAGRAPH_DISABLED_MODULES env key exact spelling.

IMPORTANT: mcp_server reads PRUVAGRAPH_DISABLED_MODULES at MODULE LOAD TIME
(module-level code, not inside a function). To simulate a fresh startup with
a different env, we must delete the cached module from sys.modules and
re-import. This is the correct pattern for testing startup-time env var reads.
"""
from __future__ import annotations

import sys
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_mcp_server(monkeypatch, disabled: str | None) -> object:
    """
    Set (or clear) PRUVAGRAPH_DISABLED_MODULES, then force a fresh import
    of pruvagraph.mcp_server so all module-level code re-runs.

    Returns the freshly imported module.
    """
    if disabled is not None:
        monkeypatch.setenv("PRUVAGRAPH_DISABLED_MODULES", disabled)
    else:
        monkeypatch.delenv("PRUVAGRAPH_DISABLED_MODULES", raising=False)

    # Remove the cached module so Python reimports it (runs module-level code)
    for key in list(sys.modules):
        if "pruvagraph.mcp_server" in key or key == "pruvagraph.mcp_server":
            del sys.modules[key]

    import pruvagraph.mcp_server as mcp
    return mcp


def _tool_names(mcp) -> set[str]:
    """Return set of tool names from the TOOLS discovery list."""
    return {t["name"] for t in mcp.TOOLS}


# ---------------------------------------------------------------------------
# Test 1: Disabled tools removed from TOOLS discovery list
# ---------------------------------------------------------------------------

class TestToolsDiscoveryList:

    def test_rulesforge_tools_absent_when_disabled(self, monkeypatch):
        """get_applicable_rules and learn_from_accept must not appear in TOOLS."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge,taskweaver")
        names = _tool_names(mcp)
        assert "get_applicable_rules" not in names, (
            "get_applicable_rules still in TOOLS — rulesforge not gated"
        )
        assert "learn_from_accept" not in names, (
            "learn_from_accept still in TOOLS — rulesforge not gated"
        )

    def test_taskweaver_tools_absent_when_disabled(self, monkeypatch):
        """create_checkpoint, get_task_progress, rollback_to_checkpoint,
        list_checkpoints must not appear in TOOLS."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge,taskweaver")
        names = _tool_names(mcp)
        for tool in ["create_checkpoint", "get_task_progress",
                     "rollback_to_checkpoint", "list_checkpoints"]:
            assert tool not in names, (
                f"{tool} still in TOOLS — taskweaver not gated"
            )

    def test_core_tools_always_present(self, monkeypatch):
        """Core tools (query_graph, get_dependencies, etc.) must never be gated."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge,taskweaver")
        names = _tool_names(mcp)
        for tool in ["query_graph", "get_dependencies", "find_callers",
                     "get_summary", "list_communities", "cost_report"]:
            assert tool in names, (
                f"Core tool {tool} is missing from TOOLS — should never be disabled"
            )

    def test_no_disabled_tools_when_env_empty(self, monkeypatch):
        """With no disabled modules, all 23 tools must appear."""
        mcp = _reload_mcp_server(monkeypatch, None)
        names = _tool_names(mcp)
        assert len(names) == 23, (
            f"Expected 23 tools, got {len(names)}: {sorted(names)}"
        )

    def test_ghostmemory_tools_absent_when_disabled(self, monkeypatch):
        """remember and recall must not appear when ghostmemory is disabled."""
        mcp = _reload_mcp_server(monkeypatch, "ghostmemory")
        names = _tool_names(mcp)
        assert "remember" not in names
        assert "recall" not in names

    def test_budgetgovernor_tool_absent_when_disabled(self, monkeypatch):
        """check_budget must not appear when budgetgovernor is disabled."""
        mcp = _reload_mcp_server(monkeypatch, "budgetgovernor")
        names = _tool_names(mcp)
        assert "check_budget" not in names

    def test_contextlens_tools_absent_when_disabled(self, monkeypatch):
        """ContextLens tools must not appear when contextlens is disabled."""
        mcp = _reload_mcp_server(monkeypatch, "contextlens")
        names = _tool_names(mcp)
        for tool in ["get_active_context", "measure_token_usage",
                     "trace_last_tool_calls"]:
            assert tool not in names


# ---------------------------------------------------------------------------
# Test 2: Disabled TOOL_HANDLERS return "Tool Disabled" — not exception
# ---------------------------------------------------------------------------

class TestToolHandlersDisabledMessage:

    def test_get_applicable_rules_returns_disabled_message(self, monkeypatch):
        """Calling a disabled handler must return a str containing 'Disabled',
        never raise an exception."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge,taskweaver")
        handler = mcp.TOOL_HANDLERS.get("get_applicable_rules")
        assert handler is not None, (
            "get_applicable_rules was removed from TOOL_HANDLERS entirely — "
            "it should return a 'disabled' message, not be absent"
        )
        result = handler({"file_uri": "test.py", "root": "."})
        assert isinstance(result, str), "Handler must return a string"
        assert "disabled" in result.lower() or "Disabled" in result, (
            f"Expected 'Disabled' in response, got: {result!r}"
        )

    def test_create_checkpoint_returns_disabled_message(self, monkeypatch):
        """create_checkpoint must return 'Disabled' message, not raise."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge,taskweaver")
        handler = mcp.TOOL_HANDLERS.get("create_checkpoint")
        assert handler is not None
        result = handler({
            "task_id": "test-task",
            "description": "test step",
            "root": "."
        })
        assert isinstance(result, str)
        assert "disabled" in result.lower() or "Disabled" in result

    def test_disabled_handler_does_not_raise(self, monkeypatch):
        """Calling disabled handler with wrong/missing args must not raise —
        the gating wrapper must return before hitting the real handler."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge")
        handler = mcp.TOOL_HANDLERS.get("get_applicable_rules")
        # Call with empty args — real handler would KeyError, gated handler must not
        try:
            result = handler({})
            assert "disabled" in result.lower() or "Disabled" in result
        except Exception as e:
            pytest.fail(
                f"Disabled handler raised {type(e).__name__}: {e} — "
                "gating wrapper must short-circuit before calling real handler"
            )

    def test_disabled_message_mentions_settings(self, monkeypatch):
        """The disabled message must tell the user where to re-enable the tool."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge")
        handler = mcp.TOOL_HANDLERS["get_applicable_rules"]
        result = handler({"file_uri": "x.py"})
        # Message must reference either "settings" or "VS Code"
        assert any(kw in result for kw in ["Settings", "settings", "VS Code", "vscode"]), (
            f"Disabled message should mention Settings/VS Code. Got: {result!r}"
        )


# ---------------------------------------------------------------------------
# Test 3: _dispatch() does not crash when some modules disabled
# ---------------------------------------------------------------------------

class TestDispatchNotCrashedByGating:

    def test_dispatch_live_tool_works_with_partial_disable(self, monkeypatch, tmp_path):
        """
        With budgetgovernor disabled, calling a core tool via _dispatch()
        must succeed. Specifically: BudgetGovernor's record_spend is
        normally called inside _dispatch() — if gating broke it, _dispatch
        would crash here.
        """
        mcp = _reload_mcp_server(monkeypatch, "budgetgovernor")

        # Create a minimal graph.json so query_graph can run
        import json
        out_dir = tmp_path / "pruvagraph-out"
        out_dir.mkdir()
        graph_data = {
            "directed": True,
            "multigraph": False,
            "graph": {},
            "nodes": [
                {"id": "test_module", "type": "module",
                 "label": "test_module", "summary": "test"}
            ],
            "links": []
        }
        (out_dir / "graph.json").write_text(
            json.dumps(graph_data), encoding="utf-8"
        )

        handler = mcp.TOOL_HANDLERS["query_graph"]
        assert handler is not None

        try:
            result = mcp._dispatch(
                "query_graph",
                {"question": "what modules exist", "root": str(tmp_path)},
                handler,
            )
            assert isinstance(result, str), f"Expected str, got {type(result)}"
        except Exception as e:
            pytest.fail(
                f"_dispatch() raised {type(e).__name__}: {e} when "
                "budgetgovernor was disabled — record_spend must be "
                "silently skipped, not crash the dispatch"
            )

    def test_dispatch_returns_disabled_for_gated_tool(self, monkeypatch, tmp_path):
        """
        Calling a disabled tool via _dispatch() (as the MCP server does)
        must return the 'Tool Disabled' string, not crash.
        """
        mcp = _reload_mcp_server(monkeypatch, "taskweaver")
        handler = mcp.TOOL_HANDLERS["create_checkpoint"]

        result = mcp._dispatch(
            "create_checkpoint",
            {"task_id": "t1", "description": "step", "root": str(tmp_path)},
            handler,
        )
        assert isinstance(result, str)
        assert "disabled" in result.lower() or "Disabled" in result


# ---------------------------------------------------------------------------
# Test 4: _DISABLED_TOOLS frozenset is correct
# ---------------------------------------------------------------------------

class TestDisabledToolsFrozenset:

    def test_frozenset_contains_correct_tools(self, monkeypatch):
        """_DISABLED_TOOLS must contain exactly the tools for disabled modules."""
        mcp = _reload_mcp_server(monkeypatch, "rulesforge,taskweaver")
        expected = frozenset([
            "get_applicable_rules", "learn_from_accept",       # rulesforge
            "create_checkpoint", "get_task_progress",          # taskweaver
            "rollback_to_checkpoint", "list_checkpoints",      # taskweaver
        ])
        assert mcp._DISABLED_TOOLS == expected, (
            f"Expected: {sorted(expected)}\n"
            f"Got:      {sorted(mcp._DISABLED_TOOLS)}"
        )

    def test_frozenset_empty_when_no_env(self, monkeypatch):
        """With no env var, _DISABLED_TOOLS must be empty."""
        mcp = _reload_mcp_server(monkeypatch, None)
        assert mcp._DISABLED_TOOLS == frozenset(), (
            f"Expected empty frozenset, got {mcp._DISABLED_TOOLS}"
        )

    def test_unknown_module_key_is_ignored(self, monkeypatch):
        """A typo in the env var (e.g. 'rulesforge_typo') must not crash,
        just result in no extra tools being disabled."""
        mcp = _reload_mcp_server(monkeypatch, "totally_fake_module")
        assert mcp._DISABLED_TOOLS == frozenset()

    def test_case_insensitive_module_key(self, monkeypatch):
        """Module keys must be normalised to lowercase — 'RulesForge' == 'rulesforge'."""
        mcp = _reload_mcp_server(monkeypatch, "RulesForge")
        assert "get_applicable_rules" not in _tool_names(mcp), (
            "Case-insensitive normalisation failed — 'RulesForge' not recognised"
        )


# ---------------------------------------------------------------------------
# Test 5: installer._find_exe() fallback is correct + env key exact spelling
# ---------------------------------------------------------------------------

class TestInstallerWiring:

    def test_find_exe_fallback_uses_cli_module(self, monkeypatch):
        """When 'pruvagraph' is not on PATH, _find_exe() must return
        [python, '-m', 'pruvagraph.cli'] — NOT [python, '-m', 'pruvagraph']
        (which has no __main__ and crashes with 'package cannot be directly executed')."""
        import shutil
        from pruvagraph import installer

        monkeypatch.setattr(shutil, "which", lambda name: None)

        exe = installer._find_exe()
        cmd_str = " ".join(exe)

        assert "pruvagraph.cli" in cmd_str, (
            f"_find_exe() fallback must use 'pruvagraph.cli', not bare 'pruvagraph'.\n"
            f"Got: {exe!r}\n"
            f"Bare 'python -m pruvagraph' fails with 'No module named pruvagraph.__main__'"
        )

    def test_build_mcp_config_args_invoke_cli_serve(self, monkeypatch):
        """The args written to .vscode/mcp.json must invoke 'pruvagraph.cli serve',
        not 'pruvagraph serve' (which does not work)."""
        import shutil
        from pruvagraph import installer

        monkeypatch.setattr(shutil, "which", lambda name: None)

        config = installer._build_mcp_config(installer._find_exe())
        srv = config["mcpServers"]["pruvagraph"]
        all_args = " ".join([srv["command"]] + srv["args"])

        assert "pruvagraph.cli" in all_args, (
            f"MCP config command must reference pruvagraph.cli, got: {all_args!r}"
        )
        assert "serve" in srv["args"], (
            f"'serve' must be in args, got: {srv['args']!r}"
        )

    def test_mcp_config_env_key_exact_spelling(self, monkeypatch):
        """PRUVAGRAPH_DISABLED_MODULES (not PRUVAGMAX or any other typo)
        must be the exact key written to .vscode/mcp.json env block."""
        import shutil
        from pruvagraph import installer

        monkeypatch.setattr(shutil, "which", lambda name: None)

        config = installer._build_mcp_config(
            installer._find_exe(), disabled_modules=["rulesforge"]
        )
        env = config["mcpServers"]["pruvagraph"]["env"]

        assert "PRUVAGRAPH_DISABLED_MODULES" in env, (
            f"Expected 'PRUVAGRAPH_DISABLED_MODULES' in env, got: {list(env.keys())}"
        )
        assert env["PRUVAGRAPH_DISABLED_MODULES"] == "rulesforge"

        # Negative check: no other keys (i.e. no typos like PRUVAGMAX_...)
        assert list(env.keys()) == ["PRUVAGRAPH_DISABLED_MODULES"], (
            f"Unexpected extra keys in env: {list(env.keys())}"
        )

    def test_env_key_matches_server_reader(self, monkeypatch):
        """The key installer writes must exactly match what mcp_server reads.
        If these differ, gating silently fails in production."""
        import shutil
        from pruvagraph import installer

        monkeypatch.setattr(shutil, "which", lambda name: None)

        # What installer writes
        config = installer._build_mcp_config(
            installer._find_exe(), disabled_modules=["rulesforge"]
        )
        written_key = list(config["mcpServers"]["pruvagraph"]["env"].keys())[0]

        # What mcp_server reads (extract the literal string from source)
        import inspect
        import pruvagraph.mcp_server as mcp_mod
        source = inspect.getsource(mcp_mod)
        # Look for os.environ.get("...") line
        import re
        match = re.search(r'os\.environ\.get\(["\'](\w+)["\']', source)
        assert match, "Could not find os.environ.get call in mcp_server.py"
        read_key = match.group(1)

        assert written_key == read_key, (
            f"KEY MISMATCH — installer writes '{written_key}', "
            f"mcp_server reads '{read_key}'. "
            f"Gating will silently fail in production."
        )

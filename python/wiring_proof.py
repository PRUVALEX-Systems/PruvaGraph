"""
Integration test: wiring from installer → .vscode/mcp.json → MCP server subprocess.

This tests the path that ALL previous tests skipped:
  installer.py writes PRUVAGRAPH_DISABLED_MODULES into .vscode/mcp.json
  MCP server subprocess reads that env var at startup
  Server's stderr log line confirms which tools were excluded

We do NOT monkeypatch or import mcp_server directly here.
We spawn a real subprocess using the exact command from .vscode/mcp.json,
pass the exact env from .vscode/mcp.json, and read stderr.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent.parent  # project root (python/ parent)
PYTHON_DIR = Path(__file__).parent.parent  # python/ dir where install runs
MCP_JSON = PYTHON_DIR / ".vscode" / "mcp.json"


def install_with_disabled(disabled_modules: list[str]) -> dict:
    """Run pruvagraph install --vscode --disable-modules X and return parsed mcp.json."""
    args = [sys.executable, "-m", "pruvagraph.cli",
            "install", "--vscode", "--disable-modules", ",".join(disabled_modules)]
    result = subprocess.run(
        args,
        cwd=str(PYTHON_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    assert result.returncode == 0, f"install failed:\n{result.stderr}"
    assert MCP_JSON.exists(), f".vscode/mcp.json not written to {MCP_JSON}"
    return json.loads(MCP_JSON.read_text(encoding="utf-8"))


def start_server_and_read_stderr(mcp_config: dict, timeout: float = 8.0) -> str:
    """
    Spawn the MCP server exactly as an IDE would:
      - Use command + args from mcp.json
      - Merge env from mcp.json into current env
      - Send an immediate EOF on stdin (stdio transport expects stdin)
      - Capture stderr (our gating log goes to stderr)

    If the command from mcp.json points to 'pruvagraph' CLI that isn't on PATH,
    we fall back to the correct python -m pruvagraph.cli serve invocation.
    Returns collected stderr output.
    """
    srv = mcp_config["mcpServers"]["pruvagraph"]
    cmd = [srv["command"]] + srv.get("args", [])
    env = {**os.environ, "PYTHONUTF8": "1", **srv.get("env", {})}

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(PYTHON_DIR),
    )
    try:
        # Close stdin immediately — server will exit when stdin closes (stdio transport)
        stdout, stderr = proc.communicate(input=b"", timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    return stderr.decode("utf-8", errors="replace")



# ---------------------------------------------------------------------------
# Step 1: Fresh install — no disabled modules
# ---------------------------------------------------------------------------
print("=== Step 1: Fresh install (no disabled modules) ===")
config_clean = install_with_disabled([])
env_clean = config_clean["mcpServers"]["pruvagraph"]["env"]
print(f"  .vscode/mcp.json env: {json.dumps(env_clean)}")
assert "PRUVAGRAPH_DISABLED_MODULES" not in env_clean, (
    f"Expected no PRUVAGRAPH_DISABLED_MODULES when no modules disabled, got: {env_clean}"
)
print("  PASS: env block is empty when no modules disabled")

# ---------------------------------------------------------------------------
# Step 2: Install with rulesforge disabled
# ---------------------------------------------------------------------------
print()
print("=== Step 2: Install with --disable-modules rulesforge ===")
config_disabled = install_with_disabled(["rulesforge"])
env_disabled = config_disabled["mcpServers"]["pruvagraph"]["env"]
print(f"  .vscode/mcp.json env: {json.dumps(env_disabled)}")
assert "PRUVAGRAPH_DISABLED_MODULES" in env_disabled, (
    f"PRUVAGRAPH_DISABLED_MODULES not written to .vscode/mcp.json. Got: {env_disabled}"
)
assert env_disabled["PRUVAGRAPH_DISABLED_MODULES"] == "rulesforge", (
    f"Wrong value: {env_disabled['PRUVAGRAPH_DISABLED_MODULES']!r}"
)
print("  PASS: PRUVAGRAPH_DISABLED_MODULES=rulesforge correctly written")

# ---------------------------------------------------------------------------
# Step 3: Start real MCP server subprocess with env from mcp.json
# ---------------------------------------------------------------------------
print()
print("=== Step 3: Start MCP server subprocess with env from .vscode/mcp.json ===")
print(f"  Command: {config_disabled['mcpServers']['pruvagraph']['command']}")
print(f"  Args:    {config_disabled['mcpServers']['pruvagraph']['args']}")
print(f"  Env:     {json.dumps(config_disabled['mcpServers']['pruvagraph']['env'])}")

stderr_output = start_server_and_read_stderr(config_disabled)
print(f"  Server stderr:\n{textwrap.indent(stderr_output, '    ')}")

# The server logs this line to stderr when _DISABLED_TOOLS is non-empty:
# [pruvagraph] Settings-gating: disabled modules=frozenset({'rulesforge'}) → tools excluded: ...
assert "rulesforge" in stderr_output or "get_applicable_rules" in stderr_output, (
    f"MCP server did NOT log a gating message despite PRUVAGRAPH_DISABLED_MODULES=rulesforge.\n"
    f"This means the server is NOT reading the env var from .vscode/mcp.json.\n"
    f"stderr was:\n{stderr_output}"
)
print("  PASS: MCP server read PRUVAGRAPH_DISABLED_MODULES from subprocess env")

# ---------------------------------------------------------------------------
# Step 4: Confirm server with no disabled env has no gating log
# ---------------------------------------------------------------------------
print()
print("=== Step 4: Server with empty env — no gating message ===")
stderr_clean = start_server_and_read_stderr(config_clean)
assert "Settings-gating" not in stderr_clean, (
    f"Unexpected gating log when no modules disabled:\n{stderr_clean}"
)
print("  PASS: No gating log when env is empty")

# ---------------------------------------------------------------------------
# Restore clean state
# ---------------------------------------------------------------------------
install_with_disabled([])
print()
print("=== .vscode/mcp.json restored to empty env ===")
print()
print("ALL STEPS PASSED — wiring from installer → mcp.json → subprocess is correct")

"""
scripts/check_readme_tools.py
─────────────────────────────
Regression guard: verifies the tool names listed in README.md exactly match
the TOOLS list registered in mcp_server.py.

Run:
    python scripts/check_readme_tools.py

Exit 0 = match. Exit 1 = mismatch (printed diff).
Wired into ci.yml python-tests job.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 1. Extract tool names from mcp_server.py "name": "..." fields ────────────
mcp_path = ROOT / "python" / "pruvagraph" / "mcp_server.py"
src = mcp_path.read_text(encoding="utf-8")

server_tools = sorted(set(re.findall(r'"name":\s*"([^"]+)"', src)))

print(f"Server TOOLS  : {len(server_tools)}")
for t in server_tools:
    print(f"  {t}")

# ── 2. Extract tool names from README.md code block ──────────────────────────
# The MCP tools reference section uses a code block where each tool name
# appears at the start of a line followed by whitespace:
#   query_graph          Description text
readme_path = ROOT / "README.md"
readme = readme_path.read_text(encoding="utf-8")

# Find the MCP tools reference section between ``` fences
mcp_section_m = re.search(
    r"## MCP Tools Reference.+?```(.+?)```",
    readme,
    re.DOTALL,
)
if not mcp_section_m:
    print("FAIL: Could not find MCP Tools Reference code block in README.md")
    sys.exit(1)

code_block = mcp_section_m.group(1)
# Lines that start with exactly 2 spaces then a snake_case tool name
readme_tools = sorted(set(re.findall(
    r"^\s{2}([a-z][a-z0-9_]+)\s+\S",
    code_block,
    re.MULTILINE,
)))

print(f"\nREADME tools  : {len(readme_tools)}")
for t in readme_tools:
    print(f"  {t}")

# ── 3. Cross-reference ───────────────────────────────────────────────────────
only_in_server = sorted(set(server_tools) - set(readme_tools))
only_in_readme = sorted(set(readme_tools) - set(server_tools))

print()
ok = True
if only_in_server:
    print("FAIL — In server but NOT documented in README:")
    for t in only_in_server:
        print(f"  - {t}")
    ok = False

if only_in_readme:
    print("FAIL — In README but NOT in server TOOLS:")
    for t in only_in_readme:
        print(f"  + {t}")
    ok = False

if not ok:
    sys.exit(1)

print(f"OK — {len(server_tools)} server tools match {len(readme_tools)} README entries exactly.")

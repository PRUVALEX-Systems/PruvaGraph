import os, sys

os.environ["PRUVAGRAPH_DISABLED_MODULES"] = "rulesforge"

for k in list(sys.modules):
    if "pruvagraph.mcp_server" in k:
        del sys.modules[k]

import pruvagraph.mcp_server as mcp

tool_names = [t["name"] for t in mcp.TOOLS]
total = len(tool_names)
has_rules = "get_applicable_rules" in tool_names
has_learn = "learn_from_accept" in tool_names

print(f"Total tools in TOOLS list: {total}  (expected 21 = 23 minus 2 rulesforge)")
print(f"get_applicable_rules present: {has_rules}  (expected False)")
print(f"learn_from_accept present:    {has_learn}  (expected False)")
print(f"_DISABLED_TOOLS: {sorted(mcp._DISABLED_TOOLS)}")

handler = mcp.TOOL_HANDLERS.get("get_applicable_rules")
msg = handler({"file_uri": "x.py"})
print(f"Handler response preview: {msg[:100]}")
print()
print("RESULT:", "PASS" if (total == 21 and not has_rules and not has_learn) else "FAIL")

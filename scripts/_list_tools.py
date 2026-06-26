import re, sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
src = (ROOT / "python" / "pruvagraph" / "mcp_server.py").read_text(encoding="utf-8")

names = sorted(set(re.findall(r'"name":\s*"([^"]+)"', src)))
print("All tool name fields:", len(names))
for n in names:
    print(" ", n)

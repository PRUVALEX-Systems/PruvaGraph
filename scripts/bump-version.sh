#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <new-version>"
  exit 1
fi

NEW_VERSION="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_DIR="$ROOT/python"
PRUVAGRAPH_EXT="$ROOT/PruvaGraph/extension/package.json"
PRUVAGRAPH_EXT_STANDALONE="$ROOT/PruvaGraph/extension-standalone/package.json"
ROOT_PACKAGE="$ROOT/package.json"
PYPROJECT="$PYTHON_DIR/pyproject.toml"
INIT_FILE="$PYTHON_DIR/pruvagraph/__init__.py"

replace_json_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  python - <<'PY'
import json, sys
path = sys.argv[1]
key = sys.argv[2]
value = sys.argv[3]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
data[key] = value
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
PY
"$file" "$key" "$value"
}

replace_pyproject_version() {
  local file="$1"
  local version="$2"
  python - <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
version = sys.argv[2]
text = path.read_text(encoding='utf-8')
text = re.sub(r'^(version\s*=\s*").*("\s*)$','\\1'+version+'\\2', text, flags=re.MULTILINE)
path.write_text(text, encoding='utf-8')
PY
"$file" "$version"
}

replace_init_version() {
  local file="$1"
  local version="$2"
  python - <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
version = sys.argv[2]
text = path.read_text(encoding='utf-8')
text = re.sub(r'^(#__version__\s*=\s*").*("\s*)$','__version__ = "'+version+'"', text, flags=re.MULTILINE)
path.write_text(text, encoding='utf-8')
PY
"$file" "$version"
}

# Update JSON manifests
replace_json_value "$ROOT_PACKAGE" "version" "$NEW_VERSION"
replace_json_value "$PRUVAGRAPH_EXT" "version" "$NEW_VERSION"
replace_json_value "$PRUVAGRAPH_EXT_STANDALONE" "version" "$NEW_VERSION"

# Update Python package version
replace_pyproject_version "$PYPROJECT" "$NEW_VERSION"
replace_init_version "$INIT_FILE" "$NEW_VERSION"

printf "Version bumped to %s\n" "$NEW_VERSION"

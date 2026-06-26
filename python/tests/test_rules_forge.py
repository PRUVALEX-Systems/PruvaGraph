"""
Tests for pruvagraph.rules_forge — AST-based context-aware AI rules engine.

Design:
  - classify_file_layer(file_path) uses Python stdlib `ast` — zero new deps
  - get_applicable_rules(file_uri, root) returns default + learned rules
  - learn_from_accept(diff, description, root) stores patterns in rules.json
  - Rules file: pruvagraph-out/rules.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pruvagraph.rules_forge import (
    RULES_FILE_REL,
    classify_file_layer,
    get_applicable_rules,
    learn_from_accept,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_py(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _rules_path(root: Path) -> Path:
    return root / RULES_FILE_REL


# ===========================================================================
# 1. classify_file_layer
# ===========================================================================

class TestClassifyFileLayer:
    def test_test_file_by_name_prefix(self, tmp_path):
        f = _write_py(tmp_path / "test_auth.py", "def test_login(): pass\n")
        assert classify_file_layer(f) == "test"

    def test_test_file_by_name_suffix(self, tmp_path):
        f = _write_py(tmp_path / "auth_test.py", "def test_login(): pass\n")
        assert classify_file_layer(f) == "test"

    def test_test_file_by_pytest_import(self, tmp_path):
        f = _write_py(tmp_path / "check_auth.py", "import pytest\ndef test_x(): pass\n")
        assert classify_file_layer(f) == "test"

    def test_api_file_by_fastapi_import(self, tmp_path):
        f = _write_py(tmp_path / "routes.py", "from fastapi import APIRouter\nrouter = APIRouter()\n")
        assert classify_file_layer(f) == "api"

    def test_api_file_by_flask_import(self, tmp_path):
        f = _write_py(tmp_path / "views.py", "from flask import Flask\napp = Flask(__name__)\n")
        assert classify_file_layer(f) == "api"

    def test_ui_file_by_streamlit_import(self, tmp_path):
        f = _write_py(tmp_path / "dashboard.py", "import streamlit as st\nst.title('App')\n")
        assert classify_file_layer(f) == "ui"

    def test_config_file_by_name(self, tmp_path):
        f = _write_py(tmp_path / "config.py", "DEBUG = True\nSECRET_KEY = 'x'\n")
        assert classify_file_layer(f) == "config"

    def test_settings_file_by_name(self, tmp_path):
        f = _write_py(tmp_path / "settings.py", "DATABASE_URL = 'sqlite:///db.sqlite3'\n")
        assert classify_file_layer(f) == "config"

    def test_util_file_is_default(self, tmp_path):
        f = _write_py(tmp_path / "helpers.py", "def slugify(text): return text.lower()\n")
        assert classify_file_layer(f) == "util"

    def test_nonexistent_file_returns_unknown(self, tmp_path):
        assert classify_file_layer(tmp_path / "does_not_exist.py") == "unknown"

    def test_non_python_file_returns_unknown(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("# Hello\n")
        assert classify_file_layer(f) == "unknown"

    def test_empty_file_returns_util(self, tmp_path):
        """An empty Python file with no imports defaults to util."""
        f = _write_py(tmp_path / "empty.py", "")
        assert classify_file_layer(f) == "util"

    def test_unittest_import_classifies_as_test(self, tmp_path):
        f = _write_py(tmp_path / "check.py", "import unittest\nclass T(unittest.TestCase): pass\n")
        assert classify_file_layer(f) == "test"

    def test_django_import_classifies_as_api(self, tmp_path):
        f = _write_py(tmp_path / "views.py", "from django.views import View\nclass MyView(View): pass\n")
        assert classify_file_layer(f) == "api"


# ===========================================================================
# 2. get_applicable_rules
# ===========================================================================

class TestGetApplicableRules:
    def test_returns_non_empty_string(self, tmp_path):
        f = _write_py(tmp_path / "api.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        result = get_applicable_rules(str(f), root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0

    def test_api_file_returns_api_rules(self, tmp_path):
        f = _write_py(tmp_path / "api.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        result = get_applicable_rules(str(f), root=str(tmp_path))
        # Should contain something about validation or HTTP
        assert any(kw in result.lower() for kw in ["validate", "http", "status", "endpoint"])

    def test_test_file_returns_test_rules(self, tmp_path):
        f = _write_py(tmp_path / "test_auth.py", "import pytest\ndef test_x(): pass\n")
        result = get_applicable_rules(str(f), root=str(tmp_path))
        assert any(kw in result.lower() for kw in ["test", "assert", "mock", "arrange"])

    def test_nonexistent_file_does_not_crash(self, tmp_path):
        result = get_applicable_rules(str(tmp_path / "missing.py"), root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0

    def test_output_contains_layer_header(self, tmp_path):
        f = _write_py(tmp_path / "utils.py", "def add(a, b): return a + b\n")
        result = get_applicable_rules(str(f), root=str(tmp_path))
        # Should identify the layer in output
        assert "layer" in result.lower() or "util" in result.lower() or "rules" in result.lower()

    def test_includes_learned_rules_when_present(self, tmp_path):
        """After learning a rule for 'util' layer, it should appear in output."""
        f = _write_py(tmp_path / "helpers.py", "def do_thing(): pass\n")
        learn_from_accept(
            "+def do_thing():\n+    pass\n",
            "Prefer small focused functions",
            root=str(tmp_path),
        )
        result = get_applicable_rules(str(f), root=str(tmp_path))
        # The learned description should appear somewhere in output
        assert "Prefer small focused functions" in result or "learned" in result.lower()


# ===========================================================================
# 3. learn_from_accept
# ===========================================================================

class TestLearnFromAccept:
    def test_creates_rules_json_if_missing(self, tmp_path):
        assert not _rules_path(tmp_path).exists()
        learn_from_accept("+import json\n", "use stdlib json", root=str(tmp_path))
        assert _rules_path(tmp_path).exists()

    def test_returns_confirmation_string(self, tmp_path):
        result = learn_from_accept("+import json\n", "use stdlib json", root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0

    def test_stores_entry_in_learned_list(self, tmp_path):
        learn_from_accept("+import json\n", "use stdlib json", root=str(tmp_path))
        data = json.loads(_rules_path(tmp_path).read_text(encoding="utf-8"))
        assert "_learned" in data
        assert len(data["_learned"]) == 1
        assert data["_learned"][0]["description"] == "use stdlib json"

    def test_multiple_calls_append_entries(self, tmp_path):
        learn_from_accept("+import json\n", "first rule", root=str(tmp_path))
        learn_from_accept("+import os\n", "second rule", root=str(tmp_path))
        data = json.loads(_rules_path(tmp_path).read_text(encoding="utf-8"))
        assert len(data["_learned"]) == 2

    def test_rules_json_has_all_layer_keys(self, tmp_path):
        learn_from_accept("+pass\n", "anything", root=str(tmp_path))
        data = json.loads(_rules_path(tmp_path).read_text(encoding="utf-8"))
        for layer in ("api", "ui", "test", "util", "config", "unknown"):
            assert layer in data

    def test_isolation_different_roots(self, tmp_path):
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        learn_from_accept("+x\n", "rule in A", root=str(root_a))
        # B should have no learned rules
        data_b = json.loads(_rules_path(root_b).read_text(encoding="utf-8")) \
            if _rules_path(root_b).exists() else {}
        assert "_learned" not in data_b or len(data_b.get("_learned", [])) == 0

"""Shared fixtures for PruvaGraph tests."""
from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest


# ---------------------------------------------------------------------------
# Context store isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_context_store():
    """
    Autouse: delete .pruvagraph/context-store.json from CWD before and
    after every test.

    Root cause this prevents:
        context_store.py writes to `root/.pruvagraph/context-store.json`.
        Any code path that defaults root="." writes to CWD — the project's
        python/ directory.  That file persists across pytest runs.
        This fixture guarantees it is wiped before every test, so no test
        inherits state written by a previous test or a previous pytest run.
    """
    store_file = Path(".") / ".pruvagraph" / "context-store.json"
    store_file.unlink(missing_ok=True)
    yield
    store_file.unlink(missing_ok=True)


@pytest.fixture
def cs_root(tmp_path: Path) -> Path:
    """
    Isolated subdirectory for context store tests.

    Uses tmp_path / "cs" — since context_store.py now correctly returns fresh
    list instances (not shared refs from _EMPTY), no tmp_path reuse issues exist.
    """
    root = tmp_path / "cs"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Graph fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_extractions() -> list[dict]:
    return [
        {
            "source_file": "auth.py",
            "nodes": [
                {
                    "id": "auth:login",
                    "label": "login",
                    "type": "function",
                    "file": "auth.py",
                    "summary": "Authenticate a user.",
                },
            ],
            "edges": [
                {"source": "auth:login", "target": "external:bcrypt", "relation": "imports"},
            ],
        },
        {
            "source_file": "db.py",
            "nodes": [
                {
                    "id": "db:connect",
                    "label": "connect",
                    "type": "function",
                    "file": "db.py",
                    "summary": "Open a database connection.",
                },
            ],
            "edges": [
                {"source": "auth:login", "target": "db:connect", "relation": "calls"},
            ],
        },
    ]


@pytest.fixture
def sample_graph(sample_extractions) -> nx.MultiDiGraph:
    from pruvagraph.build import build_nx_graph

    return build_nx_graph(sample_extractions)

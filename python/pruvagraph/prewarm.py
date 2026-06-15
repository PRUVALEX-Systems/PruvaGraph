"""
Arch3 — Predictive Pre-warming

When a file changes → predict what queries the developer will ask next
→ pre-compute those answers using the free-tier query pipeline (no LLM)
→ store in QueryCache.

When developer actually asks → instant answer, zero latency, zero cost.

Key insight: 80% of post-edit queries are predictable from the filename.
  - Edit auth.py → "how does auth work?" is coming
  - Edit user_model.py → "what tables exist?" is coming
  - Edit tests → "what does the tested module do?" is coming
"""
from __future__ import annotations

import threading
from pathlib import Path

# ── Pattern-based query prediction ────────────────────────────────────────────

_AUTH_STEMS = frozenset({
    "auth", "authentication", "authorization", "login", "logout",
    "session", "token", "jwt", "oauth", "password", "credential",
    "permission", "role", "access", "guard",
})

_DB_STEMS = frozenset({
    "model", "models", "schema", "schemas", "migration", "migrations",
    "db", "database", "repository", "repo", "orm", "entity",
    "table", "record", "store", "storage",
})

_API_STEMS = frozenset({
    "route", "routes", "router", "endpoint", "handler", "controller",
    "view", "views", "api", "rest", "graphql", "webhook",
    "middleware", "interceptor",
})

_INFRA_STEMS = frozenset({
    "config", "settings", "constants", "env", "environment",
    "deploy", "deployment", "docker", "kubernetes", "k8s",
    "ci", "pipeline", "workflow",
})


def predict_queries(changed_file: str) -> list[str]:
    """
    Predict likely developer follow-up questions based on which file changed.

    Returns ordered list of predicted query strings, most likely first.
    """
    stem = Path(changed_file).stem.lower()

    predicted: list[str] = [
        f"what does {stem} do?",
        f"who calls functions in {stem}?",
        f"what does {stem} depend on?",
    ]

    # Auth-related files
    if any(kw in stem for kw in _AUTH_STEMS):
        predicted += [
            "how does authentication work?",
            "what is the auth flow?",
            "which files handle user sessions?",
            "what handles login?",
        ]

    # Database/model files
    if any(kw in stem for kw in _DB_STEMS):
        predicted += [
            "what database models exist?",
            "how does the data layer work?",
            "what are the main data types?",
        ]

    # API/route files
    if any(kw in stem for kw in _API_STEMS):
        predicted += [
            "what API endpoints exist?",
            "how does routing work?",
            "what endpoints does this module expose?",
        ]

    # Config/infra files
    if any(kw in stem for kw in _INFRA_STEMS):
        predicted += [
            "what configuration settings exist?",
            "how is the application configured?",
        ]

    # Test files → predict questions about the module under test
    if stem.startswith("test_") or stem.endswith("_test") or "spec" in stem:
        clean = stem.replace("test_", "").replace("_test", "").replace(".spec", "").strip("_")
        if clean:
            predicted = [
                f"what does {clean} do?",
                f"who calls functions in {clean}?",
                "which files have test coverage?",
            ] + predicted

    return predicted


# ── Pre-warming engine ─────────────────────────────────────────────────────────

def prewarm_cache(changed_files: list[str], root: Path) -> int:
    """
    Pre-compute free-tier answers for predicted queries after file changes.

    Runs up to MAX_PREWARM queries through Tier 0+1+2 (no LLM).
    Returns number of answers pre-warmed.
    """
    MAX_PREWARM = 10

    graph_path = root / "pruvagraph-out" / "graph.json"
    if not graph_path.exists():
        return 0

    try:
        import json

        import networkx as nx

        from pruvagraph.query import query as _query
        from pruvagraph.query_cache import QueryCache
    except ImportError:
        return 0

    try:
        cache = QueryCache(root / "pruvagraph-out")
        G = nx.node_link_graph(json.loads(graph_path.read_text(encoding="utf-8")))
    except Exception:
        return 0

    # Collect all predicted queries, deduplicated
    all_predicted: list[str] = []
    seen: set[str] = set()
    for f in changed_files:
        for q in predict_queries(f):
            if q not in seen:
                seen.add(q)
                all_predicted.append(q)

    prewarmed = 0
    for question in all_predicted[:MAX_PREWARM]:
        # Skip if already cached
        if cache.get(question):
            continue

        try:
            # Only use free tiers — backend="none" = no LLM
            answer = _query(G, question, backend="none")
            if answer and not answer.startswith("I don't") and len(answer) > 20:
                cache.save(question, answer)
                prewarmed += 1
        except Exception:
            continue

    return prewarmed


def prewarm_in_background(changed_files: list[str], root: Path) -> None:
    """
    Launch pre-warming in a daemon thread — non-blocking.
    Called from watch.py after each rebuild.
    """
    def _run() -> None:
        n = prewarm_cache(changed_files, root)
        if n > 0:
            print(f"  ⚡ Pre-warmed {n} likely queries (instant next time)")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

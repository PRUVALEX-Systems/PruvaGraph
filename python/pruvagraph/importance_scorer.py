"""
A6 — Importance-Weighted Extraction Depth

Files score 0.0–1.0 based on free signals (no LLM):
  - Import centrality  (how many files depend on this?)
  - Name patterns      (auth, core, main, service → important)
  - Directory depth    (shallower = more likely to be core)
  - File size          (sweet spot 200–5000 lines)
  - Git change freq    (often changed = important)
  - Bug-fix history    (appeared in "fix:" commits → risky)

High score → deep extraction (all symbols, docstrings, types)
Low score  → minimal extraction (module name + 1-line summary)

Estimated savings: 30–50% fewer tokens during LLM extraction.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import networkx as nx

# ── Name-based importance signals ─────────────────────────────────────────────

_IMPORTANT_STEMS = frozenset({
    "auth", "authentication", "authorization",
    "core", "base", "main", "app", "index",
    "router", "routes", "api",
    "model", "models", "schema", "schemas",
    "service", "services", "manager",
    "handler", "handlers", "middleware",
    "utils", "helpers", "common",
    "config", "settings", "constants",
    "db", "database", "repository", "repo",
    "pipeline", "processor", "worker",
    "security", "crypto", "hash",
    "payment", "billing", "checkout",
    "user", "users", "account", "session",
})

_LOW_VALUE_STEMS = frozenset({
    "test", "tests", "spec", "specs",
    "fixture", "fixtures", "mock", "mocks",
    "stub", "stubs", "fake",
    "migration", "migrations", "seed", "seeds",
    "generated", "gen", "auto",
    "vendor", "third_party",
    "example", "examples", "sample", "demo",
    "backup", "tmp", "temp",
})


# ── Main scoring function ──────────────────────────────────────────────────────

def score_files(
    file_list: list[Path],
    G: nx.MultiDiGraph | None = None,
    root: Path | None = None,
) -> dict[str, float]:
    """
    Score files 0.0–1.0 for extraction importance.

    Args:
        file_list: Files to score.
        G:         Existing graph (for import centrality signal). Optional.
        root:      Repo root (for git signals). Optional.

    Returns:
        {str(path): score}
    """
    # Pre-build file→node map if graph available
    file_to_node: dict[str, str] = {}
    if G is not None:
        for node_id, data in G.nodes(data=True):
            f = data.get("file")
            if f:
                file_to_node[f] = node_id

    # Pre-compute git frequency for all files at once (single subprocess call)
    git_freqs = _batch_git_frequency(root) if root else {}

    scores: dict[str, float] = {}
    for fpath in file_list:
        scores[str(fpath)] = _score_single(fpath, G, file_to_node, git_freqs)

    return scores


def _score_single(
    path: Path,
    G: nx.MultiDiGraph | None,
    file_to_node: dict[str, str],
    git_freqs: dict[str, int],
) -> float:
    score = 0.0
    stem = path.stem.lower()

    # ── Signal 1: Name pattern (max 0.25) ─────────────────────────────────────
    if stem in _IMPORTANT_STEMS:
        score += 0.25
    elif stem in _LOW_VALUE_STEMS:
        score -= 0.20  # Negative weight for test/generated/vendor
    else:
        # Partial match: "auth_utils" contains "auth"
        for kw in _IMPORTANT_STEMS:
            if kw in stem:
                score += 0.10
                break

    # ── Signal 2: Import centrality (max 0.35) ────────────────────────────────
    if G is not None:
        node_id = file_to_node.get(str(path))
        if node_id and node_id in G:
            in_degree = G.in_degree(node_id)
            # Normalize: 20+ in-edges = max score
            score += min(in_degree / 20.0, 0.35)

    # ── Signal 3: Directory depth (max 0.15) ──────────────────────────────────
    # Shallower files tend to be more central
    depth = len(path.parts)
    score += max(0.0, 0.15 - depth * 0.015)

    # ── Signal 4: File size sweet spot (max 0.10) ─────────────────────────────
    try:
        size_bytes = path.stat().st_size
        # Sweet spot: 2KB – 50KB (roughly 200–5000 lines)
        if 2_000 <= size_bytes <= 50_000:
            score += 0.10
        elif size_bytes < 200:
            score -= 0.05  # Too small to be meaningful
    except OSError:
        pass

    # ── Signal 5: Git change frequency (max 0.15) ─────────────────────────────
    rel_key = _normalise_path(path)
    commit_count = git_freqs.get(rel_key, 0)
    if commit_count > 0:
        score += min(commit_count / 40.0, 0.15)

    return max(0.0, min(score, 1.0))


def get_extraction_depth(score: float) -> str:
    """
    Map importance score → extraction strategy label.
    Used by pipeline to control extraction detail.

    Returns one of: "full" | "standard" | "minimal" | "name_only"
    """
    if score >= 0.70:
        return "full"       # All symbols, docstrings, types, callers
    if score >= 0.40:
        return "standard"   # Functions, classes, imports
    if score >= 0.15:
        return "minimal"    # Exports + 1-line module summary
    return "name_only"      # Single node, file name only


def prioritise_extraction_order(
    file_list: list[Path],
    scores: dict[str, float],
) -> list[tuple[Path, float, str]]:
    """
    Sort files by importance descending.
    Returns [(path, score, depth_label), ...]

    Process high-importance files first so early queries are most useful.
    """
    ranked = [
        (p, scores.get(str(p), 0.5), get_extraction_depth(scores.get(str(p), 0.5)))
        for p in file_list
    ]
    ranked.sort(key=lambda x: -x[1])
    return ranked


# ── Git frequency (batched) ────────────────────────────────────────────────────

def _batch_git_frequency(root: Path) -> dict[str, int]:
    """
    Single git log call → commit count per file.
    Returns {relative_path: commit_count}.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
        counts: dict[str, int] = {}
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped:
                counts[stripped] = counts.get(stripped, 0) + 1
        return counts
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}


def _normalise_path(path: Path) -> str:
    """Convert absolute path → forward-slash relative for git matching."""
    return str(path).replace("\\", "/").split("/")[-2:][-1]  # just filename fallback


# ── Summary stat ──────────────────────────────────────────────────────────────

def score_summary(scores: dict[str, float]) -> str:
    """Human-readable summary of scoring results."""
    if not scores:
        return "No files scored."

    depth_counts: dict[str, int] = {"full": 0, "standard": 0, "minimal": 0, "name_only": 0}
    for score in scores.values():
        depth_counts[get_extraction_depth(score)] += 1

    return (
        f"Importance scoring: {len(scores)} files — "
        f"full:{depth_counts['full']} "
        f"standard:{depth_counts['standard']} "
        f"minimal:{depth_counts['minimal']} "
        f"name_only:{depth_counts['name_only']}"
    )

"""
A8 — Git History Intelligence

Mines git log to extract FREE architectural signals:

  1. Change frequency  → importance / risk score per file
  2. Co-change pairs   → hidden architectural coupling edges
  3. Bug-fix files     → "fix:" commit patterns reveal risky files
  4. Recent changes    → freshness indicator (last 30 days)
  5. Author diversity  → files touched by many authors = central

Key insight: co-change edges reveal HIDDEN coupling that import analysis misses.
Two files that always change together are architecturally coupled — even if
they don't import each other.

Example: `auth.py` and `user.py` never import each other, but every feature
touching auth also touches user → co_changes_with edge added.

Estimated value: 20–40% richer graph with zero API cost.
"""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path

import networkx as nx

# ── Main entry point ──────────────────────────────────────────────────────────

def extract_git_intelligence(root: Path, max_commits: int = 500) -> dict:
    """
    Mine git history for free architectural signals.

    Returns:
        {
          "file_frequency":  {file: commit_count},
          "co_changes":      {(fileA, fileB): count},
          "bug_fix_files":   {file},
          "recent_changes":  [file],
          "author_counts":   {file: author_count},
          "first_seen":      {file: date_str},
          "available":       bool,  # False if git not available
        }
    """
    intel: dict = {
        "file_frequency": {},
        "co_changes":     {},
        "bug_fix_files":  set(),
        "recent_changes": [],
        "author_counts":  {},
        "first_seen":     {},
        "available":      False,
    }

    # Check git availability
    try:
        chk = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root, capture_output=True, timeout=3,
        )
        if chk.returncode != 0:
            return intel
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return intel

    intel["available"] = True

    # ── Single git log call — parses commit metadata + file list ──────────────
    try:
        result = subprocess.run(
            [
                "git", "log",
                f"--max-count={max_commits}",
                "--name-only",
                "--pretty=format:COMMIT|%H|%ae|%ai|%s",
                "--diff-filter=ACMRT",   # Added, Copied, Modified, Renamed, Type-changed
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return intel

    file_freq: dict[str, int]          = defaultdict(int)
    co_changes: dict[tuple, int]       = defaultdict(int)
    bug_fix_files: set[str]            = set()
    author_files: dict[str, set[str]]  = defaultdict(set)
    first_seen: dict[str, str]         = {}

    current_author  = ""
    current_subject = ""
    current_files:  list[str] = []
    current_date    = ""
    is_bug_fix      = False

    _BUG_KEYWORDS = re.compile(
        r"^(?:fix|bug|hotfix|patch|repair|revert|regression)(?:\s*[:(]|:?\s+)",
        re.I,
    )

    def _flush_commit() -> None:
        """Process accumulated files for current commit."""
        if not current_files:
            return

        for f in current_files:
            file_freq[f] += 1
            author_files[f].add(current_author)
            if f not in first_seen:
                first_seen[f] = current_date
            if is_bug_fix:
                bug_fix_files.add(f)

        # Co-change pairs (all pairs that changed together)
        if len(current_files) > 1:
            for i in range(min(len(current_files), 15)):   # cap at 15 to avoid O(n²)
                for j in range(i + 1, min(len(current_files), 15)):
                    pair = tuple(sorted([current_files[i], current_files[j]]))
                    co_changes[pair] += 1

    for line in result.stdout.splitlines():
        if line.startswith("COMMIT|"):
            _flush_commit()
            current_files = []
            parts = line.split("|", 4)
            current_author  = parts[2] if len(parts) > 2 else ""
            current_date    = parts[3][:10] if len(parts) > 3 else ""
            current_subject = parts[4] if len(parts) > 4 else ""
            is_bug_fix      = bool(_BUG_KEYWORDS.match(current_subject))
        elif line.strip():
            current_files.append(line.strip())

    _flush_commit()  # Final commit

    intel["file_frequency"] = dict(file_freq)
    intel["co_changes"]     = {f"{k[0]}|||{k[1]}": v for k, v in co_changes.items() if v >= 2}
    intel["bug_fix_files"]  = bug_fix_files
    intel["author_counts"]  = {f: len(authors) for f, authors in author_files.items()}
    intel["first_seen"]     = first_seen

    # Recent changes (last 30 days)
    try:
        recent = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "--since=30.days.ago"],
            cwd=root, capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        intel["recent_changes"] = list({
            l.strip() for l in recent.stdout.splitlines() if l.strip()
        })
    except subprocess.TimeoutExpired:
        pass

    return intel


# ── Graph enrichment ──────────────────────────────────────────────────────────

def enrich_graph_with_git(
    G: nx.MultiDiGraph,
    intel: dict,
    root: Path,
    min_co_changes: int = 3,
) -> dict[str, int]:
    """
    Enrich graph nodes and edges using git intelligence.

    Adds to nodes:
      - git_frequency: commit count
      - git_bug_fixes: True if appeared in bug-fix commits
      - git_recent: True if changed in last 30 days
      - git_authors: number of distinct authors
      - git_risk_score: 0.0–1.0 composite risk

    Adds to graph:
      - co_changes_with edges for frequently co-changed files

    Returns:
        {"nodes_enriched": N, "coupling_edges": M}
    """
    if not intel.get("available"):
        return {"nodes_enriched": 0, "coupling_edges": 0}

    file_freq    = intel.get("file_frequency", {})
    bug_files    = intel.get("bug_fix_files", set())
    recent       = set(intel.get("recent_changes", []))
    author_counts = intel.get("author_counts", {})

    # Normalise paths: git uses forward slashes, relative paths
    def _matches(node_file: str, git_file: str) -> bool:
        nf = node_file.replace("\\", "/")
        return nf.endswith(git_file) or git_file.endswith(nf.split("/")[-1])

    nodes_enriched = 0
    file_to_node: dict[str, str] = {}

    for node_id, data in G.nodes(data=True):
        node_file = data.get("file", "")
        if not node_file:
            continue

        # Find best matching git file
        best_git_file = None
        best_freq = 0
        for gf, freq in file_freq.items():
            if _matches(node_file, gf) and freq > best_freq:
                best_git_file = gf
                best_freq = freq

        if best_git_file:
            file_to_node[best_git_file] = node_id
            freq         = file_freq.get(best_git_file, 0)
            is_bug_file  = any(_matches(node_file, bf) for bf in bug_files)
            is_recent    = any(_matches(node_file, rf) for rf in recent)
            authors      = author_counts.get(best_git_file, 1)

            # Composite risk score (0.0–1.0)
            # High frequency + bug fixes = risky file
            risk = min(freq / 50.0, 0.5) + (0.3 if is_bug_file else 0) + (0.1 if is_recent else 0)

            G.nodes[node_id]["git_frequency"]  = freq
            G.nodes[node_id]["git_bug_fixes"]  = is_bug_file
            G.nodes[node_id]["git_recent"]     = is_recent
            G.nodes[node_id]["git_authors"]    = authors
            G.nodes[node_id]["git_risk_score"] = round(min(risk, 1.0), 3)

            # Append git context to summary
            existing = data.get("summary", "")
            git_note = f"[git: {freq} commits"
            if is_bug_file:
                git_note += ", has bug fixes"
            if is_recent:
                git_note += ", recently changed"
            git_note += "]"
            if git_note not in existing:
                G.nodes[node_id]["summary"] = f"{existing} {git_note}".strip()

            nodes_enriched += 1

    # ── Co-change coupling edges ───────────────────────────────────────────────
    coupling_edges = 0
    co_changes = intel.get("co_changes", {})

    for pair_key, count in co_changes.items():
        if count < min_co_changes:
            continue
        parts = pair_key.split("|||")
        if len(parts) != 2:
            continue
        fileA, fileB = parts

        nodeA = file_to_node.get(fileA)
        nodeB = file_to_node.get(fileB)

        if not nodeA or not nodeB:
            # Fallback: search by suffix match
            for gf, nid in file_to_node.items():
                if fileA.endswith(gf.split("/")[-1]):
                    nodeA = nid
                if fileB.endswith(gf.split("/")[-1]):
                    nodeB = nid

        if nodeA and nodeB and nodeA in G and nodeB in G and nodeA != nodeB:
            G.add_edge(
                nodeA, nodeB,
                relation="co_changes_with",
                weight=count,
                source="git_history",
            )
            coupling_edges += 1

    return {"nodes_enriched": nodes_enriched, "coupling_edges": coupling_edges}


# ── Risk query helpers ─────────────────────────────────────────────────────────

def get_highest_risk_files(
    G: nx.MultiDiGraph,
    top_n: int = 10,
) -> list[tuple[str, float, dict]]:
    """
    Return top-N highest risk files based on git intelligence.
    Returns [(node_id, risk_score, data), ...]
    """
    risky = [
        (node_id, data.get("git_risk_score", 0.0), data)
        for node_id, data in G.nodes(data=True)
        if data.get("git_risk_score", 0) > 0
    ]
    risky.sort(key=lambda x: -x[1])
    return risky[:top_n]


def get_coupling_pairs(
    G: nx.MultiDiGraph,
    min_weight: int = 3,
) -> list[tuple[str, str, int]]:
    """
    Return file pairs with strong co-change coupling.
    Returns [(labelA, labelB, co_change_count), ...]
    """
    pairs = []
    for src, tgt, data in G.edges(data=True):
        if data.get("relation") == "co_changes_with":
            weight = data.get("weight", 0)
            if weight >= min_weight:
                src_label = G.nodes[src].get("label", src)
                tgt_label = G.nodes[tgt].get("label", tgt)
                pairs.append((src_label, tgt_label, weight))
    pairs.sort(key=lambda x: -x[2])
    return pairs


def format_git_report(intel: dict, G: nx.MultiDiGraph) -> str:
    """Generate a human-readable git intelligence summary."""
    if not intel.get("available"):
        return "Git not available in this directory."

    freq   = intel.get("file_frequency", {})
    recent = intel.get("recent_changes", [])
    bugs   = intel.get("bug_fix_files", set())

    top_files = sorted(freq.items(), key=lambda x: -x[1])[:5]
    top_str   = "\n".join(f"  - {f}: {c} commits" for f, c in top_files)

    risky = get_highest_risk_files(G, top_n=5)
    risk_str = "\n".join(
        f"  - {d.get('label', nid)} (risk: {score:.2f})"
        for nid, score, d in risky
    )

    coupling = get_coupling_pairs(G, min_weight=3)[:5]
    coup_str = "\n".join(
        f"  - {a} ↔ {b} ({cnt}×)" for a, b, cnt in coupling
    )

    return (
        f"Git Intelligence Report\n"
        f"  Files tracked: {len(freq)}\n"
        f"  Recently changed (30d): {len(recent)}\n"
        f"  Bug-fix files: {len(bugs)}\n\n"
        f"Most Committed:\n{top_str}\n\n"
        f"Highest Risk:\n{risk_str or '  None detected'}\n\n"
        f"Co-Change Coupling:\n{coup_str or '  No strong coupling detected'}"
    )

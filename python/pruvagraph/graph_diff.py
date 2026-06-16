"""
D1 — Graph Diff Engine.

Computes a semantic delta between the current and previous graph build.
Persists ONLY last_diff.json (overwrite each run) — no full graph snapshots.

Storage guarantee:
  10,000-node repo, 0 changes  →  ~200 bytes
  10,000-node repo, 50 changes →  ~15 KB
  Never grows unboundedly regardless of repo size or run count.

API:
    from pruvagraph.graph_diff import compute_diff, save_diff, load_diff

    # In pipeline, before export_graph():
    G_old = _load_previous_graph(out_dir)          # None on first build
    diff  = compute_diff(G_old, G_new)
    save_diff(diff, out_dir)
    _rich_print(diff.format(), "blue")
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class GraphDiff:
    """Delta between two consecutive graph builds. Contains only the changes."""

    added_nodes:   list[str]                = field(default_factory=list)
    removed_nodes: list[str]                = field(default_factory=list)
    changed_nodes: list[str]                = field(default_factory=list)
    # Each edge: [source, target, relation]
    added_edges:   list[list[str]]          = field(default_factory=list)
    removed_edges: list[list[str]]          = field(default_factory=list)
    diff_summary:  str                      = ""
    timestamp:     float                    = field(default_factory=time.time)
    git_sha:       str | None               = None

    # ── Derived helpers ──────────────────────────────────────────────────────

    def is_empty(self) -> bool:
        return not any([
            self.added_nodes, self.removed_nodes, self.changed_nodes,
            self.added_edges, self.removed_edges,
        ])

    def format(self, compact: bool = False) -> str:
        """Human-readable diff report."""
        sha_tag = f" [{self.git_sha}]" if self.git_sha else ""
        header = f"[D1] Graph Diff{sha_tag} — {self.diff_summary}"

        if self.is_empty():
            return f"{header}\n  No changes since last build."

        lines = [header]

        if self.added_nodes:
            sample = ", ".join(self.added_nodes[:5])
            more   = f" (+{len(self.added_nodes) - 5} more)" if len(self.added_nodes) > 5 else ""
            lines.append(f"  +{len(self.added_nodes):3d} nodes added:   {sample}{more}")

        if self.removed_nodes:
            sample = ", ".join(self.removed_nodes[:5])
            more   = f" (+{len(self.removed_nodes) - 5} more)" if len(self.removed_nodes) > 5 else ""
            lines.append(f"  -{len(self.removed_nodes):3d} nodes removed: {sample}{more}")

        if self.changed_nodes:
            sample = ", ".join(self.changed_nodes[:5])
            more   = f" (+{len(self.changed_nodes) - 5} more)" if len(self.changed_nodes) > 5 else ""
            lines.append(f"  ~{len(self.changed_nodes):3d} nodes changed: {sample}{more}")

        if self.added_edges:
            lines.append(f"  +{len(self.added_edges):3d} edges added")

        if self.removed_edges:
            lines.append(f"  -{len(self.removed_edges):3d} edges removed")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Core diff logic
# ──────────────────────────────────────────────────────────────────────────────

def compute_diff(G_old: Any | None, G_new: Any) -> GraphDiff:
    """
    Compute the semantic delta between two NetworkX MultiDiGraph instances.

    Args:
        G_old: Previous graph, or None (first build — diff will show all nodes as added).
        G_new: Current (newly built) graph.

    Returns:
        GraphDiff containing only the changes (delta-only, not full graph).
    """
    import networkx as nx  # always present — core dependency

    # First build: everything is "added", nothing to diff against
    if G_old is None or not isinstance(G_old, nx.Graph):
        n = G_new.number_of_nodes()
        e = G_new.number_of_edges()
        return GraphDiff(
            added_nodes=sorted(G_new.nodes()),
            diff_summary=f"first build: +{n} nodes, +{e} edges",
            git_sha=_get_git_sha(),
        )

    old_nodes = set(G_old.nodes())
    new_nodes = set(G_new.nodes())

    added   = sorted(new_nodes - old_nodes)
    removed = sorted(old_nodes - new_nodes)
    common  = old_nodes & new_nodes

    # Changed nodes: summary or type differ
    changed: list[str] = []
    for n in common:
        old_d = G_old.nodes[n]
        new_d = G_new.nodes[n]
        if (old_d.get("summary", "") != new_d.get("summary", "")
                or old_d.get("type", "") != new_d.get("type", "")):
            changed.append(n)
    changed.sort()

    # Edge delta — only within nodes present in both builds to avoid noise
    def _edge_set(G: Any) -> set[tuple[str, str, str]]:
        return {
            (u, v, d.get("relation", ""))
            for u, v, d in G.edges(data=True)
        }

    old_edges = _edge_set(G_old)
    new_edges = _edge_set(G_new)
    added_edges   = sorted(new_edges - old_edges)
    removed_edges = sorted(old_edges - new_edges)

    # Build concise summary string
    parts: list[str] = []
    if added:         parts.append(f"+{len(added)} nodes")
    if removed:       parts.append(f"-{len(removed)} nodes")
    if changed:       parts.append(f"~{len(changed)} changed")
    if added_edges:   parts.append(f"+{len(added_edges)} edges")
    if removed_edges: parts.append(f"-{len(removed_edges)} edges")
    summary = ", ".join(parts) if parts else "no changes"

    return GraphDiff(
        added_nodes=added,
        removed_nodes=removed,
        changed_nodes=changed,
        added_edges=[list(e) for e in added_edges],
        removed_edges=[list(e) for e in removed_edges],
        diff_summary=summary,
        git_sha=_get_git_sha(),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Persistence — delta only
# ──────────────────────────────────────────────────────────────────────────────

def save_diff(diff: GraphDiff, out_dir: Path) -> Path:
    """
    Persist delta to last_diff.json (always overwrite — no accumulation).

    Storage cost: O(number of changes), not O(graph size).
    A 10k-node graph with zero changes produces a ~200-byte file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    diff_path = out_dir / "last_diff.json"
    data = {
        "added_nodes":   diff.added_nodes,
        "removed_nodes": diff.removed_nodes,
        "changed_nodes": diff.changed_nodes,
        "added_edges":   diff.added_edges,
        "removed_edges": diff.removed_edges,
        "diff_summary":  diff.diff_summary,
        "timestamp":     diff.timestamp,
        "git_sha":       diff.git_sha,
    }
    diff_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return diff_path


def load_diff(out_dir: Path) -> GraphDiff | None:
    """Load last_diff.json. Returns None if file doesn't exist or is corrupt."""
    diff_path = out_dir / "last_diff.json"
    if not diff_path.exists():
        return None
    try:
        data = json.loads(diff_path.read_text(encoding="utf-8"))
        return GraphDiff(
            added_nodes=data.get("added_nodes", []),
            removed_nodes=data.get("removed_nodes", []),
            changed_nodes=data.get("changed_nodes", []),
            added_edges=data.get("added_edges", []),
            removed_edges=data.get("removed_edges", []),
            diff_summary=data.get("diff_summary", ""),
            timestamp=data.get("timestamp", 0.0),
            git_sha=data.get("git_sha"),
        )
    except Exception:
        return None


def load_previous_graph(out_dir: Path) -> Any | None:
    """
    Load the existing graph.json from out_dir BEFORE it is overwritten.
    Call this just before export_graph() in the pipeline.

    Returns a NetworkX graph, or None if no prior graph exists.
    """
    graph_path = out_dir / "graph.json"
    if not graph_path.exists():
        return None
    try:
        import networkx as nx
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        return nx.node_link_graph(data)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_git_sha(cwd: Path | None = None) -> str | None:
    """Return short git commit SHA, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
            cwd=str(cwd) if cwd else None,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None

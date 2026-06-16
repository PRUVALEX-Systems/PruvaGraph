"""
D2 — Impact Analyzer.

Answers: "What breaks if <symbol> changes?"

Algorithm (zero LLM calls — pure graph traversal):
  1. Resolve node_id → exact match or fuzzy label search
  2. Reverse BFS from node_id: find all nodes that directly or transitively
     depend ON it (callers, importers, inheritors)
  3. Score each affected node with a 4-signal risk formula:
       risk = (hop_proximity × 0.4)
            + (degree_factor   × 0.3)
            + (git_freq_factor × 0.2)
            + (cross_community × 0.1)
  4. Sort by risk descending, return ImpactReport

Usage:
    from pruvagraph.impact_analyzer import analyze_impact
    report = analyze_impact(G, "SessionManager", depth=3)
    print(report.format())               # Rich table
    print(report.format("json"))         # JSON for CI gates
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AffectedNode:
    node_id:    str
    label:      str
    file:       str
    hop:        int           # BFS depth from changed node (1 = direct dependent)
    risk_score: float         # 0.0 – 1.0
    in_degree:  int
    community:  int | None


@dataclass
class ImpactReport:
    """Complete impact analysis for a single changed node."""

    changed_node:       str
    changed_label:      str                    = ""
    affected:           list[AffectedNode]     = field(default_factory=list)
    total_files_at_risk: int                   = 0
    max_risk_score:     float                  = 0.0
    risk_summary:       str                    = ""
    error:              str | None             = None   # set if node not found

    # ── Output formatters ────────────────────────────────────────────────────

    def format(self, fmt: str = "table") -> str:
        if fmt == "json":
            return self._to_json()
        return self._to_table()

    def _to_json(self) -> str:
        return json.dumps({
            "changed_node":       self.changed_node,
            "changed_label":      self.changed_label,
            "affected_count":     len(self.affected),
            "total_files_at_risk": self.total_files_at_risk,
            "max_risk":           round(self.max_risk_score, 3),
            "risk_summary":       self.risk_summary,
            "error":              self.error,
            "affected": [
                {
                    "node_id":    n.node_id,
                    "label":      n.label,
                    "file":       n.file,
                    "hop":        n.hop,
                    "risk":       round(n.risk_score, 3),
                    "in_degree":  n.in_degree,
                    "community":  n.community,
                }
                for n in self.affected[:100]
            ],
        }, indent=2)

    def _to_table(self) -> str:
        if self.error:
            return f"[D2] Impact Analyzer — {self.error}"

        lines = [
            f"[D2] Impact Analysis: '{self.changed_label or self.changed_node}'",
            f"     {self.risk_summary}",
        ]

        if not self.affected:
            lines.append("  ✓ No dependents found — safe to change.")
            return "\n".join(lines)

        # Group by hop distance
        by_hop: dict[int, list[AffectedNode]] = {}
        for n in self.affected:
            by_hop.setdefault(n.hop, []).append(n)

        for hop in sorted(by_hop):
            nodes = by_hop[hop]
            lines.append(f"\n  Hop {hop} — {len(nodes)} node(s):")
            for n in sorted(nodes, key=lambda x: -x.risk_score)[:15]:
                filled = int(n.risk_score * 10)
                bar = "█" * filled + "░" * (10 - filled)
                risk_label = (
                    "HIGH  " if n.risk_score >= 0.7 else
                    "MED   " if n.risk_score >= 0.4 else
                    "low   "
                )
                lines.append(
                    f"    [{bar}] {risk_label} {n.label:<40}  {n.file}"
                )
            if len(nodes) > 15:
                lines.append(f"    ... and {len(nodes) - 15} more")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Main analysis function
# ──────────────────────────────────────────────────────────────────────────────

def analyze_impact(
    G: Any,
    node_id: str,
    depth: int = 3,
    git_intel: dict[str, Any] | None = None,
) -> ImpactReport:
    """
    Find all nodes that depend on `node_id` and score their blast radius.

    Args:
        G:         NetworkX MultiDiGraph (from pruvagraph build).
        node_id:   Node to analyse — exact graph ID or fuzzy label match.
        depth:     BFS depth limit (default 3). Higher = more transitive deps.
        git_intel: Optional dict from git_intel.py with `file_frequencies` key.

    Returns:
        ImpactReport with all affected nodes sorted by risk (high → low).
    """
    # Resolve node (exact → label → partial label)
    target = _resolve_node(G, node_id)
    if target is None:
        return ImpactReport(
            changed_node=node_id,
            error=f"Node '{node_id}' not found in graph. "
                  f"Try an exact node ID or a label substring.",
        )

    target_data    = G.nodes[target]
    target_label   = target_data.get("label", target)
    target_community = target_data.get("community")

    # ── BFS: find all nodes that depend ON target (predecessors / callers) ──
    # Graph edges: A → B means "A imports / calls / uses B"
    # So "who depends on target" = predecessors of target
    visited: dict[str, int] = {}   # node_id → first hop distance reached
    queue: list[tuple[str, int]] = []

    # Seed queue with direct predecessors
    for pred in G.predecessors(target):
        if pred not in visited:
            visited[pred] = 1
            queue.append((pred, 1))

    while queue:
        current, hop = queue.pop(0)
        if hop >= depth:
            continue
        for pred in G.predecessors(current):
            if pred not in visited:
                visited[pred] = hop + 1
                queue.append((pred, hop + 1))

    if not visited:
        return ImpactReport(
            changed_node=target,
            changed_label=target_label,
            risk_summary="No dependents found — safe to change.",
        )

    # ── Risk scoring ─────────────────────────────────────────────────────────
    max_in_degree = max((G.in_degree(n) for n in G.nodes()), default=1) or 1
    git_freqs     = (git_intel or {}).get("file_frequencies", {})
    max_git_freq  = max(git_freqs.values(), default=1) or 1

    affected:       list[AffectedNode] = []
    affected_files: set[str]           = set()

    for nid, hop in visited.items():
        data      = G.nodes[nid]
        label     = data.get("label", nid)
        file      = data.get("file", "")
        in_deg    = G.in_degree(nid)
        community = data.get("community")

        # Signal 1: hop proximity (closer = higher risk)
        hop_factor = 1.0 / hop  # hop 1 → 1.0, hop 2 → 0.5, hop 3 → 0.33

        # Signal 2: in-degree (widely-used nodes = higher blast radius on THEM)
        degree_factor = min(in_deg / max_in_degree, 1.0)

        # Signal 3: git change frequency of the AFFECTED file
        git_factor = git_freqs.get(file, 0) / max_git_freq if git_freqs else 0.0

        # Signal 4: cross-community coupling (architectural risk)
        cross_factor = 0.1 if (
            community is not None
            and target_community is not None
            and community != target_community
        ) else 0.0

        risk = min(
            hop_factor    * 0.4
            + degree_factor * 0.3
            + git_factor    * 0.2
            + cross_factor,
            1.0,
        )

        affected.append(AffectedNode(
            node_id=nid,
            label=label,
            file=file,
            hop=hop,
            risk_score=round(risk, 4),
            in_degree=in_deg,
            community=community,
        ))
        if file:
            affected_files.add(file)

    # Sort: highest risk first, then by hop distance
    affected.sort(key=lambda x: (-x.risk_score, x.hop))

    # ── Summarise ────────────────────────────────────────────────────────────
    high   = sum(1 for n in affected if n.risk_score >= 0.7)
    medium = sum(1 for n in affected if 0.4 <= n.risk_score < 0.7)
    low    = sum(1 for n in affected if n.risk_score < 0.4)

    parts = [f"{len(affected)} nodes / {len(affected_files)} files affected"]
    if high:   parts.append(f"{high} HIGH risk")
    if medium: parts.append(f"{medium} medium")
    if low:    parts.append(f"{low} low")

    return ImpactReport(
        changed_node=target,
        changed_label=target_label,
        affected=affected,
        total_files_at_risk=len(affected_files),
        max_risk_score=affected[0].risk_score if affected else 0.0,
        risk_summary=" — ".join(parts),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Node resolution helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_node(G: Any, node_id: str) -> str | None:
    """
    Resolve node_id to an actual graph node ID via 3-step matching:
      1. Exact graph node ID
      2. Case-insensitive exact label match
      3. Case-insensitive substring label match (first hit)
    """
    # 1. Exact ID
    if node_id in G:
        return node_id

    node_id_lower = node_id.lower()

    # 2. Exact label (case-insensitive)
    for n, data in G.nodes(data=True):
        if data.get("label", "").lower() == node_id_lower:
            return n

    # 3. Substring label
    for n, data in G.nodes(data=True):
        if node_id_lower in data.get("label", "").lower():
            return n

    return None

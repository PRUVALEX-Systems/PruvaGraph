"""
Arch5 — Pre-Injection Mode.

MCP tools only help once Claude decides to call them — every session
starts cold.  Fix: compute a compact (~3,500 token) architecture summary
from the graph and write it into CLAUDE.md, auto-marked, regenerated on
every build.  Claude reads CLAUDE.md at session start automatically —
context arrives free, zero tool calls, zero extra turns.

Mirrors the measured winning strategy in recent MCP research: tool-only
mode adds latency and overhead; pre-injected context eliminates the cold
start.  Do not claim this helps until benchmarked — see BENCHMARK_RESULTS.md.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

MAX_INJECT_TOKENS = 3500
TOP_N_NODES = 25

INJECT_START = "<!-- pruvagraph:preinjection:start -->"
INJECT_END   = "<!-- pruvagraph:preinjection:end -->"


def build_injection_block(
    graph_json_path: Path,
    root: Path | None = None,
) -> str:
    """Return the full injection block string (with start/end markers)."""
    if not graph_json_path.exists():
        return ""

    data = json.loads(graph_json_path.read_text(encoding="utf-8"))
    G = nx.node_link_graph(data)

    if G.number_of_nodes() == 0:
        return ""

    # ── Select nodes ─────────────────────────────────────────────────────────
    # Top N by degree (god-nodes / landmarks)
    sorted_by_degree = sorted(
        G.nodes(data=True),
        key=lambda kv: G.degree(kv[0]),
        reverse=True,
    )
    selected: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    for node_id, attrs in sorted_by_degree[:TOP_N_NODES]:
        if node_id not in seen:
            seen.add(node_id)
            selected.append((node_id, attrs))

    # One representative per community (for architectural coverage)
    communities_seen: set[Any] = set()
    for node_id, attrs in sorted_by_degree:
        cid = attrs.get("community")
        if cid is not None and cid not in communities_seen and node_id not in seen:
            communities_seen.add(cid)
            seen.add(node_id)
            selected.append((node_id, attrs))

    # ── Build the block ───────────────────────────────────────────────────────
    node_count = G.number_of_nodes()
    edge_count = G.number_of_edges()
    community_count = len(
        {d.get("community") for _, d in G.nodes(data=True) if d.get("community") is not None}
    )

    lines: list[str] = [
        INJECT_START,
        "## Auto-Injected Context (PruvaGraph Arch5 — regenerated on every build, do not edit by hand)",
        "",
        (
            f"_Graph: **{node_count:,} nodes · {edge_count:,} edges · "
            f"{community_count} architectural communities**.  "
            f"Top {len(selected)} highest-connectivity nodes + one representative "
            "per community below — loads at session start, no tool call needed._"
        ),
        "",
        "### Landmarks (highest-connectivity nodes)",
        "",
    ]

    budget = MAX_INJECT_TOKENS * 4  # chars ≈ tokens × 4
    used = 0
    for node_id, attrs in selected:
        degree   = G.degree(node_id)
        label    = attrs.get("label", node_id)
        ntype    = attrs.get("type", "node")
        file_    = attrs.get("file", "")
        summary  = attrs.get("summary", "")
        depth    = attrs.get("depth", "")
        risk     = attrs.get("git_risk_score")

        risk_flag = " ⚑ high-risk" if (risk and risk > 0.7) else ""
        depth_tag = f", depth: {depth}" if depth else ""
        file_tag  = f" `{file_}`" if file_ else ""

        line = (
            f"- **{label}**{file_tag} ({ntype}, degree {degree}{depth_tag}{risk_flag})"
            + (f" — {summary}" if summary else "")
        )

        if used + len(line) > budget:
            break
        lines.append(line)
        used += len(line)

    # ── Session Memory (Arch6) injection ─────────────────────────────────────
    if root is not None:
        try:
            from pruvagraph.context_store import format_for_injection
            memory_block = format_for_injection(root)
            if memory_block:
                lines += ["", memory_block]
        except Exception:
            pass

    lines += ["", INJECT_END]
    return "\n".join(lines)


def write_injection(
    claude_md_path: Path,
    graph_json_path: Path,
    root: Path | None = None,
) -> bool:
    """
    Write (or replace) the pre-injection block in *claude_md_path*.

    Returns True if the block was written/updated.
    Returns False if the graph was empty OR if nothing changed (idempotent).

    IMPORTANT — idempotency:
    If the computed block is byte-for-byte identical to what is already in
    CLAUDE.md, we skip the write entirely.  This prevents spurious mtime
    changes that trick file watchers (VS Code, Cursor, Claude Code's context
    reloader) into re-loading CLAUDE.md and burning tokens on an unchanged
    context — the exact problem PruvaGraph was built to prevent.
    """
    block = build_injection_block(graph_json_path, root=root)
    if not block:
        return False

    existing = (
        claude_md_path.read_text(encoding="utf-8")
        if claude_md_path.exists()
        else "# Project Context\n\n"
    )

    if INJECT_START in existing and INJECT_END in existing:
        pre, _, rest = existing.partition(INJECT_START)
        old_block, _, post = rest.partition(INJECT_END)

        # ── Idempotency check — skip write if nothing changed ────────────
        # Reconstruct what we *would* write and compare to what is already
        # on disk.  If identical, touching the file is a no-op (and harmful).
        existing_full_block = INJECT_START + old_block + INJECT_END
        if existing_full_block.strip() == block.strip():
            return False  # already up-to-date, do NOT write

        new_content = pre + block + post
    else:
        new_content = existing.rstrip() + "\n\n" + block + "\n"

    claude_md_path.write_text(new_content, encoding="utf-8")
    return True

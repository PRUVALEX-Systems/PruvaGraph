"""
Gap 2 — Session-level Read Tracker for MCP server.

Problem:
    Claude has no memory of what the MCP server already told it in the same
    session.  If it calls get_summary("AuthService") three times in one
    conversation, each call generates a full response — wasting tokens.

Solution:
    A lightweight in-process store (no disk, lives only while mcp_server.py
    is running) that records which node IDs have been served and on which
    MCP turn.  On repeated calls, the server returns a terse back-reference
    instead of the full detail.

    First call:  get_summary("SessionManager")
                 → full node detail (type, file, summary, community, edges)

    Repeat call: get_summary("SessionManager")
                 → "Already provided on turn 3 of this session.
                    Refer back to that response instead of re-reading files."

Usage in mcp_server.py:
    from pruvagraph.session_tracker import session, already_seen, record_seen

    def _get_summary(node_id, root="."):
        ref = already_seen(node_id, tool="get_summary")
        if ref:
            return ref          # terse back-reference, ~5 tokens vs ~80
        result = _compute_summary(node_id, root)
        record_seen(node_id, tool="get_summary")
        return result
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Session state (module-level singleton — lives for the MCP server process)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _NodeRecord:
    """Metadata about a node that was already returned to Claude."""
    node_id:   str
    tool:      str          # "get_summary" | "get_dependencies" | "find_callers"
    turn:      int          # MCP call counter at the time of first return
    timestamp: float = field(default_factory=time.monotonic)


class SessionTracker:
    """
    In-process session state for one MCP server lifetime.

    Thread-safe for single-threaded asyncio (no locking needed).
    Resets automatically when the MCP process restarts (new Claude session).
    """

    def __init__(self) -> None:
        self._seen:  dict[str, _NodeRecord] = {}   # node_id → record
        self._turn:  int = 0                        # increments on every MCP tool call

    # ─── Public API ───────────────────────────────────────────────────────────

    def tick(self) -> int:
        """Increment the turn counter. Call once per incoming tool request."""
        self._turn += 1
        return self._turn

    def already_seen(
        self,
        node_id: str,
        tool: str = "",
        *,
        min_turns_ago: int = 1,
    ) -> str | None:
        """
        Return a terse back-reference string if *node_id* was already served
        in this session, else None.

        Args:
            node_id:       The node ID or label that was queried.
            tool:          The MCP tool name making the query.
            min_turns_ago: Only treat as duplicate if the first call was at
                           least this many turns ago (default 1 — even the
                           immediately previous turn counts).

        Returns:
            A short string like:
                "Already provided on turn 3 (get_summary). Use that response."
            or None if this is the first time we've seen *node_id*.
        """
        rec = self._seen.get(node_id)
        if rec is None:
            return None
        if (self._turn - rec.turn) < min_turns_ago:
            return None  # too recent to be worth flagging

        tool_hint = rec.tool if rec.tool else "a previous tool call"
        return (
            f"[PruvaGraph] Node '{node_id}' was already returned on "
            f"turn {rec.turn} via {tool_hint} in this session.\n"
            f"Please refer back to that response rather than reading raw files. "
            f"If you need updated info after a rebuild, call the same tool again "
            f"and the tracker will refresh."
        )

    def record_seen(self, node_id: str, tool: str = "") -> None:
        """
        Mark *node_id* as having been returned to Claude this session.
        Subsequent calls to already_seen() for the same node will return
        a back-reference instead of None.
        """
        if node_id not in self._seen:
            self._seen[node_id] = _NodeRecord(
                node_id=node_id,
                tool=tool,
                turn=self._turn,
            )
        # If already recorded: don't overwrite (keep the FIRST occurrence turn)

    def reset(self) -> None:
        """Clear all session state (useful for testing or explicit session reset)."""
        self._seen.clear()
        self._turn = 0

    def stats(self) -> dict[str, Any]:
        """Return current session statistics."""
        return {
            "current_turn": self._turn,
            "nodes_seen":   len(self._seen),
            "seen_list":    [
                {"node_id": r.node_id, "tool": r.tool, "turn": r.turn}
                for r in sorted(self._seen.values(), key=lambda r: r.turn)
            ],
        }


# ──────────────────────────────────────────────────────────────────────────────
# Module-level singleton — import and use directly
# ──────────────────────────────────────────────────────────────────────────────

_session = SessionTracker()


def tick() -> int:
    """Increment global turn counter. Call once per MCP tool invocation."""
    return _session.tick()


def already_seen(node_id: str, tool: str = "") -> str | None:
    """Return back-reference string if node was already served, else None."""
    return _session.already_seen(node_id, tool=tool)


def record_seen(node_id: str, tool: str = "") -> None:
    """Mark node as served in this session."""
    _session.record_seen(node_id, tool=tool)


def reset() -> None:
    """Reset the entire session (for testing)."""
    _session.reset()


def stats() -> dict[str, Any]:
    """Return session statistics dict."""
    return _session.stats()

"""
pruvagraph.budget_governor — Per-session token budget enforcement (Gate 7).

Addresses the "Token Budget Governor" gap from the strategy plan §5 Gate 7:
the `--budget` CLI flag existed but only logged; this wires it to a real
per-session budget with MCP-surfaced status that an agent can query before
spending context budget.

Design decisions:
  - Session state: pruvagraph-out/budget_session.json
    { "session_id": "<uuid4>", "budget_cap": <int> }
  - Spend log: pruvagraph-out/pruvagraph.db → budget_log table
    (same shared DB as task_weaver.py — no separate DB init needed)
  - Token estimation: chars // 4 (consistent with context_lens.py)
  - Thresholds: OK (<80%), WARNING (80–99%), EXCEEDED (≥100%)
  - set_budget() creates a fresh session_id — prior session's spend is ignored
    for the new session (the DB rows still exist for audit purposes)
  - No budget set → record_spend() is a no-op; check_budget() returns a
    "no budget set" message. Never raises.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_FILE_REL: str = "pruvagraph-out/budget_session.json"
_DB_REL: str = "pruvagraph-out/pruvagraph.db"

# Status thresholds
_WARNING_PCT: float = 80.0
_EXCEEDED_PCT: float = 100.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _session_path(root: str | Path) -> Path:
    return Path(root) / SESSION_FILE_REL


def _db_path(root: str | Path) -> Path:
    return Path(root) / _DB_REL


def _ensure_db(root: str | Path) -> sqlite3.Connection:
    """Open the shared DB and create budget_log table if needed."""
    path = _db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS budget_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            tool_name    TEXT NOT NULL,
            tokens_spent INTEGER NOT NULL,
            budget_cap   INTEGER,
            created_at   TEXT NOT NULL
        )
    """)
    con.commit()
    return con


def _load_session(root: str | Path) -> dict | None:
    """Return { session_id, budget_cap } or None if no budget is set."""
    path = _session_path(root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _session_total_spend(con: sqlite3.Connection, session_id: str) -> int:
    """Return total tokens spent in this session."""
    row = con.execute(
        "SELECT SUM(tokens_spent) FROM budget_log WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return row[0] or 0


def _status_label(spent: int, cap: int) -> str:
    pct = (spent / cap * 100) if cap > 0 else 0.0
    if pct >= _EXCEEDED_PCT:
        return "EXCEEDED"
    if pct >= _WARNING_PCT:
        return "WARNING"
    return "OK"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_budget(tokens: int, root: str | Path = ".") -> str:
    """Set the session token budget cap.

    Creates a fresh session — prior spend from any previous session is
    ignored for all subsequent check_budget() and record_spend() calls.
    """
    session_id = str(uuid.uuid4())
    path = _session_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"session_id": session_id, "budget_cap": tokens}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return (
        f"### Budget Governor — Budget Set\n\n"
        f"**Session budget:** {tokens:,} tokens\n"
        f"**Session ID:** `{session_id[:8]}...`\n"
        f"Use `check_budget()` at any time to see remaining budget."
    )


def check_budget(root: str | Path = ".") -> str:
    """Return the current budget status: cap, spent, remaining, % used, status."""
    session = _load_session(root)
    if session is None:
        return (
            "### Budget Governor — No Budget Set\n\n"
            "No token budget is configured for this session.\n"
            "Set one with: `set_budget(tokens=50000)`"
        )

    session_id = session["session_id"]
    cap = session["budget_cap"]

    con = _ensure_db(root)
    spent = _session_total_spend(con, session_id)
    con.close()

    remaining = max(cap - spent, 0)
    pct = (spent / cap * 100) if cap > 0 else 0.0
    status = _status_label(spent, cap)
    status_icon = {"OK": "OK", "WARNING": "WARNING", "EXCEEDED": "EXCEEDED"}[status]

    return (
        f"### Budget Governor — [{status_icon}]\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| **Budget cap** | {cap:,} tokens |\n"
        f"| **Spent** | {spent:,} tokens ({pct:.1f}%) |\n"
        f"| **Remaining** | {remaining:,} tokens |\n"
        f"| **Status** | {status} |\n"
    )


def record_spend(
    tokens: int,
    tool_name: str,
    root: str | Path = ".",
) -> str:
    """Record a token spend against the current session budget.

    Called automatically by mcp_server._dispatch() after every tool call.
    If no budget is set, this is a no-op (returns a neutral message).
    Returns check_budget() summary after recording.
    """
    session = _load_session(root)
    if session is None:
        return "Budget Governor: no budget set — spend not recorded."

    session_id = session["session_id"]
    cap = session["budget_cap"]
    now = datetime.now(timezone.utc).isoformat()

    con = _ensure_db(root)
    con.execute(
        """INSERT INTO budget_log (session_id, tool_name, tokens_spent, budget_cap, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, tool_name, tokens, cap, now),
    )
    con.commit()
    con.close()

    return check_budget(root=root)


def check_budget_json(root: str | Path = ".") -> dict:
    """Return budget status as a plain dict for webview/JSON consumption.

    Keys: session_set (bool), cap, spent, remaining, pct_used, status
    """
    session = _load_session(root)
    if session is None:
        return {
            "session_set": False,
            "cap": 0,
            "spent": 0,
            "remaining": 0,
            "pct_used": 0.0,
            "status": "NO_BUDGET",
        }

    session_id = session["session_id"]
    cap = session["budget_cap"]

    con = _ensure_db(root)
    spent = _session_total_spend(con, session_id)
    con.close()

    remaining = max(cap - spent, 0)
    pct = round((spent / cap * 100) if cap > 0 else 0.0, 1)
    status = _status_label(spent, cap)

    return {
        "session_set": True,
        "cap": cap,
        "spent": spent,
        "remaining": remaining,
        "pct_used": pct,
        "status": status,
    }

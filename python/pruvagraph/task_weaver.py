"""
pruvagraph.task_weaver — SQLite-backed agent checkpoint/recovery system.

Directly addresses the "task fragility" pain point from the gap analysis:
a long agent run that dies halfway can resume from the last checkpoint instead
of restarting and re-paying for context from scratch.

Design decisions:
  - DB: pruvagraph-out/pruvagraph.db (sqlite3 stdlib — zero new dependencies)
  - Table: task_checkpoints — DAG structure (parent_id links checkpoints in order)
  - Git micro-commits: created automatically when inside a git repo (non-blocking
    fallback: git_sha=NULL if git unavailable or repo not initialised)
  - Rollback: advisory — surfaces git SHA + exact command, does NOT run
    `git reset --hard` automatically (destructive, requires explicit user consent)
  - Shared DB file: budget_governor.py writes to the same pruvagraph.db
    (different table) so both modules share one DB init path
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_REL_PATH: str = "pruvagraph-out/pruvagraph.db"


# ---------------------------------------------------------------------------
# Internal: DB initialisation
# ---------------------------------------------------------------------------

def _db_path(root: str | Path) -> Path:
    return Path(root) / DB_REL_PATH


def _get_connection(root: str | Path) -> sqlite3.Connection:
    """Open (and initialise if needed) the shared SQLite DB."""
    path = _db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS task_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            task_id       TEXT NOT NULL,
            parent_id     TEXT,
            description   TEXT NOT NULL,
            files_changed TEXT,
            git_sha       TEXT,
            status        TEXT NOT NULL DEFAULT 'active',
            token_spend   INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        )
    """)
    con.commit()
    return con


# ---------------------------------------------------------------------------
# Internal: git helpers
# ---------------------------------------------------------------------------

def _is_git_repo(root: str | Path) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(root), capture_output=True, text=True,
    )
    return r.returncode == 0


def _git_micro_commit(
    root: str | Path,
    task_id: str,
    checkpoint_id: str,
    files_changed: list[str] | None,
) -> str | None:
    """
    Stage files_changed (or all tracked changes) and create a micro-commit.
    Returns the full 40-char SHA on success, None on any failure.
    Git is the user's tool — we never force-push or hard-reset.
    """
    try:
        root_path = Path(root)
        if not _is_git_repo(root_path):
            return None

        # Stage the specified files, or all changes if none specified
        if files_changed:
            for f in files_changed:
                subprocess.run(
                    ["git", "add", "--", f],
                    cwd=str(root_path), capture_output=True, check=False,
                )
        else:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(root_path), capture_output=True, check=False,
            )

        msg = f"[pruvagraph checkpoint] {task_id}:{checkpoint_id[:8]}"
        r = subprocess.run(
            ["git", "commit", "-m", msg, "--allow-empty"],
            cwd=str(root_path), capture_output=True, text=True,
        )
        if r.returncode != 0:
            return None

        # Retrieve the SHA of the commit we just made
        sha_r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root_path), capture_output=True, text=True,
        )
        if sha_r.returncode != 0:
            return None
        return sha_r.stdout.strip()
    except Exception:
        return None


def _get_latest_checkpoint_id(
    con: sqlite3.Connection,
    task_id: str,
) -> str | None:
    """Return the checkpoint_id of the most recent active checkpoint for task_id."""
    row = con.execute(
        """SELECT checkpoint_id FROM task_checkpoints
           WHERE task_id = ? AND status = 'active'
           ORDER BY created_at DESC LIMIT 1""",
        (task_id,),
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_checkpoint(
    task_id: str,
    description: str,
    files_changed: list[str] | None = None,
    root: str | Path = ".",
) -> str:
    """Create a checkpoint for the current agent step.

    Attempts a git micro-commit; if git is unavailable or this is not a git
    repo, the checkpoint is saved with git_sha=NULL — non-blocking.

    Returns:
        Formatted string with checkpoint_id, parent, and git SHA (if available).
    """
    checkpoint_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    files_json = json.dumps(files_changed) if files_changed else None

    con = _get_connection(root)
    parent_id = _get_latest_checkpoint_id(con, task_id)

    # Attempt git micro-commit (non-blocking)
    git_sha = _git_micro_commit(root, task_id, checkpoint_id, files_changed)

    con.execute(
        """INSERT INTO task_checkpoints
           (checkpoint_id, task_id, parent_id, description,
            files_changed, git_sha, status, token_spend, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?)""",
        (checkpoint_id, task_id, parent_id, description,
         files_json, git_sha, now),
    )
    con.commit()
    con.close()

    lines = [
        f"### TaskWeaver — Checkpoint Created",
        f"",
        f"**Task:** `{task_id}`",
        f"**Checkpoint:** `{checkpoint_id}`",
        f"**Parent:** `{parent_id or 'none (first checkpoint)'}`",
        f"**Description:** {description}",
    ]
    if files_changed:
        lines.append(f"**Files:** {', '.join(files_changed)}")
    if git_sha:
        lines.append(f"**Git SHA:** `{git_sha}`")
    else:
        lines.append(f"**Git SHA:** N/A (not a git repo or no changes to commit)")

    return "\n".join(lines)


def get_task_progress(task_id: str, root: str | Path = ".") -> str:
    """Return a formatted progress summary for a task.

    Shows: checkpoint count, cumulative token spend, per-step description and status.
    """
    con = _get_connection(root)
    rows = con.execute(
        """SELECT checkpoint_id, description, status, files_changed,
                  git_sha, token_spend, created_at
           FROM task_checkpoints
           WHERE task_id = ?
           ORDER BY created_at""",
        (task_id,),
    ).fetchall()
    con.close()

    if not rows:
        return (
            f"### TaskWeaver — Task Progress\n\n"
            f"No checkpoints found for task `{task_id}`.\n"
            f"Create one with: `create_checkpoint(task_id=\"{task_id}\", description=\"...\")`"
        )

    total_tokens = sum(r[5] for r in rows)
    active = sum(1 for r in rows if r[2] == "active")
    rolled_back = sum(1 for r in rows if r[2] == "rolled_back")

    lines = [
        f"### TaskWeaver — Task `{task_id}`",
        f"",
        f"**{len(rows)} checkpoint{'s' if len(rows) != 1 else ''}** · "
        f"{active} active · {rolled_back} rolled back · ~{total_tokens:,} tokens spent",
        f"",
        f"| # | Description | Status | Git SHA | Tokens |",
        f"|---|-------------|--------|---------|--------|",
    ]
    for i, (cid, desc, status, files, sha, tokens, ts) in enumerate(rows, 1):
        sha_short = sha[:8] if sha else "-"
        status_icon = "+" if status == "active" else "~"
        lines.append(
            f"| {i} | {desc[:40]} | {status_icon} {status} | `{sha_short}` | {tokens:,} |"
        )

    return "\n".join(lines)


def rollback_to_checkpoint(checkpoint_id: str, root: str | Path = ".") -> str:
    """Mark a checkpoint (and all subsequent ones in the same task) as rolled_back.

    Returns the git SHA at that checkpoint and the exact git command to restore
    to that state. Does NOT execute the git command — that is a destructive action
    requiring explicit user consent.
    """
    con = _get_connection(root)
    row = con.execute(
        """SELECT task_id, description, git_sha, created_at
           FROM task_checkpoints
           WHERE checkpoint_id = ?""",
        (checkpoint_id,),
    ).fetchone()

    if not row:
        con.close()
        return (
            f"### TaskWeaver — Rollback Failed\n\n"
            f"Checkpoint `{checkpoint_id}` not found.\n"
            f"Use `list_checkpoints()` to see available checkpoints."
        )

    task_id, description, git_sha, created_at = row

    # Mark this checkpoint and all checkpoints created after it for the same task
    con.execute(
        """UPDATE task_checkpoints
           SET status = 'rolled_back'
           WHERE task_id = ? AND created_at >= ?""",
        (task_id, created_at),
    )
    con.commit()
    con.close()

    lines = [
        f"### TaskWeaver — Rolled Back",
        f"",
        f"**Task:** `{task_id}`",
        f"**Rolled back to:** `{checkpoint_id[:8]}` — {description}",
    ]
    if git_sha:
        lines += [
            f"**Git SHA at checkpoint:** `{git_sha}`",
            f"",
            f"To restore the working tree to this exact state, run:",
            f"```",
            f"git checkout {git_sha}",
            f"```",
            f"⚠ This will detach HEAD. To reset the current branch instead:",
            f"```",
            f"git reset --hard {git_sha}",
            f"```",
            f"**Review the diff before running either command.**",
        ]
    else:
        lines += [
            f"",
            f"No git SHA recorded at this checkpoint (not a git repo at time of creation).",
            f"Restore files manually from your backup or version control.",
        ]

    return "\n".join(lines)


def list_checkpoints(
    task_id: str | None = None,
    root: str | Path = ".",
) -> str:
    """List all checkpoints, optionally filtered by task_id."""
    con = _get_connection(root)
    if task_id:
        rows = con.execute(
            """SELECT checkpoint_id, task_id, description, status, git_sha, created_at
               FROM task_checkpoints
               WHERE task_id = ?
               ORDER BY created_at""",
            (task_id,),
        ).fetchall()
    else:
        rows = con.execute(
            """SELECT checkpoint_id, task_id, description, status, git_sha, created_at
               FROM task_checkpoints
               ORDER BY created_at""",
        ).fetchall()
    con.close()

    if not rows:
        scope = f"task `{task_id}`" if task_id else "any task"
        return (
            f"### TaskWeaver — Checkpoints\n\n"
            f"No checkpoints found for {scope}."
        )

    header = f"### TaskWeaver — Checkpoints"
    if task_id:
        header += f" for `{task_id}`"

    lines = [
        header,
        f"",
        f"| # | Task | Checkpoint | Description | Status | SHA |",
        f"|---|------|------------|-------------|--------|-----|",
    ]
    for i, (cid, tid, desc, status, sha, ts) in enumerate(rows, 1):
        sha_short = sha[:8] if sha else "-"
        status_icon = "+" if status == "active" else "~"
        lines.append(
            f"| {i} | `{tid}` | `{cid[:8]}` | {desc[:35]} | {status_icon} {status} | `{sha_short}` |"
        )

    return "\n".join(lines)


def list_checkpoints_json(
    task_id: str | None = None,
    root: str | Path = ".",
) -> list[dict]:
    """Return all checkpoints as a list of dicts for webview/JSON consumption.

    Each dict: checkpoint_id, task_id, description, status, git_sha, created_at
    Optionally filtered by task_id.
    """
    con = _get_connection(root)
    if task_id:
        rows = con.execute(
            """SELECT checkpoint_id, task_id, description, status, git_sha, created_at
               FROM task_checkpoints
               WHERE task_id = ?
               ORDER BY created_at""",
            (task_id,),
        ).fetchall()
    else:
        rows = con.execute(
            """SELECT checkpoint_id, task_id, description, status, git_sha, created_at
               FROM task_checkpoints
               ORDER BY created_at""",
        ).fetchall()
    con.close()

    return [
        {
            "checkpoint_id": row[0],
            "task_id": row[1],
            "description": row[2],
            "status": row[3],
            "git_sha": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]

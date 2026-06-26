"""
Tests for pruvagraph.task_weaver — SQLite-backed agent checkpoint/recovery system.

Design:
  - DB: pruvagraph-out/pruvagraph.db (sqlite3 stdlib, no new dependency)
  - Table: task_checkpoints (checkpoint_id, task_id, parent_id, description,
           files_changed, git_sha, status, token_spend, created_at)
  - Git integration: optional — creates a micro-commit when inside a git repo.
    If no git repo, checkpoint is saved with git_sha=NULL (non-blocking).
  - Rollback: advisory — surfaces git SHA + recommended command, does NOT run
    `git reset --hard` automatically (destructive action requires user consent).
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from pruvagraph.task_weaver import (
    DB_REL_PATH,
    create_checkpoint,
    get_task_progress,
    list_checkpoints,
    rollback_to_checkpoint,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_path(root: Path) -> Path:
    return root / DB_REL_PATH


def _row_count(root: Path, table: str = "task_checkpoints") -> int:
    con = sqlite3.connect(_db_path(root))
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    con.close()
    return n


def _init_git_repo(path: Path) -> None:
    """Initialize a bare git repo in path with one commit so HEAD exists."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"],
                   cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=str(path), check=True, capture_output=True)
    # Create an initial commit so HEAD is valid
    dummy = path / "README.md"
    dummy.write_text("# Test repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(path),
                   check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"],
                   cwd=str(path), check=True, capture_output=True)


# ===========================================================================
# 1. DB initialisation
# ===========================================================================

class TestInitDB:
    def test_db_created_on_first_checkpoint(self, tmp_path):
        assert not _db_path(tmp_path).exists()
        create_checkpoint("task1", "first step", root=str(tmp_path))
        assert _db_path(tmp_path).exists()

    def test_db_creation_is_idempotent(self, tmp_path):
        create_checkpoint("task1", "step 1", root=str(tmp_path))
        create_checkpoint("task1", "step 2", root=str(tmp_path))
        # No exception — table CREATE IF NOT EXISTS
        assert _row_count(tmp_path) == 2

    def test_creates_out_dir_if_missing(self, tmp_path):
        create_checkpoint("t", "d", root=str(tmp_path))
        assert (tmp_path / "pruvagraph-out").is_dir()


# ===========================================================================
# 2. create_checkpoint
# ===========================================================================

class TestCreateCheckpoint:
    def test_returns_non_empty_string(self, tmp_path):
        result = create_checkpoint("task1", "implemented login", root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0

    def test_result_contains_checkpoint_id(self, tmp_path):
        result = create_checkpoint("task1", "step A", root=str(tmp_path))
        # Should mention checkpoint_id in some form
        assert "checkpoint" in result.lower() or "-" in result

    def test_writes_one_row_to_db(self, tmp_path):
        create_checkpoint("task1", "step A", root=str(tmp_path))
        assert _row_count(tmp_path) == 1

    def test_files_changed_stored_as_json(self, tmp_path):
        files = ["src/auth.py", "src/models.py"]
        create_checkpoint("task1", "wired auth", files_changed=files, root=str(tmp_path))
        con = sqlite3.connect(_db_path(tmp_path))
        row = con.execute("SELECT files_changed FROM task_checkpoints").fetchone()
        con.close()
        stored = json.loads(row[0])
        assert stored == files

    def test_git_sha_null_when_not_git_repo(self, tmp_path):
        """In a non-git directory, git_sha must be NULL — must not crash."""
        create_checkpoint("task1", "step", root=str(tmp_path))
        con = sqlite3.connect(_db_path(tmp_path))
        row = con.execute("SELECT git_sha FROM task_checkpoints").fetchone()
        con.close()
        assert row[0] is None

    def test_git_sha_populated_in_git_repo(self, tmp_path):
        """In a real git repo, a micro-commit is created and SHA stored."""
        _init_git_repo(tmp_path)
        # Create a file to give git something to commit
        (tmp_path / "feature.py").write_text("def main(): pass\n")
        result = create_checkpoint(
            "task1", "added feature",
            files_changed=["feature.py"],
            root=str(tmp_path),
        )
        con = sqlite3.connect(_db_path(tmp_path))
        row = con.execute("SELECT git_sha FROM task_checkpoints").fetchone()
        con.close()
        # git_sha should be a 40-char hex string
        sha = row[0]
        assert sha is not None and len(sha) == 40

    def test_parent_id_linked_on_second_checkpoint(self, tmp_path):
        """Second checkpoint for the same task should reference the first."""
        create_checkpoint("task1", "step 1", root=str(tmp_path))
        create_checkpoint("task1", "step 2", root=str(tmp_path))
        con = sqlite3.connect(_db_path(tmp_path))
        rows = con.execute(
            "SELECT checkpoint_id, parent_id FROM task_checkpoints ORDER BY created_at"
        ).fetchall()
        con.close()
        first_id, first_parent = rows[0]
        second_id, second_parent = rows[1]
        assert first_parent is None
        assert second_parent == first_id

    def test_status_defaults_to_active(self, tmp_path):
        create_checkpoint("task1", "step", root=str(tmp_path))
        con = sqlite3.connect(_db_path(tmp_path))
        row = con.execute("SELECT status FROM task_checkpoints").fetchone()
        con.close()
        assert row[0] == "active"


# ===========================================================================
# 3. get_task_progress
# ===========================================================================

class TestGetTaskProgress:
    def test_empty_task_returns_helpful_string(self, tmp_path):
        result = get_task_progress("no-such-task", root=str(tmp_path))
        assert isinstance(result, str) and len(result) > 0
        assert "no" in result.lower() or "0" in result or "empty" in result.lower()

    def test_with_one_checkpoint_contains_description(self, tmp_path):
        create_checkpoint("task1", "wired auth endpoint", root=str(tmp_path))
        result = get_task_progress("task1", root=str(tmp_path))
        assert "wired auth endpoint" in result or "task1" in result

    def test_with_multiple_checkpoints_shows_count(self, tmp_path):
        for i in range(3):
            create_checkpoint("task1", f"step {i}", root=str(tmp_path))
        result = get_task_progress("task1", root=str(tmp_path))
        assert "3" in result

    def test_returns_string_always(self, tmp_path):
        assert isinstance(get_task_progress("x", root=str(tmp_path)), str)


# ===========================================================================
# 4. rollback_to_checkpoint
# ===========================================================================

class TestRollbackToCheckpoint:
    def test_invalid_id_returns_error(self, tmp_path):
        result = rollback_to_checkpoint("nonexistent-id", root=str(tmp_path))
        assert isinstance(result, str)
        assert "not found" in result.lower() or "error" in result.lower() or "no" in result.lower()

    def test_marks_checkpoint_rolled_back(self, tmp_path):
        create_checkpoint("task1", "step 1", root=str(tmp_path))
        create_checkpoint("task1", "step 2", root=str(tmp_path))
        con = sqlite3.connect(_db_path(tmp_path))
        first_id = con.execute(
            "SELECT checkpoint_id FROM task_checkpoints ORDER BY created_at LIMIT 1"
        ).fetchone()[0]
        con.close()
        rollback_to_checkpoint(first_id, root=str(tmp_path))
        con = sqlite3.connect(_db_path(tmp_path))
        statuses = [r[0] for r in con.execute("SELECT status FROM task_checkpoints ORDER BY created_at").fetchall()]
        con.close()
        # First checkpoint should be rolled_back, and subsequent ones too
        assert "rolled_back" in statuses

    def test_result_contains_git_command_hint(self, tmp_path):
        create_checkpoint("task1", "step 1", root=str(tmp_path))
        con = sqlite3.connect(_db_path(tmp_path))
        cid = con.execute("SELECT checkpoint_id FROM task_checkpoints").fetchone()[0]
        con.close()
        result = rollback_to_checkpoint(cid, root=str(tmp_path))
        # Should mention git or the checkpoint id
        assert "git" in result.lower() or cid[:8] in result or "rolled back" in result.lower()


# ===========================================================================
# 5. list_checkpoints
# ===========================================================================

class TestListCheckpoints:
    def test_empty_db(self, tmp_path):
        result = list_checkpoints(root=str(tmp_path))
        assert isinstance(result, str)
        assert "no" in result.lower() or "0" in result or "empty" in result.lower()

    def test_lists_all_when_no_task_filter(self, tmp_path):
        create_checkpoint("task1", "step A", root=str(tmp_path))
        create_checkpoint("task2", "step B", root=str(tmp_path))
        result = list_checkpoints(root=str(tmp_path))
        assert "task1" in result and "task2" in result

    def test_filters_by_task_id(self, tmp_path):
        create_checkpoint("task1", "step A", root=str(tmp_path))
        create_checkpoint("task2", "step B", root=str(tmp_path))
        result = list_checkpoints(task_id="task1", root=str(tmp_path))
        assert "task1" in result
        assert "task2" not in result

    def test_multiple_tasks_separated(self, tmp_path):
        for i in range(3):
            create_checkpoint("alpha", f"alpha step {i}", root=str(tmp_path))
        for i in range(2):
            create_checkpoint("beta", f"beta step {i}", root=str(tmp_path))
        alpha_result = list_checkpoints(task_id="alpha", root=str(tmp_path))
        beta_result = list_checkpoints(task_id="beta", root=str(tmp_path))
        assert "alpha step" in alpha_result
        assert "beta step" not in alpha_result
        assert "beta step" in beta_result
        assert "alpha step" not in beta_result

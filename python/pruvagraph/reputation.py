"""
Arch2 — Reputation Cache (Negative Cache + Learning System)

Tracks which files and patterns produce low-value extractions over time.
System learns across runs → progressively fewer wasted calls.

Phase 1 (this file): local reputation per repo.
Phase 2 (future):    global reputation shared across all PruvaGraph users.

How it works:
  After each build, score each file's extraction quality:
    - "score" = unique_nodes + 2 × unique_edges  (information density)
    - Low score files → reputation marked as "low_value"
    - Pattern detected (e.g., all *-generated.ts = low value) → pattern added

  Next build:
    - Low-value files checked against reputation → skip entirely
    - Saves tokens proportional to how many low-value files exist

Estimated savings: 10–30% over 3+ runs as system learns junk files.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

# ── Default skip patterns (applies before any learning) ───────────────────────

DEFAULT_SKIP_PATTERNS: list[str] = [
    r".*\.(min|bundle|chunk)\.(js|css)$",   # Minified assets
    r".*/generated/.*",                       # Generated directories
    r".*/\.next/.*",                          # Next.js build output
    r".*/__pycache__/.*",                     # Python bytecode dirs
    r".*/dist/.*\.(js|d\.ts)$",              # Built TypeScript/JS
    r".*\.pb\.go$",                           # Generated protobuf Go
    r".*_pb2\.py$",                           # Generated protobuf Python
    r".*\.generated\.\w+$",                  # .generated.* files
    r".*/migrations/\d+.*",                  # Database migrations
    r".*package-lock\.json$",                # npm lock file
    r".*yarn\.lock$",                         # Yarn lock file
    r".*poetry\.lock$",                       # Poetry lock file
    r".*Cargo\.lock$",                        # Rust lock file
    r".*composer\.lock$",                     # PHP Composer lock
    r".*Pipfile\.lock$",                      # Pipenv lock file
]

# ── Low-value extraction score threshold ──────────────────────────────────────

LOW_VALUE_THRESHOLD = 2   # Files with ≤2 info points → low value
MAX_REPUTATION_AGE_DAYS = 30  # Discard old reputation entries


class ReputationCache:
    """
    Persistent reputation store for extraction quality learning.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._path = cache_dir / "reputation.json"
        self._data: dict = self._load()
        self._compiled_patterns: list[re.Pattern] = []
        self._compile_patterns()

    # ── Public API ─────────────────────────────────────────────────────────────

    def should_skip(self, path: Path) -> tuple[bool, str]:
        """
        Return (should_skip, reason) for a file.

        Checks in order:
          1. Default skip patterns (hardcoded)
          2. Learned always-skip patterns
          3. Low-value file reputation
        """
        path_str = str(path).replace("\\", "/")

        # 1. Default patterns
        for pattern in self._compiled_patterns:
            if pattern.match(path_str):
                return True, f"default_pattern:{pattern.pattern[:40]}"

        # 2. Learned always-skip patterns
        for pat in self._data.get("always_skip_patterns", []):
            if re.match(pat, path_str):
                return True, f"learned_pattern:{pat[:40]}"

        # 3. Low-value file history
        file_rep = self._data.get("files", {}).get(path_str)
        if file_rep:
            score     = file_rep.get("avg_score", 10)
            runs      = file_rep.get("runs", 0)
            last_seen = file_rep.get("last_seen", "")

            # Need at least 2 runs before trusting reputation
            if runs >= 2 and score <= LOW_VALUE_THRESHOLD:
                # Check age
                if self._is_fresh(last_seen):
                    return True, f"low_value:{score:.1f}_avg_over_{runs}_runs"

        return False, ""

    def record_extraction(
        self,
        path: Path,
        nodes: list[dict],
        edges: list[dict],
    ) -> None:
        """
        Record extraction quality for a file after a run.
        Updates the file's reputation score.
        """
        path_str = str(path).replace("\\", "/")

        # Information density score
        unique_node_labels = len({n.get("label", "") for n in nodes})
        meaningful_nodes   = sum(
            1 for n in nodes
            if n.get("summary") and len(n.get("summary", "")) > 20
        )
        score = unique_node_labels + 2 * len(edges) + meaningful_nodes

        existing = self._data.setdefault("files", {}).setdefault(path_str, {
            "runs": 0, "avg_score": 0.0, "last_seen": "",
        })

        # Rolling average
        runs           = existing["runs"] + 1
        old_avg        = existing["avg_score"]
        new_avg        = (old_avg * (runs - 1) + score) / runs

        existing["runs"]      = runs
        existing["avg_score"] = round(new_avg, 2)
        existing["last_seen"] = time.strftime("%Y-%m")

        self._save()

    def learn_pattern(self, pattern: str, reason: str = "") -> None:
        """
        Add a learned skip pattern.
        Called when multiple files matching a pattern are all low-value.
        """
        patterns = self._data.setdefault("always_skip_patterns", [])
        if pattern not in patterns:
            patterns.append(pattern)
            self._data.setdefault("pattern_reasons", {})[pattern] = reason
            self._compile_patterns()
            self._save()

    def auto_learn_patterns(self) -> list[str]:
        """
        Analyse reputation data to automatically discover skip patterns.
        Returns list of newly learned patterns.
        """
        files    = self._data.get("files", {})
        new_pats: list[str] = []

        # Group low-value files by directory
        low_dirs: dict[str, int] = {}
        for path_str, rep in files.items():
            if rep.get("runs", 0) >= 2 and rep.get("avg_score", 10) <= LOW_VALUE_THRESHOLD:
                parent = "/".join(path_str.split("/")[:-1])
                low_dirs[parent] = low_dirs.get(parent, 0) + 1

        # If ≥ 3 low-value files in same directory → learn pattern
        for directory, count in low_dirs.items():
            if count >= 3:
                pattern = f"{re.escape(directory)}/.*"
                if pattern not in self._data.get("always_skip_patterns", []):
                    self.learn_pattern(pattern, f"auto: {count} low-value files in dir")
                    new_pats.append(pattern)

        # Group by file extension
        low_exts: dict[str, int] = {}
        for path_str, rep in files.items():
            if rep.get("runs", 0) >= 3 and rep.get("avg_score", 10) <= LOW_VALUE_THRESHOLD:
                ext = path_str.rsplit(".", 1)[-1] if "." in path_str else ""
                if ext:
                    low_exts[ext] = low_exts.get(ext, 0) + 1

        for ext, count in low_exts.items():
            if count >= 5:  # 5+ files of same extension all low-value
                pattern = f".*\\.{re.escape(ext)}$"
                if pattern not in self._data.get("always_skip_patterns", []):
                    self.learn_pattern(pattern, f"auto: {count} low-value .{ext} files")
                    new_pats.append(pattern)

        return new_pats

    def get_stats(self) -> dict:
        """Return reputation cache statistics."""
        files   = self._data.get("files", {})
        n_low   = sum(1 for r in files.values() if r.get("avg_score", 10) <= LOW_VALUE_THRESHOLD)
        n_pats  = len(self._data.get("always_skip_patterns", []))
        return {
            "total_files_tracked": len(files),
            "low_value_files":     n_low,
            "learned_patterns":    n_pats,
            "default_patterns":    len(DEFAULT_SKIP_PATTERNS),
        }

    def purge_old_entries(self) -> int:
        """Remove entries not seen in MAX_REPUTATION_AGE_DAYS. Returns count removed."""
        files = self._data.get("files", {})
        cutoff_month = time.strftime(
            "%Y-%m",
            time.localtime(time.time() - MAX_REPUTATION_AGE_DAYS * 86400),
        )
        to_remove = [
            k for k, v in files.items()
            if v.get("last_seen", "") < cutoff_month
        ]
        for k in to_remove:
            del files[k]
        if to_remove:
            self._save()
        return len(to_remove)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"files": {}, "always_skip_patterns": [], "pattern_reasons": {}}

    def _compile_patterns(self) -> None:
        """Compile all patterns to regex objects."""
        all_pats = DEFAULT_SKIP_PATTERNS + self._data.get("always_skip_patterns", [])
        compiled = []
        for pat in all_pats:
            try:
                compiled.append(re.compile(pat, re.I))
            except re.error:
                pass
        self._compiled_patterns = compiled

    @staticmethod
    def _is_fresh(month_str: str) -> bool:
        """Return True if last_seen month is within MAX_REPUTATION_AGE_DAYS."""
        if not month_str:
            return False
        cutoff = time.strftime(
            "%Y-%m",
            time.localtime(time.time() - MAX_REPUTATION_AGE_DAYS * 86400),
        )
        return month_str >= cutoff

"""
3-layer cache — the primary LLM cost reducer in PruvaGraph.

Layer 1 (stat): size + mtime_ns check — O(1), no file read needed.
                Same as make(1). Touch causes a harmless extra hash.
Layer 2 (hash): SHA-256 content fingerprint — skips unchanged files.
Layer 3 (ast):  AST structure hash — catches formatting-only changes
                that produce identical semantics (whitespace, renames).
                Code files only. Falls back to content hash for docs.

Cost impact: on a 10,000-file repo with 8 files changed per commit,
cache hit rate is ~99.92%. 9,992 files → 0 LLM calls. 8 files → extraction.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_OUT_DIR = os.environ.get("PRUVAGRAPH_OUT", "pruvagraph-out")


@dataclass
class CacheEntry:
    """Stored result for a single file."""
    path: str
    stat_size: int
    stat_mtime_ns: int
    content_hash: str       # SHA-256 of raw bytes
    ast_hash: str | None    # SHA-256 of normalised AST (code files only)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    extraction_cost_usd: float = 0.0
    backend: str = "none"   # "tree-sitter" | "claude" | "gemini" | "ollama" | etc.
    pruvagraph_version: str = "1.0.0"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CacheEntry":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GraphCache:
    """
    Persistent extraction cache backed by two JSON files:
      - stat-index.json   → size + mtime_ns per path (fast stat check)
      - semantic/{hash}.json → full CacheEntry per content-hash

    Thread-safe for reads; writes flushed atomically via tempfile+rename.
    """

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._out = self._root / _OUT_DIR / "cache"
        self._out.mkdir(parents=True, exist_ok=True)

        self._stat_index: dict[str, dict[str, int | str]] = {}
        self._stat_dirty = False
        self._load_stat_index()
        atexit.register(self.flush)

    # ──────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────

    def check(self, path: Path) -> CacheEntry | None:
        """
        Return cached CacheEntry if the file is unchanged, else None.

        Fast path (no file read):
          1. stat() the file.
          2. If size + mtime_ns match the stat-index → load by stored hash.
          3. If match found → return immediately.

        Slow path (file read):
          4. Compute SHA-256 of content.
          5. Look up by content hash.
          6. Update stat-index.
        """
        abs_path = str(path.resolve())
        try:
            st = path.stat()
        except OSError:
            return None

        # ── fast path ──
        idx = self._stat_index.get(abs_path)
        if idx and idx["size"] == st.st_size and idx["mtime_ns"] == st.st_mtime_ns:
            entry = self._load_by_hash(str(idx["hash"]))
            if entry:
                return entry

        # ── slow path: compute hash ──
        try:
            content = path.read_bytes()
        except OSError:
            return None

        content_hash = _sha256(content)
        entry = self._load_by_hash(content_hash)

        # Update stat-index so next call uses the fast path
        self._stat_index[abs_path] = {
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "hash": content_hash,
        }
        self._stat_dirty = True

        return entry

    def save(self, path: Path, entry: CacheEntry) -> None:
        """Persist a new CacheEntry for *path*."""
        abs_path = str(path.resolve())

        # Write semantic entry keyed by content hash
        cache_file = self._out / "semantic" / f"{entry.content_hash}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(cache_file, json.dumps(entry.to_dict(), indent=2).encode())

        # Update stat-index
        try:
            st = path.stat()
            self._stat_index[abs_path] = {
                "size": st.st_size,
                "mtime_ns": st.st_mtime_ns,
                "hash": entry.content_hash,
            }
            self._stat_dirty = True
        except OSError:
            pass

    def flush(self) -> None:
        """Flush stat-index to disk (called automatically at exit)."""
        if not self._stat_dirty:
            return
        p = self._out / "stat-index.json"
        _atomic_write(p, json.dumps(self._stat_index, separators=(",", ":")).encode())
        self._stat_dirty = False

    def invalidate(self, path: Path) -> None:
        """Remove a path from the stat-index (does NOT delete semantic entry)."""
        abs_path = str(path.resolve())
        self._stat_index.pop(abs_path, None)
        self._stat_dirty = True

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        semantic_dir = self._out / "semantic"
        n_entries = len(list(semantic_dir.glob("*.json"))) if semantic_dir.exists() else 0
        return {
            "stat_index_entries": len(self._stat_index),
            "semantic_entries": n_entries,
        }

    # ──────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────

    def _load_stat_index(self) -> None:
        p = self._out / "stat-index.json"
        if p.exists():
            try:
                self._stat_index = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._stat_index = {}

    def _load_by_hash(self, content_hash: str) -> CacheEntry | None:
        cache_file = self._out / "semantic" / f"{content_hash}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return CacheEntry.from_dict(data)
        except (json.JSONDecodeError, OSError, TypeError, KeyError):
            return None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    """Write *data* to *path* atomically via tempfile+rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def compute_ast_hash(path: Path) -> str | None:
    """
    Compute a normalised AST hash for a code file.
    Returns None if tree-sitter grammar isn't available for this extension.

    The hash is over the AST node type sequence — not the raw text —
    so reformatting produces the same hash while actual logic changes
    produce a different one.
    """
    try:
        from pruvagraph.extract.treesitter import ast_fingerprint, get_parser
        parser = get_parser(path.suffix)
        if parser is None:
            return None
        content = path.read_bytes()
        fingerprint = ast_fingerprint(parser, content)
        return hashlib.sha256(fingerprint.encode()).hexdigest()
    except Exception:
        return None

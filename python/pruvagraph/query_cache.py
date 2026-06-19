"""
N6 — Semantic Query Cache

Caches LLM query answers with exact + fuzzy (Jaccard) matching.
Identical or near-identical questions get instant cached replies.

Estimated savings: 30–60% of repeat query LLM calls eliminated.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path


class QueryCache:
    """
    Two-level cache:
      1. Exact match  — MD5 hash of normalized question
      2. Fuzzy match  — Jaccard similarity >= threshold
    """

    def __init__(self, cache_dir: Path, similarity_threshold: float = 0.80):
        self._path      = cache_dir / "query_cache.json"
        self._threshold = similarity_threshold
        self._cache: dict[str, dict] = self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def get(self, question: str) -> str | None:
        """Return cached answer or None if not found."""
        # 1. Exact match
        key = self._hash(question)
        if key in self._cache:
            entry = self._cache[key]
            entry["hits"] = entry.get("hits", 0) + 1
            self._save()
            return entry["answer"]

        # 2. Fuzzy match — use Jaccard similarity over normalized token sets.
        q_tokens = set(self._tokenise(question))
        best_score = 0.0
        best_entry = None

        for entry in self._cache.values():
            cached_tokens = set(self._tokenise(entry.get("question", "")))
            score = self._jaccard(q_tokens, cached_tokens)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= self._threshold and best_entry is not None:
            best_entry["hits"] = best_entry.get("hits", 0) + 1
            self._save()
            return best_entry.get("answer")

        return None

    def save(self, question: str, answer: str) -> None:
        """Store a question → answer pair."""
        key = self._hash(question)
        self._cache[key] = {
            "question":   question,
            "answer":     answer,
            "saved_at":   time.time(),
            "hits":       0,
        }
        self._save()

    def clear(self) -> int:
        """Clear all cached entries. Returns number cleared."""
        count = len(self._cache)
        self._cache = {}
        self._save()
        return count

    def stats(self) -> dict:
        total_hits = sum(e.get("hits", 0) for e in self._cache.values())
        return {
            "cached_questions": len(self._cache),
            "total_cache_hits": total_hits,
            "cache_file":       str(self._path),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.md5(text.lower().strip().encode()).hexdigest()[:12]

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

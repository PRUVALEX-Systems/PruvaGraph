"""
Semantic MinHash deduplication — Layer 2 of PruvaGraph's cost reduction.

Problem: A repo with 40 similar React components (e.g. UserCard, ProductCard,
OrderCard) sends 40 separate LLM calls. They're structurally near-identical.
PruvaGraph detects this and extracts ONE representative per group,
then projects the result back to all similar files.

Algorithm:
  1. Compute MinHash signature for each file (shingle set over tokens).
  2. Use LSH (Locality-Sensitive Hashing) to find near-duplicate pairs fast.
  3. Build connected components — each component is a "dedup group".
  4. For each group: extract ONE file (representative), copy result to others.

Jaccard threshold: 0.82 by default (tunable via --dedup-threshold).
MinHash parameters: 128 hash functions, 4-gram shingles.

Cost impact example:
  40 React components, avg 200 tokens each → 40 LLM calls
  After dedup (Jaccard 0.82): 3 representatives → 3 LLM calls
  Savings: 92.5% of those 40 calls eliminated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from datasketch import MinHash, MinHashLSH
    _DATASKETCH_AVAILABLE = True
except ImportError:
    _DATASKETCH_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DedupGroup:
    """A group of semantically similar files."""
    representative: Path          # The one file we'll actually send to LLM
    duplicates: list[Path]        # Files we'll map results back to
    similarity: float             # Avg Jaccard similarity within group

    @property
    def all_paths(self) -> list[Path]:
        return [self.representative] + self.duplicates

    def __len__(self) -> int:
        return 1 + len(self.duplicates)


@dataclass
class DedupResult:
    """Result of running dedup over a file list."""
    groups: list[DedupGroup]
    singletons: list[Path]        # Files that had no near-duplicates

    @property
    def representatives(self) -> list[Path]:
        """Files that need LLM extraction."""
        return [g.representative for g in self.groups] + self.singletons

    @property
    def total_files(self) -> int:
        return sum(len(g) for g in self.groups) + len(self.singletons)

    @property
    def llm_calls_needed(self) -> int:
        return len(self.representatives)

    @property
    def calls_saved(self) -> int:
        return self.total_files - self.llm_calls_needed

    @property
    def savings_pct(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.calls_saved / self.total_files * 100


def deduplicate(
    paths: list[Path],
    threshold: float = 0.82,
    num_perm: int = 128,
    ngram: int = 4,
) -> DedupResult:
    """
    Group *paths* by semantic similarity.

    Args:
        paths:      Files to deduplicate.
        threshold:  Jaccard similarity cutoff (0–1). Higher = stricter grouping.
        num_perm:   MinHash permutations. More = more accurate, slower.
        ngram:      Token n-gram size for shingle computation.

    Returns:
        DedupResult with groups (representative + duplicates) and singletons.

    Falls back to no-dedup (all singletons) if datasketch is not installed.
    """
    if not _DATASKETCH_AVAILABLE or len(paths) < 2:
        return DedupResult(groups=[], singletons=list(paths))

    # Compute MinHash per file
    minhashes: dict[int, MinHash] = {}
    contents: dict[int, str] = {}

    for i, path in enumerate(paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        contents[i] = text
        minhashes[i] = _minhash(text, num_perm=num_perm, ngram=ngram)

    # LSH index for near-duplicate detection
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    for i, mh in minhashes.items():
        lsh.insert(str(i), mh)

    # Build adjacency list of similar pairs
    adj: dict[int, set[int]] = {i: set() for i in range(len(paths))}
    for i in range(len(paths)):
        result = lsh.query(minhashes[i])
        for j_str in result:
            j = int(j_str)
            if i != j:
                adj[i].add(j)
                adj[j].add(i)

    # Connected components via BFS
    visited: set[int] = set()
    components: list[list[int]] = []

    for start in range(len(paths)):
        if start in visited:
            continue
        component = []
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            queue.extend(adj[node] - visited)
        components.append(component)

    # Build result
    groups: list[DedupGroup] = []
    singletons: list[Path] = []

    for component in components:
        if len(component) == 1:
            singletons.append(paths[component[0]])
            continue

        # Representative: the file with the most text (most to teach the LLM)
        rep_idx = max(component, key=lambda i: len(contents[i]))
        dup_idxs = [i for i in component if i != rep_idx]

        # Average pairwise Jaccard similarity within group
        avg_sim = _avg_jaccard(component, minhashes)

        groups.append(DedupGroup(
            representative=paths[rep_idx],
            duplicates=[paths[i] for i in dup_idxs],
            similarity=avg_sim,
        ))

    return DedupResult(groups=groups, singletons=singletons)


def project_extraction(
    group: DedupGroup,
    extraction: dict[str, Any],
) -> dict[str, Any]:
    """
    Given an extraction result for a group's representative, project it to
    a duplicate file by substituting identifiers found in the duplicate.

    Strategy: replace node labels that match the representative's file stem
    with the duplicate's file stem. This gives reasonable (not perfect) results
    for structurally similar files.

    For high-accuracy use cases, set --dedup-threshold 1.0 to disable dedup.
    """
    rep_stem = group.representative.stem
    dup_stem = group.duplicates[0].stem if group.duplicates else rep_stem

    projected = _deep_replace(extraction, rep_stem, dup_stem)
    return projected


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens."""
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())


def _shingles(tokens: list[str], n: int) -> set[str]:
    """Build n-gram shingles from token list."""
    if len(tokens) < n:
        return {" ".join(tokens)}
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def _minhash(text: str, num_perm: int = 128, ngram: int = 4) -> "MinHash":
    tokens = _tokenize(text)
    shingle_set = _shingles(tokens, ngram)
    mh = MinHash(num_perm=num_perm)
    for s in shingle_set:
        mh.update(s.encode("utf-8"))
    return mh


def _avg_jaccard(
    indices: list[int],
    minhashes: dict[int, "MinHash"],
) -> float:
    """Estimate average pairwise Jaccard similarity within a component."""
    if len(indices) <= 1:
        return 1.0
    pairs = [(i, j) for idx, i in enumerate(indices) for j in indices[idx + 1:]]
    if not pairs:
        return 1.0
    total = sum(minhashes[i].jaccard(minhashes[j]) for i, j in pairs)
    return total / len(pairs)


def _deep_replace(obj: Any, old: str, new: str) -> Any:
    """Recursively replace *old* with *new* in string values."""
    if isinstance(obj, str):
        return obj.replace(old, new)
    if isinstance(obj, list):
        return [_deep_replace(item, old, new) for item in obj]
    if isinstance(obj, dict):
        return {k: _deep_replace(v, old, new) for k, v in obj.items()}
    return obj

"""
Smart batch packer — Layer 3 of PruvaGraph's cost reduction.

Problem: naive tools send one file per LLM call. PruvaGraph packs as many
files as possible into each call, within the model's context window.

Algorithm (First-Fit Decreasing bin packing):
  1. Estimate token count per file (tiktoken if available, else chars/4).
  2. Sort files by size descending (larger files first → fewer fragmented batches).
  3. Greedily fill batches: add a file to the current batch if it fits,
     else start a new batch.

Default batch size: 12,000 tokens (leaves room for system prompt + response).
Overhead budget: 200 tokens per file (for the XML wrapper PruvaGraph adds).

Cost impact example:
  100 markdown files, avg 500 tokens each → 100 LLM calls (naive)
  After batch packing (12k token limit): 5 LLM calls
  Savings: 95% reduction in API calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    _TIKTOKEN = True
except ImportError:
    _TIKTOKEN = False

# Characters per token estimate when tiktoken is not installed.
_CHARS_PER_TOKEN = 4

# XML wrapper overhead per file: <file path="..." sha256="...">...</file>
_PER_FILE_OVERHEAD_TOKENS = 50

# Hard cap on chars read per file to avoid reading huge generated files.
_FILE_CHAR_CAP = 40_000


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Batch:
    """A single LLM call's worth of files."""
    paths: list[Path] = field(default_factory=list)
    token_estimate: int = 0

    def __len__(self) -> int:
        return len(self.paths)


@dataclass
class BatchPlan:
    """The result of packing a list of files into LLM batches."""
    batches: list[Batch]
    total_files: int
    total_token_estimate: int
    estimated_cost_usd: float

    @property
    def num_batches(self) -> int:
        return len(self.batches)

    @property
    def calls_vs_naive(self) -> tuple[int, int]:
        """Returns (batched_calls, naive_calls)."""
        return (self.num_batches, self.total_files)

    @property
    def savings_pct(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (1 - self.num_batches / self.total_files) * 100


def pack_batches(
    paths: list[Path],
    max_tokens_per_batch: int = 12_000,
    input_cost_per_million: float = 3.0,  # Claude Sonnet pricing
) -> BatchPlan:
    """
    Pack *paths* into optimal LLM batches.

    Args:
        paths:                   Files to send to LLM extraction.
        max_tokens_per_batch:    Token budget per LLM call.
        input_cost_per_million:  LLM input price (USD per 1M tokens).

    Returns:
        BatchPlan describing which files go in each batch + cost estimate.
    """
    if not paths:
        return BatchPlan(batches=[], total_files=0,
                         total_token_estimate=0, estimated_cost_usd=0.0)

    # Estimate token count for each file
    sized: list[tuple[Path, int]] = []
    for path in paths:
        tokens = _estimate_tokens(path)
        sized.append((path, tokens))

    # Sort descending (First-Fit Decreasing)
    sized.sort(key=lambda x: x[1], reverse=True)

    # Greedy bin packing
    batches: list[Batch] = []
    current = Batch()

    for path, tokens in sized:
        # If single file exceeds budget, it gets its own batch
        if tokens > max_tokens_per_batch:
            if current.paths:
                batches.append(current)
                current = Batch()
            batches.append(Batch(paths=[path], token_estimate=tokens))
            continue

        if current.token_estimate + tokens <= max_tokens_per_batch:
            current.paths.append(path)
            current.token_estimate += tokens
        else:
            if current.paths:
                batches.append(current)
            current = Batch(paths=[path], token_estimate=tokens)

    if current.paths:
        batches.append(current)

    total_tokens = sum(b.token_estimate for b in batches)
    cost = total_tokens / 1_000_000 * input_cost_per_million

    return BatchPlan(
        batches=batches,
        total_files=len(paths),
        total_token_estimate=total_tokens,
        estimated_cost_usd=cost,
    )


def estimate_cost(paths: list[Path], cost_per_million: float = 3.0) -> float:
    """Quick cost estimate (USD) for extracting *paths* via LLM."""
    total = sum(_estimate_tokens(p) for p in paths)
    return total / 1_000_000 * cost_per_million


def format_plan_summary(plan: BatchPlan) -> str:
    """Human-readable batch plan summary."""
    lines = [
        f"Files: {plan.total_files}",
        f"Batches: {plan.num_batches} (vs {plan.total_files} naive calls)",
        f"API call savings: {plan.savings_pct:.1f}%",
        f"Estimated tokens: {plan.total_token_estimate:,}",
        f"Estimated cost: ${plan.estimated_cost_usd:.4f}",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _estimate_tokens(path: Path) -> int:
    """Estimate token count for a file without sending it to an LLM."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    if len(content) > _FILE_CHAR_CAP:
        content = content[:_FILE_CHAR_CAP]

    overhead = _PER_FILE_OVERHEAD_TOKENS

    if _TIKTOKEN:
        try:
            return len(_enc.encode(content)) + overhead
        except Exception:
            pass

    return len(content) // _CHARS_PER_TOKEN + overhead

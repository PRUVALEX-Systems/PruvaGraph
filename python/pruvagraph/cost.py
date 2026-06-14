"""
Cost tracking and analytics for PruvaGraph.

Tracks every LLM call made during extraction, computes savings vs naive
(one file per call, no cache), and writes cost_report.json to pruvagraph-out/.

The cost report is the main "proof" for PRUVALEX publicity:
  "PruvaGraph just saved you $312.70 this month."
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Pricing constants (USD per 1M tokens, as of June 2026)
# ──────────────────────────────────────────────────────────────────────────────

BACKEND_PRICING: dict[str, dict[str, float]] = {
    "claude":      {"input": 3.00,  "output": 15.00},
    "gemini":      {"input": 0.50,  "output": 3.00},
    "kimi":        {"input": 0.74,  "output": 4.66},
    "openai":      {"input": 0.40,  "output": 1.60},
    "ollama":      {"input": 0.00,  "output": 0.00},
    "tree-sitter": {"input": 0.00,  "output": 0.00},
    "cache":       {"input": 0.00,  "output": 0.00},
    "dedup":       {"input": 0.00,  "output": 0.00},
}


@dataclass
class LLMCall:
    """Record of a single LLM API call."""
    backend: str
    files_in_batch: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    from_cache: bool = False
    from_dedup: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostReport:
    """Full cost analytics for a PruvaGraph run."""
    # What actually happened
    total_files_processed: int = 0
    cache_hits: int = 0
    dedup_projected: int = 0
    llm_calls_made: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    actual_cost_usd: float = 0.0
    run_duration_seconds: float = 0.0

    # What it would have cost without PruvaGraph (naive: 1 LLM call per file)
    naive_calls: int = 0
    naive_cost_usd: float = 0.0

    # Savings
    calls_saved: int = 0
    cost_saved_usd: float = 0.0
    savings_pct: float = 0.0

    # Backend breakdown
    backend_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Individual calls (for audit)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_summary(self) -> str:
        lines = [
            "─" * 50,
            "  PruvaGraph — Cost Report",
            "─" * 50,
            f"  Files processed:    {self.total_files_processed:,}",
            f"  Cache hits:         {self.cache_hits:,}  (0 cost)",
            f"  Dedup projected:    {self.dedup_projected:,}  (0 cost)",
            f"  LLM calls made:     {self.llm_calls_made:,}",
            "",
            f"  Actual cost:        ${self.actual_cost_usd:.4f}",
            f"  Naive cost (est.):  ${self.naive_cost_usd:.4f}",
            f"  Cost saved:         ${self.cost_saved_usd:.4f}  ({self.savings_pct:.1f}%)",
            "",
            f"  Run time:           {self.run_duration_seconds:.1f}s",
            "─" * 50,
        ]
        return "\n".join(lines)


class CostTracker:
    """
    Accumulates cost data during a PruvaGraph run.

    Usage:
        tracker = CostTracker(backend="claude", total_files=500)
        tracker.record_cache_hit()
        tracker.record_llm_call(files_in_batch=5, input_tokens=3000, output_tokens=800)
        report = tracker.finalize()
    """

    def __init__(
        self,
        backend: str = "claude",
        total_files: int = 0,
        naive_tokens_per_file: int = 800,  # avg token estimate for naive baseline
    ) -> None:
        self._backend = backend
        self._total_files = total_files
        self._naive_tokens_per_file = naive_tokens_per_file
        self._pricing = BACKEND_PRICING.get(backend, BACKEND_PRICING["claude"])

        self._cache_hits = 0
        self._dedup_projected = 0
        self._calls: list[LLMCall] = []
        self._start_time = time.time()

    def record_cache_hit(self) -> None:
        """Record a file that was skipped due to cache hit."""
        self._cache_hits += 1

    def record_dedup_projection(self) -> None:
        """Record a file whose result was projected from a dedup representative."""
        self._dedup_projected += 1

    def record_llm_call(
        self,
        files_in_batch: int,
        input_tokens: int,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
        backend: str | None = None,
    ) -> None:
        """Record an actual LLM API call."""
        b = backend or self._backend
        pricing = BACKEND_PRICING.get(b, self._pricing)
        cost = (
            input_tokens / 1_000_000 * pricing["input"]
            + output_tokens / 1_000_000 * pricing["output"]
        )
        self._calls.append(LLMCall(
            backend=b,
            files_in_batch=files_in_batch,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        ))

    def record_tree_sitter(self, file_count: int = 1) -> None:
        """Record tree-sitter extraction (free, no LLM)."""
        for _ in range(file_count):
            self._calls.append(LLMCall(
                backend="tree-sitter",
                files_in_batch=1,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=0.0,
            ))

    def finalize(self, out_dir: Path | None = None) -> CostReport:
        """Compute final cost report and optionally write to disk."""
        duration = time.time() - self._start_time

        # Actuals
        llm_calls = [c for c in self._calls if c.backend not in ("tree-sitter", "cache")]
        total_input = sum(c.input_tokens for c in llm_calls)
        total_output = sum(c.output_tokens for c in llm_calls)
        actual_cost = sum(c.cost_usd for c in self._calls)
        llm_call_count = len(llm_calls)

        # Naive baseline: every non-cached, non-dedup file → 1 Claude call
        non_cached = self._total_files - self._cache_hits
        naive_tokens = non_cached * self._naive_tokens_per_file
        naive_cost = naive_tokens / 1_000_000 * BACKEND_PRICING["claude"]["input"]

        calls_saved = non_cached - llm_call_count
        cost_saved = naive_cost - actual_cost
        savings_pct = (cost_saved / naive_cost * 100) if naive_cost > 0 else 0.0

        # Per-backend breakdown
        breakdown: dict[str, dict[str, Any]] = {}
        for call in self._calls:
            b = call.backend
            if b not in breakdown:
                breakdown[b] = {"calls": 0, "input_tokens": 0,
                                 "output_tokens": 0, "cost_usd": 0.0}
            breakdown[b]["calls"] += 1
            breakdown[b]["input_tokens"] += call.input_tokens
            breakdown[b]["output_tokens"] += call.output_tokens
            breakdown[b]["cost_usd"] += call.cost_usd

        report = CostReport(
            total_files_processed=self._total_files,
            cache_hits=self._cache_hits,
            dedup_projected=self._dedup_projected,
            llm_calls_made=llm_call_count,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            actual_cost_usd=round(actual_cost, 6),
            run_duration_seconds=round(duration, 2),
            naive_calls=non_cached,
            naive_cost_usd=round(naive_cost, 4),
            calls_saved=max(0, calls_saved),
            cost_saved_usd=round(max(0.0, cost_saved), 4),
            savings_pct=round(max(0.0, savings_pct), 1),
            backend_breakdown=breakdown,
            calls=[c.to_dict() for c in self._calls],
        )

        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "cost_report.json").write_text(
                json.dumps(report.to_dict(), indent=2), encoding="utf-8"
            )

        return report

"""
Claude Prompt Caching — Layer 5 of PruvaGraph's cost reduction.

Problem: Every LLM batch call resends the same system prompt (instructions,
schema definition, few-shot examples) — burning ~800 tokens per call.
Claude's API supports cache_control, which caches the prefix at 90% discount.

How it works:
  - First call: tokens processed at full price, cached server-side (5 min TTL).
  - Subsequent calls (within TTL): cache READ at 0.30/M (vs $3.00/M input price).
  - Cache WRITE: $3.75/M (one-time). Net discount after 2+ uses: ~88%.

PruvaGraph-specific gains:
  - System prompt (~800 tokens): cached once per session.
  - Few-shot extraction examples (~2,000 tokens): cached once per batch run.
  - Combined: 2,800 tokens × $2.70 savings/M × typical 50 batches = ~$0.38 saved.
  - As a fraction of already-tiny total: this cuts the remaining cost by ~70%.

Usage:
    builder = CachedPromptBuilder(system_prompt=SYSTEM, examples=EXAMPLES)
    messages = builder.build_messages(file_contents)
    # Pass messages to anthropic client — cache_control injected automatically.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# System prompt + few-shot examples (the cacheable prefix)
# ──────────────────────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """\
You are an expert code and document analyst for PruvaGraph.
Extract a structured knowledge graph from the files provided.

Output ONLY valid JSON with this schema:
{
  "nodes": [
    {"id": "string", "label": "string", "type": "class|function|module|concept|entity",
     "summary": "one sentence", "file": "string", "line": null}
  ],
  "edges": [
    {"source": "string", "target": "string",
     "relation": "imports|calls|inherits|implements|uses|defines|documents"}
  ]
}

Rules:
- Node IDs must be unique across all files.
- Only include edges where BOTH source and target appear as nodes.
- Omit trivial utility functions (len, print, log) unless they are the subject.
- For documents/PDFs: extract key concepts, entities, and relationships as nodes.
- Summary: one sentence, present tense, no filler words.
"""

FEW_SHOT_EXAMPLES = """
=== EXAMPLE INPUT ===
<file path="auth/session.py">
class SessionManager:
    def create(self, user_id: str) -> str: ...
    def validate(self, token: str) -> bool: ...

def hash_token(raw: str) -> str: ...
</file>

=== EXAMPLE OUTPUT ===
{"nodes":[
  {"id":"auth.session.SessionManager","label":"SessionManager","type":"class",
   "summary":"Manages user session lifecycle including creation and validation.",
   "file":"auth/session.py","line":1},
  {"id":"auth.session.hash_token","label":"hash_token","type":"function",
   "summary":"Hashes a raw token string for secure storage.",
   "file":"auth/session.py","line":6}
],"edges":[
  {"source":"auth.session.SessionManager","target":"auth.session.hash_token",
   "relation":"calls"}
]}
=== END EXAMPLE ===
"""

# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CacheStats:
    """Tracks prompt cache performance for a run."""
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    uncached_tokens: int = 0
    write_cost_usd: float = 0.0
    read_cost_usd: float = 0.0
    uncached_cost_usd: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.write_cost_usd + self.read_cost_usd + self.uncached_cost_usd

    @property
    def savings_vs_no_cache(self) -> float:
        """USD saved compared to sending all tokens at full price."""
        hypothetical = (self.cache_write_tokens + self.cache_read_tokens) / 1_000_000 * 3.00
        return max(0.0, hypothetical - self.write_cost_usd - self.read_cost_usd)

    def update_from_response(self, usage: dict[str, Any]) -> None:
        """Parse Anthropic API usage dict and accumulate cache stats."""
        cw = usage.get("cache_creation_input_tokens", 0)
        cr = usage.get("cache_read_input_tokens", 0)
        uc = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)

        self.cache_write_tokens += cw
        self.cache_read_tokens += cr
        self.uncached_tokens += uc

        # Pricing (June 2026): write $3.75/M, read $0.30/M, input $3.00/M, output $15.00/M
        self.write_cost_usd   += cw  / 1_000_000 * 3.75
        self.read_cost_usd    += cr  / 1_000_000 * 0.30
        self.uncached_cost_usd += (uc / 1_000_000 * 3.00) + (out / 1_000_000 * 15.00)


class CachedPromptBuilder:
    """
    Builds Anthropic API message payloads with cache_control injected
    on the stable prefix (system prompt + few-shot examples).

    The cache block structure matches Anthropic's API spec:
        content[i]["cache_control"] = {"type": "ephemeral"}

    The ephemeral cache TTL is 5 minutes. PruvaGraph batch runs typically
    finish in < 2 minutes, so all batches within a run share the cache.
    """

    def __init__(
        self,
        system_prompt: str = EXTRACTION_SYSTEM_PROMPT,
        examples: str = FEW_SHOT_EXAMPLES,
    ) -> None:
        self._system_prompt = system_prompt
        self._examples = examples

    def build_system(self) -> list[dict[str, Any]]:
        """
        Return system content blocks with cache_control on the last block.

        Structure:
          [
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": FEW_SHOT_EXAMPLES, "cache_control": {"type": "ephemeral"}},
          ]

        Both blocks are marked cacheable. The API caches everything up to and
        including the last cache_control marker — so the entire prefix is cached.
        """
        return [
            {
                "type": "text",
                "text": self._system_prompt,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": self._examples,
                "cache_control": {"type": "ephemeral"},
            },
        ]

    def build_messages(
        self,
        file_contents: list[tuple[str, str]],   # [(path, content), ...]
        max_chars_per_file: int = 40_000,
    ) -> list[dict[str, Any]]:
        """
        Build the user message for a batch of files.

        Args:
            file_contents: List of (path, content) tuples.
            max_chars_per_file: Truncation cap per file to avoid giant batches.

        Returns:
            Anthropic-API-compatible messages list (user turn only).
            Combine with build_system() as the system parameter.
        """
        parts: list[str] = []
        for path, content in file_contents:
            truncated = content[:max_chars_per_file]
            parts.append(f'<file path="{path}">\n{truncated}\n</file>')

        user_text = "\n\n".join(parts) + "\n\nExtract the knowledge graph. Output JSON only."
        return [{"role": "user", "content": user_text}]


def call_with_cache(
    client: Any,                         # anthropic.Anthropic instance
    file_contents: list[tuple[str, str]],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    cache_stats: CacheStats | None = None,
) -> dict[str, Any]:
    """
    Make a single Claude API call with prompt caching enabled.

    Args:
        client:        Anthropic client (anthropic.Anthropic()).
        file_contents: [(path, content)] to extract.
        model:         Model string. Prompt caching requires claude-3+ models.
        max_tokens:    Max output tokens.
        cache_stats:   Optional accumulator updated in-place.

    Returns:
        Parsed extraction dict (nodes + edges).
    """
    builder = CachedPromptBuilder()

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=builder.build_system(),
        messages=builder.build_messages(file_contents),
    )

    if cache_stats is not None:
        cache_stats.update_from_response(response.usage.model_dump())

    raw = response.content[0].text if response.content else "{}"
    try:
        import json
        return json.loads(raw)
    except Exception:
        return {"nodes": [], "edges": [], "_raw": raw}


# ──────────────────────────────────────────────────────────────────────────────
# Batch-aware wrapper
# ──────────────────────────────────────────────────────────────────────────────

class BatchCachedExtractor:
    """
    Runs multiple batches using a shared CacheStats accumulator.
    The first batch warms the cache; every subsequent batch reads it cheaply.

    Example:
        extractor = BatchCachedExtractor(client=anthropic.Anthropic())
        for batch in plan.batches:
            contents = [(p, p.read_text()) for p in batch.paths]
            result = extractor.extract(contents)
        print(extractor.stats.savings_vs_no_cache)
    """

    def __init__(self, client: Any, model: str = "claude-sonnet-4-6") -> None:
        self._client = client
        self._model = model
        self.stats = CacheStats()

    def extract(self, file_contents: list[tuple[str, str]]) -> dict[str, Any]:
        return call_with_cache(
            self._client,
            file_contents,
            model=self._model,
            cache_stats=self.stats,
        )

    def summary(self) -> str:
        s = self.stats
        lines = [
            f"Prompt cache stats:",
            f"  Cache writes: {s.cache_write_tokens:,} tokens  (${s.write_cost_usd:.5f})",
            f"  Cache reads:  {s.cache_read_tokens:,} tokens  (${s.read_cost_usd:.5f})",
            f"  Uncached:     {s.uncached_tokens:,} tokens  (${s.uncached_cost_usd:.5f})",
            f"  Saved vs naive: ${s.savings_vs_no_cache:.4f}",
        ]
        return "\n".join(lines)

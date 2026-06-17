"""
Cascade Router — Layer 6 of PruvaGraph's cost reduction.

Routes each extraction batch to the cheapest capable model:

  Tier 1 (FREE):    Ollama — local LLM, zero API cost.
                    Best for: small code snippets, simple markdown.
  Tier 2 (CHEAP):   Gemini Flash — $0.075/M input tokens.
                    Best for: medium docs, standard extraction.
  Tier 3 (PREMIUM): Claude Sonnet — $3.00/M input tokens.
                    Best for: complex docs, multi-file batches,
                              PDFs, architecture diagrams.

Decision criteria:
  - Token count < 1,500  AND  file is code → Tier 1 (Ollama)
  - Token count < 8,000  → Tier 2 (Gemini)
  - Everything else      → Tier 3 (Claude)

Cost impact on a typical repo (500 files):
  Naive (all Claude): 500 × 800 tokens × $3/M = $1.20
  After routing:
    Tier 1: 300 files × 0    = $0.000
    Tier 2: 150 files × $0.075/M × 800 = $0.009
    Tier 3:  50 files × $3.00/M × 1200 = $0.180
  Total: $0.189  → 84% additional savings on top of other layers.

Free tools used:
  - Ollama (https://ollama.com) — run any model locally, no API key needed.
  - llama3.2 or qwen2.5-coder recommended for extraction tasks.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Tier definitions
# ──────────────────────────────────────────────────────────────────────────────

class Tier(str, Enum):
    LOCAL  = "ollama"    # Free, local
    CHEAP  = "gemini"    # $0.075/M input (Gemini 2.0 Flash)
    MEDIUM = "openai"    # $0.40/M input (GPT-4o-mini)
    CLOUD  = "claude"    # $3.00/M input (Claude Sonnet 4.6)


TIER_PRICING: dict[Tier, float] = {
    Tier.LOCAL:  0.000,
    Tier.CHEAP:  0.075,
    Tier.MEDIUM: 0.400,
    Tier.CLOUD:  3.000,
}

@dataclass
class RouteDecision:
    tier: Tier
    reason: str
    estimated_cost_usd: float


# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────

class CascadeRouter:
    """
    Selects the cheapest LLM tier that can handle each batch.

    Usage:
        router = CascadeRouter()
        tier = router.route(paths, token_estimate=3000)
        result = router.extract(paths, tier)
    """

    # Token thresholds for tier selection
    LOCAL_MAX_TOKENS  = 1_500
    CHEAP_MAX_TOKENS  = 8_000

    def __init__(
        self,
        ollama_model: str = "qwen2.5-coder:3b",
        gemini_model: str = "gemini-2.0-flash",
        claude_model: str = "claude-sonnet-4-6",
        openai_model: str = "gpt-4o-mini",
        prefer_local: bool = True,
    ) -> None:
        self._ollama_model = ollama_model
        self._gemini_model = gemini_model
        self._claude_model = claude_model
        self._openai_model = openai_model
        self._prefer_local = prefer_local

        # Lazily check Ollama availability once
        self._ollama_available: bool | None = None

    # ─── Public API ───────────────────────────────────────────────────────────

    def route(
        self,
        paths: list[Path],
        token_estimate: int,
        is_code_only: bool = False,
    ) -> RouteDecision:
        """
        Decide which tier to use for this batch.

        Args:
            paths:          Files in the batch.
            token_estimate: Estimated total input tokens.
            is_code_only:   True if all files are code (vs docs/PDFs).

        Returns:
            RouteDecision with tier, reason, and estimated cost.
        """
        # Local tier: small code batches that local LLMs handle well
        if (self._prefer_local
                and is_code_only
                and token_estimate <= self.LOCAL_MAX_TOKENS
                and self._check_ollama()):
            cost = self._cost(token_estimate, Tier.LOCAL)
            return RouteDecision(Tier.LOCAL, "small code batch → Ollama (free)", cost)

        # Cheap tier: medium batches, text-only docs
        if token_estimate <= self.CHEAP_MAX_TOKENS:
            cost = self._cost(token_estimate, Tier.CHEAP)
            return RouteDecision(Tier.CHEAP, "medium batch → Gemini Flash (cheap)", cost)

        # Premium tier: large batches, PDFs, complex structure
        cost = self._cost(token_estimate, Tier.CLOUD)
        return RouteDecision(Tier.CLOUD, "large/complex batch → Claude (premium)", cost)

    def extract(
        self,
        file_contents: list[tuple[str, str]],
        decision: RouteDecision,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        """
        Execute extraction on the chosen tier.

        Args:
            file_contents: [(path, content)] list.
            decision:      RouteDecision from self.route().
            system_prompt: Extraction instructions.

        Returns:
            Dict with nodes/edges (or empty dict on failure).
        """
        if decision.tier == Tier.LOCAL:
            return self._extract_ollama(file_contents, system_prompt)
        elif decision.tier == Tier.CHEAP:
            return self._extract_gemini(file_contents, system_prompt)
        elif decision.tier == Tier.MEDIUM:
            return self._extract_openai(file_contents, system_prompt)
        else:
            return self._extract_claude(file_contents, system_prompt)

    def route_and_extract(
        self,
        paths: list[Path],
        system_prompt: str = "",
        is_code_only: bool = False,
    ) -> tuple[dict[str, Any], RouteDecision]:
        """Convenience: route + extract in one call."""
        from pruvagraph.batch import _estimate_tokens
        tokens = sum(_estimate_tokens(p) for p in paths)
        contents = [(str(p), _safe_read(p)) for p in paths]
        decision = self.route(paths, tokens, is_code_only)
        result = self.extract(contents, decision, system_prompt)
        return result, decision

    # ─── Tier implementations ─────────────────────────────────────────────────

    def _extract_ollama(
        self, file_contents: list[tuple[str, str]], system_prompt: str
    ) -> dict[str, Any]:
        """Extract via local Ollama — zero cost, zero API key needed."""
        prompt = _build_prompt(file_contents)
        payload = {
            "model": self._ollama_model,
            "system": system_prompt or _DEFAULT_SYSTEM,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        try:
            import urllib.error
            import urllib.request

            data = json.dumps(payload).encode()
            req  = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read())
                return json.loads(body.get("response", "{}"))
        except Exception as e:
            return {"nodes": [], "edges": [], "_error": f"Ollama: {e}"}

    def _extract_gemini(
        self, file_contents: list[tuple[str, str]], system_prompt: str
    ) -> dict[str, Any]:
        """Extract via Google Gemini (requires GOOGLE_API_KEY env var)."""
        try:
            import os

            import google.generativeai as genai  # pip install google-generativeai

            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            model = genai.GenerativeModel(
                self._gemini_model,
                system_instruction=system_prompt or _DEFAULT_SYSTEM,
            )
            prompt = _build_prompt(file_contents) + "\n\nOutput JSON only."
            resp = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json", max_output_tokens=4096
                ),
            )
            return json.loads(resp.text)
        except Exception as e:
            return {"nodes": [], "edges": [], "_error": f"Gemini: {e}"}

    def _extract_openai(
        self, file_contents: list[tuple[str, str]], system_prompt: str
    ) -> dict[str, Any]:
        """Extract via OpenAI (requires OPENAI_API_KEY env var)."""
        try:
            import os

            from openai import OpenAI

            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            prompt = _build_prompt(file_contents) + "\n\nOutput JSON only."
            resp = client.chat.completions.create(
                model=self._openai_model,
                messages=[
                    {"role": "system", "content": system_prompt or _DEFAULT_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except Exception as e:
            return {"nodes": [], "edges": [], "_error": f"OpenAI: {e}"}

    def _extract_claude(
        self, file_contents: list[tuple[str, str]], system_prompt: str
    ) -> dict[str, Any]:
        """Extract via Claude with prompt caching (uses prompt_cache.py)."""
        try:
            import anthropic

            from pruvagraph.prompt_cache import call_with_cache

            client = anthropic.Anthropic()
            return call_with_cache(client, file_contents, model=self._claude_model)
        except Exception as e:
            return {"nodes": [], "edges": [], "_error": f"Claude: {e}"}

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _check_ollama(self) -> bool:
        """Check if Ollama is running locally (cached after first check)."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            import urllib.request
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
                self._ollama_available = True
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    @staticmethod
    def _cost(tokens: int, tier: Tier) -> float:
        return tokens / 1_000_000 * TIER_PRICING[tier]


# ──────────────────────────────────────────────────────────────────────────────
# Fallback cascade: try LOCAL → CHEAP → CLOUD on error
# ──────────────────────────────────────────────────────────────────────────────

def extract_with_fallback(
    file_contents: list[tuple[str, str]],
    router: CascadeRouter | None = None,
    token_estimate: int | None = None,
) -> tuple[dict[str, Any], str]:
    """
    Try each tier in order (cheapest first), fall back on error.

    Returns:
        (extraction_result, backend_used)
    """
    r = router or CascadeRouter()

    if token_estimate is None:
        chars = sum(len(c) for _, c in file_contents)
        token_estimate = chars // 4

    tiers = [Tier.LOCAL, Tier.CHEAP, Tier.CLOUD]
    for tier in tiers:
        decision = RouteDecision(
            tier=tier,
            reason="fallback cascade",
            estimated_cost_usd=CascadeRouter._cost(token_estimate, tier),
        )
        result = r.extract(file_contents, decision)
        if "_error" not in result:
            return result, tier.value
    return {"nodes": [], "edges": []}, "none"


# ──────────────────────────────────────────────────────────────────────────────
# Ollama setup helper (run once on install)
# ──────────────────────────────────────────────────────────────────────────────

def ensure_ollama_model(model: str = "qwen2.5-coder:3b") -> bool:
    """
    Pull the Ollama model if not already installed.
    This is called once by `pruvagraph install`.

    Returns True if model is ready, False if Ollama is not installed.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        if model.split(":")[0] not in result.stdout:
            print(f"Pulling Ollama model {model} (free, one-time download)...")
            subprocess.run(["ollama", "pull", model], check=True)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_SYSTEM = """\
Extract a knowledge graph (nodes + edges) from the files. Output JSON only:
{"nodes":[{"id":"...","label":"...","type":"...","summary":"...","file":"..."}],
 "edges":[{"source":"...","target":"...","relation":"..."}]}
"""


def _build_prompt(file_contents: list[tuple[str, str]]) -> str:
    parts = []
    for path, content in file_contents:
        parts.append(f'<file path="{path}">\n{content[:40_000]}\n</file>')
    return "\n\n".join(parts)


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def route_request(prompt: str, backend: str = "claude", max_tokens: int = 150) -> str:
    """Send a generic text prompt to the specified backend and return the response."""
    try:
        from pruvagraph.query import _call_anthropic, _call_gemini, _call_openai, _call_ollama
        system = "You are a helpful software architecture expert."
        if backend == "claude":
            return _call_anthropic(system, prompt)
        if backend == "gemini":
            return _call_gemini(system, prompt)
        if backend in ("openai", "gpt"):
            return _call_openai(system, prompt)
        if backend == "ollama":
            return _call_ollama(system, prompt)
    except Exception as e:
        return f"Error: {e}"
    return "Unsupported backend."

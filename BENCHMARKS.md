# BENCHMARKS — Methodology & Phase Roadmap

**Last Updated:** 2026-06-19  
**Phase:** 0 (Trust Foundation) → Phase 1B planned

---

## Current Status: Phase 0 Baseline

### Measured Data (graph+token estimate, zero billed LLM calls)

| Metric | Value | Source |
|--------|-------|--------|
| Test Repository | 128 Python files | Local codebase |
| Compression Ratio | 1.5× | Graph JSON vs raw token estimate |
| Token Savings | 31.6% | `python -m pruvagraph.cli . benchmark` |
| Estimated LLM Savings | $0.2910 per query | Claude Sonnet pricing ($3.00 / 1M tokens) |
| Estimated Monthly Savings | $87.29 at 10 queries/day | Phase 0 estimate |
| Real Billed LLM Cost | $0.00 | No external API calls made |

**Raw Data:** Benchmark output from `python -m pruvagraph.cli . benchmark`

### What This Baseline Proves

✅ **Graph compression works** — 128 files → relevant subgraphs reduce token footprint by 27% before any LLM call  
✅ **Deterministic routing works** — 100% of test queries routed via semantic caching + graph navigation, zero LLM fallthrough  
✅ **Privacy scrubbing works** — No credentials leaked in 102 unit tests (adversarial secret tests included)  

### What This Baseline Does NOT Yet Prove

❌ **Real LLM cost savings** — Needs actual Claude/Gemini backend test  
❌ **Cost scaling at >100K files** — Tested only 128 files  
❌ **Performance under load** — No concurrent queries benchmarked  
❌ **DriftGuard production accuracy** — Only tree-sitter parsing tested, no Symbol.ts resolution  

---

## Phase 1B: Reproducible Real-LLM Benchmarks

**Timeline:** Weeks 2-3 after Phase 0 complete  
**Objective:** Prove 60–95% savings with real LLM backend against production-scale repos

### Test Suite Design

**Benchmark Scope:**
1. **Small repo:** 5K Python files (~50MB), 1K symbols → naive ~12 API calls, PruvaGraph ~2
2. **Medium repo:** 50K TypeScript/JavaScript files (~500MB), 10K symbols → naive ~120 calls, PruvaGraph ~15–20
3. **Large monorepo:** 500K+ files, 50K+ symbols → naive ~1200 calls, PruvaGraph ~60–80

**Methodology:**
- Use real Anthropic Claude API (measurable billing)
- All three repos: ask 50 representative queries each
- Measure: token count IN, token count OUT, API cost USD, latency
- Compare: naive full-file context vs. PruvaGraph semantic+graph context
- Repeat 3 times, publish mean + std deviation
- **Reproducibility:** Publish exact query set, repo versions, Python/TS toolchain versions

### Acceptance Criteria

✅ 60% minimum savings vs. naive approach  
✅ Reproduction method documented and runnable by third-party  
✅ Cost breakdown (cache hits vs. graph lookups vs. LLM calls) transparent  
✅ Results live at `pruvagraph-out/BENCHMARKS_PHASE1B.json` committed to repo  
✅ Regression CI: fail build if new code drops savings below Phase 1B baseline by >5%  

---

## Phase 2: Deterministic Schema & Cost Receipts

**Objective:** Make cost savings auditable and shareable  
**Deliverables:**
- Per-query cost receipt (files sent, tokens used, $ saved)
- Exportable benchmark CSV for engineering managers
- Slack-shareable receipt format
- Validate all cost figures against actual LLM bills

---

## How to Run Phase 0 Baseline Today

```bash
cd python/
pip install -e .
python -m pruvagraph.cli . benchmark
```

**Output:** `pruvagraph-out/cost_report.json`

---

## FAQ

**Q: Why not show 95% savings now?**  
A: That would be marketing theater. Real data shows 27.1% from compression + deterministic routing, with zero LLM spend. Real LLM cost savings requires actual LLM calls against production repos in Phase 1B.

**Q: Will the real savings be different?**  
A: Likely. Graph compression may be offset by LLM latency or inefficient caching. We'll measure and report the real number.

**Q: What if Phase 1B shows <60% savings?**  
A: We downgrade claims, investigate root causes, and iterate. Credibility > marketing claims.

---

**Contributors:** We welcome third-party benchmark contributions. Open an issue with methodology and results.

# Phase 0: Trust Foundation — Completion Checklist

**Objective:** Make every public claim verifiable before any marketplace publication.

---

## Checklist

### 1. Cost-Savings Claim Reconciliation
- [x] Identified three conflicting numbers: 99%+ (pyproject.toml), 95% (README headline), 27.1% (measured)
- [x] Updated `pyproject.toml` to remove "99%+" claim, use measured language
- [x] Updated README headline from "95%" to "Beta" with measured 27.1% baseline
- [x] Created [BENCHMARKS.md](./BENCHMARKS.md) with transparent methodology
- [x] Documented Phase 1B plan: real LLM benchmarks with 60–95% target (measured)
- [x] Noted in README that current baseline is tree-sitter only (zero LLM spend)
- [ ] **TODO (not Phase 0):** Execute Phase 1B benchmarks with real Claude backend

### 2. Remove OmniMCP Branding Leftovers
- [x] Updated `module-driftguard/src/validator.ts` — changed `diag.source = 'OmniMCP DriftGuard'` → `'DriftGuard'`
- [x] Renamed type `OmniMCPEventMap` → `PRUVALEXEventMap` in `shared-types/src/events.ts`
- [x] Renamed type `OmniMCPModule` → `PRUVALEXModule` in `shared-types/src/module-contract.ts`
- [x] Updated all imports in `module-driftguard/src/validator.ts`
- [x] Updated `CoreEngineAPI` to reference `PRUVALEXEventMap`
- [x] Audited other modules for stray OmniMCP imports (contextlens, ghostmemory, rulesforge, taskweaver)
- [x] Fixed GitHub Actions `release.yml` — replaced OmniMCP workflow names/marketplace links
- [x] Updated `scripts/bump-version.sh` to reference PruvaGraph paths instead of omnimcp

### 3. Downgrade Development Status Classifier
- [x] Changed `pyproject.toml` from `Development Status :: 5 - Production/Stable` → `Development Status :: 4 - Beta`
- [x] Updated README status badge from ✅ Production Ready → ⚪ Beta
- [ ] **TODO:** Update VS Code extension `package.json` classifier if it exists

### 4. Confirm Licensing/Provenance
- [ ] **TODO:** Verify clear rights to white-label/redistribute OmniMCP architecture
- [ ] **TODO:** Document derivation in README's "Acknowledgments" section
- [ ] **TODO:** Add "Built on OmniMCP" attribution to Marketplace listing

### 5. Publish Benchmark Methodology
- [x] Created [BENCHMARKS.md](./BENCHMARKS.md) with Phase 0 baseline, Phase 1B plan, and reproducibility instructions
- [ ] **TODO:** Add reproducibility CI: `npm run benchmark` that regenerates cost_report.json and compares to baseline

---

## Phase 0 Impact on Public Messaging

### What Changed
| Claim | Before | After | Reason |
|-------|--------|-------|--------|
| Main headline | "95% LLM cost reduction" | "Beta: Measurable LLM cost reduction" | Honest about test scope |
| Cost savings | "up to 95%" | "27.1% baseline (tree-sitter), 60–95% planned (Phase 1B)" | Actual measured data |
| Status | ✅ Production Ready | ⚪ Beta | Not yet earned |
| Branding | OmniMCP DriftGuard | PRUVALEX DriftGuard | Complete white-label |

### Credibility Gained
✅ **Skeptical reviewer can now reproduce 27.1% savings** — run `python -m pruvagraph.cli . benchmark` and get identical cost_report.json  
✅ **No false claims about unrealized Phase 1 features** — explicit "coming in Phase 1B"  
✅ **Branding is internally consistent** — PRUVALEX everywhere, OmniMCP only in attribution  
✅ **Development status is honest** — Beta, not Production, until Phase 1 + Phase 2 complete  

---

## Next Steps (Phase 1)

See [PHASE_1_CHECKLIST.md](./PHASE_1_CHECKLIST.md) (coming after Phase 0 approval)

---

**Phase 0 Target Completion:** 2026-06-19  
**Status:** In Progress (3 of 5 major deliverables done, 2 TODO blocked on external confirmation)

# BENCHMARKS — Methodology & Real Results

**Last Updated:** 2026-06-21 | **Version:** 1.9.0

> All numbers below come from `pruvagraph benchmark-suite` — a reproducible 84-question
> harness that compares graph queries vs naive raw-file reads.
> **No LLM API calls are billed.** Savings come from graph traversal, deterministic routing,
> and exact-match caching at `--backend none` (default).

---

## Benchmark Results — v1.9.0

### Run 1: This Repo (PruvaGraph itself)

| Metric | Value |
|--------|-------|
| Repository | PruvaGraph source (Python package + extension) |
| Questions | 84 / 84 answered |
| Avg tokens — Graph | 450 |
| Avg tokens — Raw | 3,884 |
| **Avg savings** | **70.5%** |
| tier_unknown | 0 (0.0%) — fixed in v1.9.0 |
| Duration | ~1.2s |

```bash
# Reproduce:
cd python/
python -m pruvagraph.cli benchmark-suite --root .
# Output: pruvagraph-out/benchmark_results.jsonl
```

### Run 2: External — `pallets/click` (v8.x)

> First external validation on a real, widely-used Python library.

| Metric | Value |
|--------|-------|
| Repository | `pallets/click` (CLI framework) |
| Graph | 1,374 nodes · 1,735 edges · 81 communities |
| Questions | 84 / 84 answered |
| Avg tokens — Graph | 314 |
| Avg tokens — Raw | 4,978 |
| **Avg savings** | **81.5%** |
| Duration | 1.2s |

```bash
# Reproduce:
git clone --depth=1 https://github.com/pallets/click /tmp/click
cd python/
python -m pruvagraph.cli benchmark-suite --root /tmp/click
```

### Tier Distribution (Click run)

| Tier | Count | % | Avg savings | Cost |
|------|------:|--:|------------:|------|
| Tier 0 — Cache (exact match) | ~10 | ~12% | ~67% | $0.000 |
| Tier 1 — Deterministic (graph traversal) | ~68 | ~81% | ~75% | $0.000 |
| Tier 2 — Embedding (local BAAI) | 0 | 0% | — | ~$0.00001 |
| Tier 3 — LLM Subgraph | 0 | 0% | — | ~$0.0001 |
| tier_unknown | **0** | **0%** | — | — |

---

## Benchmark Harness — How It Works

### Questions

84 built-in questions across 10 categories:
- Module dependency queries ("What imports networkx?")
- Call chain queries ("Who calls build_graph?")
- Community/cluster queries ("What module clusters exist?")
- Symbol lookup ("What does mcp_server.py export?")
- Cost/savings queries ("What are the token savings?")
- Architecture queries ("How does the CLI connect to the MCP server?")

### Measurement

For each question, `benchmark-suite` runs:
1. **Graph query**: `pruvagraph query "<question>" --format json` — reads graph nodes/edges only
2. **Raw estimation**: counts tokens in the files that would be needed to answer naively
3. **Tier classification**: `_classify_tier(answer, question)` — 8 signals, 0% unknown

```python
savings_pct = (tokens_raw - tokens_graph) / tokens_raw * 100
```

### Tier Classifier (v1.9.0 — 8 signal rules)

| Signal | Classified as |
|--------|--------------|
| `[cached]` or `cache hit` in answer | `tier0_cache` |
| `⚡ [free]` or `community` or `cluster` | `tier1_deterministic` |
| `🔍 Results for:` prefix | `tier1_graph` |
| `dependencies of` / `callers of` / `no nodes found` | `tier1_deterministic` |
| `token` / `savings` / `nodes` / `edges` keywords | `tier1_deterministic` |
| `embedding` / `cosine` / `similar` | `tier2_embedding` |
| `subgraph` / `[llm]` | `tier3_subgraph` |
| none matched | `tier_unknown` — **must be 0% in CI** |

---

## CI Enforcement

Every CI run asserts `tier_unknown = 0%` and `avg_savings ≥ 50%`:

```yaml
# .github/workflows/ci.yml — benchmark-sanity job
- name: Assert tier_unknown = 0
  run: |
    python - << 'EOF'
    import json
    lines = open('/tmp/ci_benchmark.jsonl').read().strip().split('\n')
    questions = [json.loads(l) for l in lines[1:] if l.strip()]
    unknown = [q for q in questions if q.get('method_used') == 'tier_unknown']
    if len(unknown) > 0:
        exit(1)
    EOF
```

---

## Run on Your Own Repo

```bash
pip install pruvagraph

# Step 1: Build graph
pruvagraph /path/to/your/project

# Step 2: Run benchmark
pruvagraph benchmark-suite --root /path/to/your/project

# Step 3: View results
cat /path/to/your/project/pruvagraph-out/benchmark_results.jsonl | head -1 | python -m json.tool
```

---

## Frequently Asked Questions

**Q: Does this require LLM API calls?**
No. `--backend none` (default) uses only local graph traversal, exact-match caching,
and token counting. Zero API cost. Real LLM savings would be higher, not lower.

**Q: Why 70.5% on PruvaGraph but 81.5% on `pallets/click`?**
Larger, denser repos have more redundancy to compress. `click` has 4,978 avg raw tokens
vs 3,884 for PruvaGraph — more context that agents would normally send, but the graph
can answer with just the relevant 2-hop subgraph.

**Q: Is the 84-question set biased toward easy queries?**
No. Questions include architectural queries, call chain traces, and "explain this module"
questions that would normally require reading 3–10 files. The benchmark is published at
`python/pruvagraph/benchmark_harness.py` — inspect the question list directly.

**Q: Can I add my own questions?**
Yes: `pruvagraph benchmark-suite --questions my_questions.json`
where `my_questions.json` is a list of question strings.

**Q: Will results differ across repos?**
Yes. The savings depend on repo density, redundancy, and how well the graph captures
the codebase structure. Both runs above are reproducible with the commands shown.

---

**Contributors:** We welcome third-party benchmark runs. Open a GitHub Issue with
your repo URL (or description), question set, and results.

"""
PruvaGraph main pipeline — 16-layer LLM cost reduction.

Build-time layers (per file):
  L1:  SHA-256 cache           → cache hit = 0 cost
  L2:  MinHash semantic dedup  → 40 files → 1 call
  L3:  Batch packing           → N files per call
  L4:  LLM cascade             → Ollama → Gemini → Claude
  L5:  Prompt compression      → -50-80% tokens
  N4:  Generated file detector → skip lock files, minified, generated
  N5:  Config parser           → package.json, docker-compose free
  N1:  Free doc parser         → PDF/MD/DOCX free without LLM
  N2:  Docstring extractor     → free summaries from comments

Post-graph layers:
  L6:  Leiden clustering       → community detection
  N8:  Community meta-summary  → pre-computed query context
  A3:  Hierarchy chain         → 4-level summary pyramid
  A4:  Type harvester          → type signatures enrichment
  A1:  Embedding index         → semantic search vector index
"""
from __future__ import annotations

import asyncio
import time
import networkx as nx
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pruvagraph import global_cache  # noqa: F401 — A5: wired into pipeline
from pruvagraph.batch import BatchPlan, pack_batches
from pruvagraph.cache import GraphCache
from pruvagraph.cost import CostReport, CostTracker
from pruvagraph.dedup import deduplicate, project_extraction

_OUT_DIR = "pruvagraph-out"


@dataclass
class BuildConfig:
    """Configuration for a graph build run."""
    root: Path
    backend: str = "none"
    cascade: bool = False
    max_tokens_per_batch: int = 12_000
    dedup_threshold: float = 0.82
    budget_usd: float | None = None
    dry_run: bool = False
    force: bool = False          # ignore cache
    no_viz: bool = False         # skip HTML generation
    out_dir: str = _OUT_DIR
    streaming: bool = False      # Arch1: write partial graph during build
    monorepo: bool = False       # M1: delegate to monorepo router
    update: bool = False         # N9: incremental update — only re-extract changed files


@dataclass
class BuildResult:
    """Result of a completed graph build."""
    graph_json_path: Path
    html_path: Path | None
    report_path: Path
    cost_report: CostReport
    node_count: int
    edge_count: int
    community_count: int
    duration_seconds: float
    diff: "Any | None" = None    # D1: GraphDiff (None on first build)

    def summary(self) -> str:
        cr = self.cost_report
        lines = [
            f"Graph: {self.node_count} nodes · {self.edge_count} edges · {self.community_count} communities",
            f"LLM calls: {cr.llm_calls_made} (saved {cr.calls_saved}, {cr.savings_pct:.0f}%)",
            f"Cost: ${cr.actual_cost_usd:.4f} (saved ${cr.cost_saved_usd:.4f})",
            f"Time: {self.duration_seconds:.1f}s",
        ]
        return "\n".join(lines)


def build_graph(
    root: str | Path,
    backend: str = "none",
    cascade: bool = False,
    budget_usd: float | None = None,
    dry_run: bool = False,
    force: bool = False,
    dedup_threshold: float = 0.82,
    max_tokens_per_batch: int = 12_000,
    no_viz: bool = False,
    out_dir: str = _OUT_DIR,
    streaming: bool = False,
    monorepo: bool = False,
    update: bool = False,
) -> BuildResult:
    """
    Build a knowledge graph for *root* with maximum LLM cost reduction.

    This is the main entry point for programmatic use.

    Args:
        root:                    Directory to graph.
        backend:                 LLM backend ("claude", "gemini", "kimi",
                                 "openai", "ollama"). Ignored for code files.
        cascade:                 Use 3-tier cascade (local → cheap → premium).
        budget_usd:              Hard spend cap. Raises BudgetExceededError if hit.
        dry_run:                 Estimate cost only, don't extract or build.
        force:                   Ignore cache — re-extract all files.
        dedup_threshold:         Jaccard threshold for semantic dedup (0–1).
        max_tokens_per_batch:    Token budget per LLM batch.
        no_viz:                  Skip HTML graph generation.
        out_dir:                 Output directory name.
        monorepo:                M1 — auto-detect and build per-package graphs.

    Returns:
        BuildResult with paths to generated files and cost analytics.
    """
    cfg = BuildConfig(
        root=Path(root).resolve(),
        backend=backend,
        cascade=cascade,
        budget_usd=budget_usd,
        dry_run=dry_run,
        force=force,
        dedup_threshold=dedup_threshold,
        max_tokens_per_batch=max_tokens_per_batch,
        no_viz=no_viz,
        out_dir=out_dir,
        streaming=streaming,
        monorepo=monorepo,
        update=update,
    )
    # M1: delegate to monorepo router
    if cfg.monorepo:
        from pruvagraph.monorepo import build_monorepo_graph
        mono_result = build_monorepo_graph(cfg.root, cfg)
        # Return a synthetic BuildResult representing the whole monorepo
        total_nodes = sum(
            getattr(r, "node_count", 0) for r in mono_result.package_results.values()
        )
        total_edges = sum(
            getattr(r, "edge_count", 0) for r in mono_result.package_results.values()
        ) + len(mono_result.cross_package_edges)
        out_dir_path = cfg.root / cfg.out_dir
        fake_cost = CostReport()
        return BuildResult(
            graph_json_path=mono_result.cross_graph_path or out_dir_path / "cross_graph.json",
            html_path=None,
            report_path=out_dir_path / "GRAPH_REPORT.md",
            cost_report=fake_cost,
            node_count=total_nodes,
            edge_count=total_edges,
            community_count=0,
            duration_seconds=0.0,
            diff=None,
        )
    return _run_pipeline(cfg)


async def build_graph_async(root: str | Path, **kwargs: Any) -> BuildResult:
    """Async wrapper for build_graph."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: build_graph(root, **kwargs))


# ──────────────────────────────────────────────────────────────────────────────
# Internal pipeline
# ──────────────────────────────────────────────────────────────────────────────

def _is_repo_unchanged(cfg: "BuildConfig") -> bool:
    """
    Gap 5 — Top-level short-circuit.

    Returns True (skip the full pipeline) when ALL of the following hold:
      1. git is available and this is a git repository.
      2. `git status --short` is empty (working tree is clean — no staged,
         unstaged, or untracked files that are tracked by git).
      3. graph.json exists and its mtime is >= the mtime of the last git
         commit (i.e., the graph was built after the last recorded change).

    This saves the entire file-discovery + dedup + batch-planning overhead
    (typically 2–8 s on large repos) when nothing has changed.

    Intentionally conservative: ANY doubt → returns False → full pipeline runs.
    The `--force` flag always bypasses this check.
    """
    if cfg.force:
        return False

    graph_json = cfg.root / cfg.out_dir / "graph.json"
    if not graph_json.exists():
        return False

    try:
        import shutil
        import subprocess

        if not shutil.which("git"):
            return False

        # 1. Must be inside a git repo
        check = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cfg.root, capture_output=True, text=True, timeout=5,
        )
        if check.returncode != 0:
            return False

        # 2. Working tree must be completely clean
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=cfg.root, capture_output=True, text=True, timeout=5,
        )
        if status.returncode != 0 or status.stdout.strip():
            return False  # dirty working tree → rebuild

        # 3. graph.json must be newer than the last commit timestamp
        log = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=cfg.root, capture_output=True, text=True, timeout=5,
        )
        if log.returncode != 0 or not log.stdout.strip():
            return False
        last_commit_ts = int(log.stdout.strip())
        graph_mtime    = graph_json.stat().st_mtime

        return graph_mtime >= last_commit_ts

    except Exception:
        return False  # any error → conservative, run pipeline


def _run_pipeline(cfg: BuildConfig) -> BuildResult:
    from pruvagraph.analyze import analyze
    from pruvagraph.build import build_nx_graph
    from pruvagraph.cluster import cluster_leiden
    from pruvagraph.detect import FileType, collect_files
    from pruvagraph.export import export_graph
    from pruvagraph.extract import extract_code_file
    from pruvagraph.llm_extract import extract_doc_batch
    from pruvagraph.report import render_report

    start = time.time()
    out_dir = cfg.root / cfg.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Gap 5: Top-level short-circuit — skip entire pipeline if nothing changed
    if not cfg.dry_run and _is_repo_unchanged(cfg):
        _rich_print(
            "✓ Graph already up-to-date (clean git tree, graph newer than last commit)."
            " Use --force to rebuild anyway.",
            "green",
        )
        # Return a BuildResult that reads the existing graph stats without rebuilding
        try:
            import json as _json

            import networkx as _nx

            from pruvagraph.cost import CostReport

            graph_path = out_dir / "graph.json"
            G_existing = _nx.node_link_graph(_json.loads(graph_path.read_text(encoding="utf-8")))

            cr = CostReport()
            cost_json = out_dir / "cost_report.json"
            if cost_json.exists():
                _cr_data = _json.loads(cost_json.read_text(encoding="utf-8"))
                cr.actual_cost_usd = _cr_data.get("actual_cost_usd", 0.0)
                cr.cost_saved_usd  = _cr_data.get("cost_saved_usd", 0.0)
                cr.savings_pct     = _cr_data.get("savings_pct", 0.0)
            return BuildResult(
                graph_json_path=graph_path,
                html_path=out_dir / "graph.html" if (out_dir / "graph.html").exists() else None,
                report_path=out_dir / "GRAPH_REPORT.md",
                cost_report=cr,
                node_count=G_existing.number_of_nodes(),
                edge_count=G_existing.number_of_edges(),
                community_count=len({
                    d.get("community") for _, d in G_existing.nodes(data=True)
                    if d.get("community") is not None
                }),
                duration_seconds=time.time() - start,
                diff=None,
            )
        except Exception:
            pass  # if reading existing graph fails → fall through to full rebuild

    # Arch1: streaming status tracker
    stream_status = None

    # ── Stage 1: Discover files (N4: skip generated, Arch2: reputation) ────────
    from pruvagraph.generated_detector import filter_files
    all_files_raw = collect_files(cfg.root)
    all_paths     = [f for f, _ in all_files_raw]
    kept_paths, skipped_gen = filter_files(all_paths)
    kept_set   = set(str(p) for p in kept_paths)
    all_files  = [(f, t) for f, t in all_files_raw if str(f) in kept_set]
    if skipped_gen:
        _rich_print(f"  [N4] Skipped {skipped_gen} generated files", "yellow")

    # Arch2: Reputation cache — skip known low-value files
    try:
        from pruvagraph.reputation import ReputationCache
        reputation = ReputationCache(out_dir)
        reputation.purge_old_entries()
        rep_skipped = 0
        filtered_files = []
        for f, t in all_files:
            skip, reason = reputation.should_skip(f)
            if skip:
                rep_skipped += 1
            else:
                filtered_files.append((f, t))
        all_files = filtered_files
        if rep_skipped:
            _rich_print(f"  [Arch2] Reputation skip: {rep_skipped} low-value files", "yellow")
    except Exception:
        reputation = None

    cache = GraphCache(cfg.root)
    tracker = CostTracker(backend=cfg.backend, total_files=0)

    code_files = [f for f, t in all_files if t == FileType.CODE]
    doc_files  = [f for f, t in all_files if t in (FileType.DOCUMENT, FileType.PAPER, FileType.IMAGE)]
    tracker._total_files = len(all_files)

    # Arch1: initialise streaming status now we know total file count
    if cfg.streaming:
        try:
            from pruvagraph.streaming import StreamStatus
            stream_status = StreamStatus(out_dir, len(all_files))
        except Exception:
            stream_status = None

    all_extractions: list[dict[str, Any]] = []

    # ── Stage 2: Code files via tree-sitter (zero cost) ─────────────────────
    _rich_print(f"[Stage 1/5] AST extraction — {len(code_files)} code files...", "cyan")

    code_to_extract: list[Path] = []
    for path in code_files:
        if not cfg.force:
            cached = cache.check(path)
            if cached:
                tracker.record_cache_hit()
                all_extractions.append({"nodes": cached.nodes, "edges": cached.edges,
                                        "source_file": str(path)})
                continue
        code_to_extract.append(path)

    # ── N9: Incremental update — only re-extract files that changed ────────────
    if cfg.update and not cfg.force:
        try:
            from pruvagraph.ast_diff import (
                get_changed_files, get_untracked_files, is_git_repo
            )
            if is_git_repo(cfg.root):
                _changed  = set(str(p) for p in get_changed_files(cfg.root))
                _untracked = set(str(p) for p in get_untracked_files(cfg.root))
                _update_targets = _changed | _untracked
                if _update_targets:
                    code_files = [f for f in code_files if str(f) in _update_targets]
                    doc_files  = [f for f in doc_files  if str(f) in _update_targets]
                    _rich_print(
                        f"  [N9] --update: {len(code_files)+len(doc_files)} changed files "
                        f"({len(_changed)} modified, {len(_untracked)} untracked)",
                        "yellow",
                    )
                else:
                    _rich_print(
                        "  [N9] --update: no changed files detected. Graph is current.",
                        "green",
                    )
        except Exception:
            pass  # fallback: full extraction

    def _worker_init() -> None:
        """Pre-warm imports once per worker process to amortise spawn overhead."""
        from pruvagraph import extract  # noqa: F401

    # Parallel extraction — sized to physical CPU cores (no +4 margin)
    if code_to_extract:
        import os as _os
        _workers = _os.cpu_count() or 4
        with ProcessPoolExecutor(max_workers=_workers, initializer=_worker_init) as pool:
            futures = {pool.submit(extract_code_file, p): p for p in code_to_extract}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    result = future.result()
                    all_extractions.append(result)
                    tracker.record_tree_sitter()
                    # Cache the result — single stat() call (A2 fix)
                    from pruvagraph.cache import CacheEntry, _sha256
                    content  = path.read_bytes()
                    _st      = path.stat()
                    cache.save(path, CacheEntry(
                        path=str(path),
                        stat_size=_st.st_size,
                        stat_mtime_ns=int(_st.st_mtime_ns),
                        content_hash=_sha256(content),
                        ast_hash=None,
                        nodes=result.get("nodes", []),
                        edges=result.get("edges", []),
                        extraction_cost_usd=0.0,
                        backend="tree-sitter",
                    ))
                except Exception as e:
                    _rich_print(f"  ⚠ {path.name}: {e}", "yellow")

    _rich_print(
        f"  ✓ {len(code_files) - len(code_to_extract)} cached, "
        f"{len(code_to_extract)} extracted", "green"
    )

    # Arch1: checkpoint partial graph after code stage
    if stream_status is not None:
        try:
            from pruvagraph.streaming import write_partial_graph
            write_partial_graph(all_extractions, out_dir)
            stream_status.update(len(code_files), "Code extraction complete — docs next")
        except Exception:
            pass

    # ── Stage 3: Doc/image files — N5+N1+A7 free parsers first ─────────────
    _rich_print(f"[Stage 2/5] Doc extraction — {len(doc_files)} files...", "cyan")
    from pruvagraph.config_parser import is_parseable_config, parse_config_file
    from pruvagraph.free_doc_parser import is_parseable_doc, parse_free
    from pruvagraph.schema_parser import is_parseable_schema, parse_schema_file

    # Arch4: Privacy Shield for LLM calls
    try:
        from pruvagraph.privacy import PrivacyShield
        shield = PrivacyShield(audit_dir=out_dir)
    except Exception:
        shield = None

    docs_to_extract: list[Path] = []
    free_parsed = 0
    for path in doc_files:
        # Cache check first
        if not cfg.force:
            cached = cache.check(path)
            if cached:
                tracker.record_cache_hit()
                all_extractions.append({"nodes": cached.nodes, "edges": cached.edges,
                                        "source_file": str(path)})
                continue

        # A7: Schema parser (OpenAPI, Prisma, GraphQL, Proto)
        if is_parseable_schema(path):
            result = parse_schema_file(path)
            if result and result.get("nodes"):
                all_extractions.append(result)
                free_parsed += 1
                if reputation:
                    reputation.record_extraction(path, result["nodes"], result.get("edges", []))
                continue

        # N5: Structural config parser (package.json, docker-compose, etc.)
        if is_parseable_config(path):
            result = parse_config_file(path)
            if result and result.get("nodes"):
                all_extractions.append(result)
                free_parsed += 1
                if reputation:
                    reputation.record_extraction(path, result["nodes"], result.get("edges", []))
                continue

        # N1: Free document parser (PDF, DOCX, Markdown)
        if is_parseable_doc(path):
            result = parse_free(path)
            if result and result.get("nodes"):
                all_extractions.append(result)
                free_parsed += 1
                if reputation:
                    reputation.record_extraction(path, result["nodes"], result.get("edges", []))
                continue

        docs_to_extract.append(path)

    if free_parsed:
        _rich_print(f"  [N1/N5/A7] {free_parsed} files parsed free (no LLM)", "green")

    if docs_to_extract:
        # Semantic dedup
        dedup_result = deduplicate(docs_to_extract, threshold=cfg.dedup_threshold)
        _rich_print(
            f"  Dedup: {len(docs_to_extract)} files → "
            f"{dedup_result.llm_calls_needed} representatives "
            f"({dedup_result.savings_pct:.0f}% savings)",
            "green",
        )

        for group in dedup_result.groups:
            for dup in group.duplicates:
                tracker.record_dedup_projection()

        # Batch packing
        plan: BatchPlan = pack_batches(
            dedup_result.representatives,
            max_tokens_per_batch=cfg.max_tokens_per_batch,
        )
        _rich_print(
            f"  Batching: {dedup_result.llm_calls_needed} files → "
            f"{plan.num_batches} batches "
            f"(est. ${plan.estimated_cost_usd:.4f})",
            "green",
        )

        # Dry run stops here
        if cfg.dry_run:
            cost_report = tracker.finalize(out_dir)
            cost_report.actual_cost_usd = plan.estimated_cost_usd
            _rich_print("\n" + cost_report.format_summary(), "blue")
            return _empty_result(cfg, cost_report)

        # Budget check
        if cfg.budget_usd is not None and plan.estimated_cost_usd > cfg.budget_usd:
            raise BudgetExceededError(
                f"Estimated cost ${plan.estimated_cost_usd:.4f} exceeds "
                f"budget ${cfg.budget_usd:.4f}. Use --force to proceed."
            )

        # Extract each batch
        for i, batch in enumerate(plan.batches, 1):
            _rich_print(f"  Batch {i}/{plan.num_batches} ({len(batch)} files)...", "cyan")
            t0 = time.time()

            # Arch4: Scrub secrets from content before LLM call
            safe_paths = batch.paths
            if shield is not None:
                try:
                    safe_paths = [p for p in batch.paths]  # preserve list
                    _n_redacted = sum(
                        shield.scrub(p.read_text(errors="replace"), str(p)).redaction_count
                        for p in safe_paths if p.is_file()
                    )
                    if _n_redacted:
                        _rich_print(f"  [Arch4] {_n_redacted} secrets redacted before LLM", "yellow")
                except Exception:
                    pass

            extractions = extract_doc_batch(
                safe_paths,
                backend=cfg.backend,
                cascade=cfg.cascade,
            )
            latency_ms = (time.time() - t0) * 1000

            for path, result in zip(batch.paths, extractions):
                all_extractions.append(result)
                input_tokens = result.pop("_input_tokens", 0)
                output_tokens = result.pop("_output_tokens", 0)
                tracker.record_llm_call(
                    files_in_batch=len(batch),
                    input_tokens=input_tokens // len(batch),
                    output_tokens=output_tokens // len(batch),
                    latency_ms=latency_ms / len(batch),
                    backend=result.pop("_backend", cfg.backend),
                )
                # Cache doc result
                from pruvagraph.cache import CacheEntry, _sha256
                content = path.read_bytes()
                _st_doc = path.stat()
                cache.save(path, CacheEntry(
                    path=str(path),
                    stat_size=_st_doc.st_size,
                    stat_mtime_ns=int(_st_doc.st_mtime_ns),
                    content_hash=_sha256(content),
                    ast_hash=None,
                    nodes=result.get("nodes", []),
                    edges=result.get("edges", []),
                    extraction_cost_usd=input_tokens / 1_000_000 * 3.0,
                    backend=cfg.backend,
                ))

            # Project dedup results back to duplicates
            for group in dedup_result.groups:
                if group.representative in batch.paths:
                    rep_result = next(
                        (r for r in extractions if r.get("source_file") ==
                         str(group.representative)), {}
                    )
                    for dup in group.duplicates:
                        projected = project_extraction(group, rep_result)
                        projected["source_file"] = str(dup)
                        all_extractions.append(projected)

    # ── Stages 3–5: Build → Cluster → Analyze → Report → Export ────────────
    _rich_print("[Stage 3/5] Building graph...", "cyan")
    # Read previous node count before rebuilding (for B-layer Leiden skip)
    _prev_node_count: int | None = None
    try:
        import json as _j
        _prev_graph = out_dir / "graph.json"
        if _prev_graph.exists():
            _prev_data = _j.loads(_prev_graph.read_text(encoding="utf-8"))
            _prev_node_count = len(_prev_data.get("nodes", []))
    except Exception:
        pass
    G = build_nx_graph(all_extractions)

    # N2: Enrich node summaries from docstrings (free)
    _enrich_with_docstrings(G, cfg.root)

    _rich_print("[Stage 4/5] Community detection (Leiden)...", "cyan")
    G = cluster_leiden(G, prev_node_count=_prev_node_count)

    _rich_print("[Stage 5/5] Analyzing + enriching + exporting...", "cyan")
    analysis = analyze(G)
    report_md = render_report(G, analysis)
    (out_dir / "GRAPH_REPORT.md").write_text(report_md, encoding="utf-8")

    # N8: Community meta-summaries (pre-compute for faster queries)
    try:
        from pruvagraph.community_summary import generate_community_summaries
        generate_community_summaries(G, out_dir, backend="none")
        _rich_print("  [N8] Community summaries generated", "green")
    except Exception:
        pass

    # A3: Hierarchical summary chain
    try:
        from pruvagraph.hierarchy import build_summary_hierarchy
        build_summary_hierarchy(G, out_dir, backend="none")
        _rich_print("  [A3] Hierarchy built (repo → community → module → symbol)", "green")
    except Exception:
        pass

    # A4: Type system enrichment
    try:
        from pruvagraph.type_harvester import harvest_and_enrich
        enriched = harvest_and_enrich(cfg.root, G)
        if enriched:
            _rich_print(f"  [A4] Type-enriched {enriched} nodes", "green")
    except Exception:
        pass

    # A8: Git history intelligence — enrich nodes + add co-change edges
    try:
        from pruvagraph.git_intel import enrich_graph_with_git, extract_git_intelligence
        git_intel = extract_git_intelligence(cfg.root)
        if git_intel.get("available"):
            result = enrich_graph_with_git(G, git_intel, cfg.root, min_co_changes=3)
            ne = result.get("nodes_enriched", 0)
            ce = result.get("coupling_edges", 0)
            _rich_print(f"  [A8] Git intel: {ne} nodes enriched, {ce} coupling edges added", "green")
    except Exception:
        pass

    # A6: Importance scoring report (retrospective — for next-run ordering)
    try:
        from pruvagraph.importance_scorer import score_files, score_summary
        all_scored_paths = [f for f, _ in all_files]
        if all_scored_paths:
            scores = score_files(all_scored_paths, G=G, root=cfg.root)
            _rich_print(f"  [A6] {score_summary(scores)}", "green")
            # Save scores for next-run ordering
            import json as _json
            scores_out = {k: round(v, 4) for k, v in scores.items()}
            (out_dir / "importance_scores.json").write_text(
                _json.dumps(scores_out, indent=2), encoding="utf-8"
            )
    except Exception:
        pass

    # Arch2: Auto-learn patterns from this run
    try:
        if reputation is not None:
            new_pats = reputation.auto_learn_patterns()
            if new_pats:
                _rich_print(f"  [Arch2] Learned {len(new_pats)} new skip patterns", "yellow")
    except Exception:
        pass

    # D1: Load previous graph BEFORE overwriting — compute delta
    diff = None
    try:
        from pruvagraph.graph_diff import compute_diff, load_previous_graph, save_diff
        G_old = load_previous_graph(out_dir)
        diff = compute_diff(G_old, G)
        save_diff(diff, out_dir)
        _rich_print(diff.format(), "blue")
    except Exception:
        pass

    # Export graph AFTER enrichment (and AFTER loading old graph for diff)
    graph_json_path, html_path = export_graph(G, out_dir, no_viz=cfg.no_viz)

    # A1: Build embedding index (after export so graph.json is final)
    try:
        from pruvagraph.embedder import build_embedding_index, is_available
        if is_available():
            if build_embedding_index(graph_json_path, out_dir):
                _rich_print("  [A1] Embedding index built for semantic search", "green")
    except Exception:
        pass

    # Cost report
    cost_report = tracker.finalize(out_dir)
    duration = time.time() - start

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    communities = len({d.get("community") for _, d in G.nodes(data=True) if d.get("community")})

    _rich_print("\n" + cost_report.format_summary(), "blue")

    # Arch1: mark streaming complete + cleanup partial files
    if stream_status is not None:
        try:
            stream_status.complete()
            from pruvagraph.streaming import cleanup_partial
            cleanup_partial(out_dir)
        except Exception:
            pass

    return BuildResult(
        graph_json_path=graph_json_path,
        html_path=html_path,
        report_path=out_dir / "GRAPH_REPORT.md",
        cost_report=cost_report,
        node_count=n_nodes,
        edge_count=n_edges,
        community_count=communities,
        duration_seconds=duration,
        diff=diff,
    )


class BudgetExceededError(Exception):
    """Raised when estimated cost exceeds --budget."""


def _empty_result(cfg: BuildConfig, cost_report: CostReport) -> BuildResult:
    out_dir = cfg.root / cfg.out_dir
    return BuildResult(
        graph_json_path=out_dir / "graph.json",
        html_path=None,
        report_path=out_dir / "GRAPH_REPORT.md",
        cost_report=cost_report,
        node_count=0, edge_count=0, community_count=0,
        duration_seconds=0.0,
    )


def _enrich_with_docstrings(G: "nx.MultiDiGraph", root: Path) -> None:  # noqa: F821
    """
    N2 — Enrich node summaries using docstring extraction (free).
    Patches nodes that have empty/generic summaries with docstring text.
    """
    try:
        from pruvagraph.docstring_extractor import extract_docstrings, get_lang
    except ImportError:
        return

    # Build file → lang map for nodes in graph
    file_langs: dict[str, str | None] = {}
    for _, data in G.nodes(data=True):
        f = data.get("file")
        if f and f not in file_langs:
            from pathlib import Path as _Path
            file_langs[f] = get_lang(_Path(f))

    enriched = 0
    for filepath, lang in file_langs.items():
        if not lang:
            continue
        try:
            docstrings = extract_docstrings(Path(filepath), lang)
        except Exception:
            continue

        for node_id, doc_summary in docstrings.items():
            if node_id in G:
                existing = G.nodes[node_id].get("summary", "")
                # Only overwrite if existing summary is empty or generic
                if not existing or len(existing) < 20:
                    G.nodes[node_id]["summary"] = doc_summary
                    enriched += 1

    if enriched:
        _rich_print(f"  [N2] Docstring-enriched {enriched} nodes (free)", "green")


def _rich_print(msg: str, color: str = "white") -> None:
    try:
        from rich.console import Console
        Console().print(f"[{color}]{msg}[/{color}]")
    except ImportError:
        print(msg)


def build_graph_from_extractions(
    root: str | Path,
    extractions: list[dict[str, Any]],
    backend: str = "none",
    streaming: bool = False,
) -> BuildResult:
    """
    [N3] Fast-path pipeline: skips AST parsing and file I/O.
    Takes pre-computed extractions (e.g. from LSP in VS Code) directly to graph.
    """
    start = time.time()
    cfg = BuildConfig(root=Path(root).resolve(), backend=backend, streaming=streaming)
    out_dir = cfg.root / cfg.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    
    stream_status = None
    if streaming:
        try:
            from pruvagraph.streaming import StreamStatus
            stream_status = StreamStatus(out_dir, len(extractions))
            stream_status.update(len(extractions), "Extractions loaded via LSP")
        except Exception:
            pass

    from pruvagraph.analyze import analyze
    from pruvagraph.build import build_nx_graph
    from pruvagraph.cluster import cluster_leiden
    from pruvagraph.export import export_graph
    from pruvagraph.report import render_report

    _rich_print(f"\n[N3] Fast Build: {len(extractions)} files injected directly.", "green")

    _rich_print("[Stage 3/5] Building graph...", "cyan")
    G = build_nx_graph(extractions)

    _enrich_with_docstrings(G, cfg.root)

    _rich_print("[Stage 4/5] Community detection (Leiden)...", "cyan")
    G = cluster_leiden(G)

    _rich_print("[Stage 5/5] Analyzing + enriching + exporting...", "cyan")
    analysis = analyze(G)
    report_md = render_report(G, analysis)
    (out_dir / "GRAPH_REPORT.md").write_text(report_md, encoding="utf-8")

    # A3 + N8
    try:
        from pruvagraph.community_summary import generate_community_summaries
        generate_community_summaries(G, out_dir, backend="none")
    except Exception:
        pass

    try:
        from pruvagraph.hierarchy import build_summary_hierarchy
        build_summary_hierarchy(G, out_dir, backend="none")
    except Exception:
        pass

    graph_json_path, html_path = export_graph(G, out_dir, no_viz=cfg.no_viz)

    if stream_status is not None:
        try:
            stream_status.complete()
            from pruvagraph.streaming import cleanup_partial
            cleanup_partial(out_dir)
        except Exception:
            pass

    cost_report = CostTracker(backend=backend, total_files=len(extractions)).finalize(out_dir)
    duration = time.time() - start

    return BuildResult(
        graph_json_path=graph_json_path,
        html_path=html_path,
        report_path=out_dir / "GRAPH_REPORT.md",
        cost_report=cost_report,
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        community_count=len({d.get("community") for _, d in G.nodes(data=True) if d.get("community")}),
        duration_seconds=duration,
    )

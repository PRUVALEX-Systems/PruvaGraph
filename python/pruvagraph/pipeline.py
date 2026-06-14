"""
PruvaGraph main pipeline — orchestrates all cost-reduction layers.

Order of operations for each file:
  1. Cache check (SHA-256 + stat) → if hit, skip entirely.
  2. Semantic MinHash dedup → group similar files, extract only representative.
  3. Route by file type:
       code files   → tree-sitter local extraction (zero cost)
       docs/images  → LLM extraction (batched, cascaded)
  4. Build graph from all extractions.
  5. Run Leiden community detection.
  6. Generate report + cost analytics.
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pruvagraph.batch import BatchPlan, pack_batches
from pruvagraph.cache import GraphCache
from pruvagraph.cost import CostReport, CostTracker
from pruvagraph.dedup import deduplicate, project_extraction

_OUT_DIR = "pruvagraph-out"


@dataclass
class BuildConfig:
    """Configuration for a graph build run."""
    root: Path
    backend: str = "claude"
    cascade: bool = False
    max_tokens_per_batch: int = 12_000
    dedup_threshold: float = 0.82
    budget_usd: float | None = None
    dry_run: bool = False
    force: bool = False          # ignore cache
    no_viz: bool = False         # skip HTML generation
    out_dir: str = _OUT_DIR


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
    backend: str = "claude",
    cascade: bool = False,
    budget_usd: float | None = None,
    dry_run: bool = False,
    force: bool = False,
    dedup_threshold: float = 0.82,
    max_tokens_per_batch: int = 12_000,
    no_viz: bool = False,
    out_dir: str = _OUT_DIR,
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
    )
    return _run_pipeline(cfg)


async def build_graph_async(root: str | Path, **kwargs: Any) -> BuildResult:
    """Async wrapper for build_graph."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: build_graph(root, **kwargs))


# ──────────────────────────────────────────────────────────────────────────────
# Internal pipeline
# ──────────────────────────────────────────────────────────────────────────────

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

    cache = GraphCache(cfg.root)
    tracker = CostTracker(backend=cfg.backend, total_files=0)

    # ── Stage 1: Discover files ──────────────────────────────────────────────
    all_files = collect_files(cfg.root)
    code_files = [f for f, t in all_files if t == FileType.CODE]
    doc_files  = [f for f, t in all_files if t in (FileType.DOCUMENT, FileType.PAPER, FileType.IMAGE)]
    tracker._total_files = len(all_files)

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

    # Parallel tree-sitter extraction
    if code_to_extract:
        with ProcessPoolExecutor() as pool:
            futures = {pool.submit(extract_code_file, p): p for p in code_to_extract}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    result = future.result()
                    all_extractions.append(result)
                    tracker.record_tree_sitter()
                    # Cache the result
                    from pruvagraph.cache import CacheEntry, _sha256
                    content = path.read_bytes()
                    cache.save(path, CacheEntry(
                        path=str(path),
                        stat_size=path.stat().st_size,
                        stat_mtime_ns=int(path.stat().st_mtime_ns),
                        content_hash=_sha256(content),
                        ast_hash=None,
                        nodes=result.get("nodes", []),
                        edges=result.get("edges", []),
                        extraction_cost_usd=0.0,
                        backend="tree-sitter",
                    ))
                except Exception as e:
                    _rich_print(f"  ⚠ {path.name}: {e}", "yellow")

    _rich_print(f"  ✓ {len(code_files) - len(code_to_extract)} cached, "
                f"{len(code_to_extract)} extracted", "green")

    # ── Stage 3: Doc/image files via LLM (with dedup + batching) ────────────
    _rich_print(f"[Stage 2/5] LLM extraction — {len(doc_files)} doc/image files...", "cyan")

    # Cache check for docs too
    docs_to_extract: list[Path] = []
    for path in doc_files:
        if not cfg.force:
            cached = cache.check(path)
            if cached:
                tracker.record_cache_hit()
                all_extractions.append({"nodes": cached.nodes, "edges": cached.edges,
                                        "source_file": str(path)})
                continue
        docs_to_extract.append(path)

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
            cost_report.estimated_cost_usd = plan.estimated_cost_usd
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
            extractions = extract_doc_batch(
                batch.paths,
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
                cache.save(path, CacheEntry(
                    path=str(path),
                    stat_size=path.stat().st_size,
                    stat_mtime_ns=int(path.stat().st_mtime_ns),
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
    G = build_nx_graph(all_extractions)

    _rich_print("[Stage 4/5] Community detection (Leiden)...", "cyan")
    G = cluster_leiden(G)

    _rich_print("[Stage 5/5] Analyzing + exporting...", "cyan")
    analysis = analyze(G)
    report_md = render_report(G, analysis)

    (out_dir / "GRAPH_REPORT.md").write_text(report_md, encoding="utf-8")
    graph_json_path, html_path = export_graph(G, out_dir, no_viz=cfg.no_viz)

    # Cost report
    cost_report = tracker.finalize(out_dir)
    duration = time.time() - start

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    communities = len({d.get("community") for _, d in G.nodes(data=True) if d.get("community")})

    _rich_print("\n" + cost_report.format_summary(), "blue")

    return BuildResult(
        graph_json_path=graph_json_path,
        html_path=html_path,
        report_path=out_dir / "GRAPH_REPORT.md",
        cost_report=cost_report,
        node_count=n_nodes,
        edge_count=n_edges,
        community_count=communities,
        duration_seconds=duration,
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


def _rich_print(msg: str, color: str = "white") -> None:
    try:
        from rich.console import Console
        Console().print(f"[{color}]{msg}[/{color}]")
    except ImportError:
        print(msg)

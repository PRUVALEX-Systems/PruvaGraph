"""
Arch1 — Streaming Graph Build

Current behaviour: build finishes (30–120s) → THEN you can query.
After this layer:  query at second 3 while build continues in background.

How it works:
  1. Every N files processed → write graph_partial.json + build_status.json
  2. MCP server + query CLI use partial graph if full not yet ready
  3. After full build → overwrite graph.json, delete partials
  4. Status file tells VS Code extension what % is done

Status file format (pruvagraph-out/build_status.json):
  {
    "status": "building" | "complete" | "idle" | "error",
    "files_done": 47,
    "files_total": 500,
    "percent": 9,
    "started_at": "2026-06-15T10:30:00Z",
    "message": "Extracting batch 3/12..."
  }
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# ── Status writer ──────────────────────────────────────────────────────────────

class StreamStatus:
    """
    Writes build_status.json to disk during a streaming build.
    Used by VS Code extension for progress updates.
    """

    def __init__(self, out_dir: Path, files_total: int) -> None:
        self._path        = out_dir / "build_status.json"
        self._files_total = max(files_total, 1)
        self._files_done  = 0
        self._started_at  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._write("building", "Starting…")

    def update(self, files_done: int, message: str = "") -> None:
        self._files_done = files_done
        self._write("building", message)

    def complete(self) -> None:
        self._write("complete", "Build complete")

    def error(self, msg: str) -> None:
        self._write("error", msg)

    def _write(self, status: str, message: str) -> None:
        pct = int(100 * self._files_done / self._files_total)
        data = {
            "status":      status,
            "files_done":  self._files_done,
            "files_total": self._files_total,
            "percent":     pct,
            "started_at":  self._started_at,
            "message":     message,
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass


# ── Partial graph writer ───────────────────────────────────────────────────────

def write_partial_graph(
    extractions: list[dict[str, Any]],
    out_dir: Path,
) -> bool:
    """
    Build a minimal graph from current extractions and write it as graph_partial.json.
    Called periodically during a streaming build.

    Returns True if successful.
    """
    if not extractions:
        return False

    try:
        import networkx as nx

        from pruvagraph.build import build_nx_graph

        G = build_nx_graph(extractions)
        if G.number_of_nodes() == 0:
            return False

        partial_path = out_dir / "graph_partial.json"
        partial_path.write_text(
            json.dumps(nx.node_link_data(G), ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def cleanup_partial(out_dir: Path) -> None:
    """Remove partial graph files after full build completes."""
    for name in ("graph_partial.json",):
        p = out_dir / name
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# ── Graph reader (partial-aware) ──────────────────────────────────────────────

def load_best_graph(out_dir: Path) -> tuple[Any, bool]:
    """
    Load the best available graph. Prefers full graph, falls back to partial.

    Returns:
        (networkx_graph, is_partial)
        (None, False) if no graph available
    """
    import networkx as nx

    full_path    = out_dir / "graph.json"
    partial_path = out_dir / "graph_partial.json"

    if full_path.exists():
        try:
            G = nx.node_link_graph(json.loads(full_path.read_text(encoding="utf-8")))
            return G, False
        except Exception:
            pass

    if partial_path.exists():
        try:
            G = nx.node_link_graph(json.loads(partial_path.read_text(encoding="utf-8")))
            return G, True
        except Exception:
            pass

    return None, False


def get_build_status(out_dir: Path) -> dict:
    """Read current build_status.json. Returns default if not found."""
    status_path = out_dir / "build_status.json"
    if status_path.exists():
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "idle", "files_done": 0, "files_total": 0, "percent": 0}


def partial_graph_note(pct: int) -> str:
    """Warning prefix for partial graph answers."""
    return (
        f"⚠️  Note: Graph is {pct}% built — answering from partial data. "
        f"Run `pruvagraph .` to complete the build.\n\n"
    )

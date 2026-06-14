"""
File watcher — triggers incremental graph updates on file changes.

Uses ``watchdog`` (cross-platform, pip install watchdog).
Falls back to polling if watchdog is not available.

Incremental mode: only re-extracts files that changed since the last run.
This makes watch mode almost free: cache hit rate is ~99% per commit.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def watch_and_update(root: Path, out_dir: str = "pruvagraph-out") -> None:
    """
    Watch *root* for file changes and trigger incremental graph rebuilds.

    Blocks until Ctrl+C.
    """
    try:
        _watch_watchdog(root, out_dir)
    except ImportError:
        _watch_polling(root, out_dir)


# ──────────────────────────────────────────────────────────────────────────────
# watchdog-based (preferred — event-driven, no CPU waste)
# ──────────────────────────────────────────────────────────────────────────────

def _watch_watchdog(root: Path, out_dir: str) -> None:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent

    _debounce: dict[str, float] = {}
    DEBOUNCE_SECONDS = 2.0

    class Handler(FileSystemEventHandler):
        def on_modified(self, event: FileSystemEvent) -> None:
            if event.is_directory:
                return
            path = Path(str(event.src_path))
            _maybe_rebuild(root, path, _debounce, DEBOUNCE_SECONDS, out_dir)

        def on_created(self, event: FileSystemEvent) -> None:
            self.on_modified(event)

    observer = Observer()
    observer.schedule(Handler(), str(root), recursive=True)
    observer.start()

    print(f"👁  Watching {root} … (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


# ──────────────────────────────────────────────────────────────────────────────
# Polling fallback (slower, universal)
# ──────────────────────────────────────────────────────────────────────────────

def _watch_polling(root: Path, out_dir: str) -> None:
    from pruvagraph.detect import collect_files

    print(f"👁  Watching {root} (polling mode — install watchdog for better performance)")
    last_mtimes: dict[str, float] = {}

    try:
        while True:
            current: dict[str, float] = {}
            for path, _ in collect_files(root):
                try:
                    current[str(path)] = path.stat().st_mtime
                except OSError:
                    pass

            changed = [
                p for p, mt in current.items()
                if last_mtimes.get(p) != mt
            ]

            if changed:
                print(f"  ↻ {len(changed)} file(s) changed, rebuilding …")
                _rebuild(root, out_dir)

            last_mtimes = current
            time.sleep(3)

    except KeyboardInterrupt:
        print("\n👁  Stopped.")


# ──────────────────────────────────────────────────────────────────────────────
# Shared rebuild logic
# ──────────────────────────────────────────────────────────────────────────────

_WATCHED_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".go", ".rs", ".java", ".kt", ".swift",
    ".md", ".txt", ".yaml", ".toml", ".json",
})


def _maybe_rebuild(
    root: Path,
    changed_path: Path,
    debounce: dict[str, float],
    debounce_sec: float,
    out_dir: str,
) -> None:
    """Rebuild only if the file extension is worth tracking and debounce has elapsed."""
    if changed_path.suffix.lower() not in _WATCHED_EXTENSIONS:
        return

    # Skip pruvagraph output dir
    try:
        rel = changed_path.relative_to(root)
        if rel.parts and rel.parts[0] in ("pruvagraph-out", ".git", "node_modules", "__pycache__"):
            return
    except ValueError:
        pass

    now = time.time()
    key = str(changed_path)
    if now - debounce.get(key, 0) < debounce_sec:
        return
    debounce[key] = now

    print(f"  ↻ Changed: {changed_path.name}")
    _rebuild(root, out_dir)


def _rebuild(root: Path, out_dir: str) -> None:
    """Trigger an incremental rebuild (cache-aware — only changed files re-extracted)."""
    try:
        from pruvagraph.pipeline import build_graph
        result = build_graph(root, no_viz=True, out_dir=out_dir)
        cr = result.cost_report
        print(
            f"  ✓ {result.node_count} nodes · {result.edge_count} edges "
            f"· saved ${cr.cost_saved_usd:.4f} ({cr.savings_pct:.0f}%)"
        )
    except Exception as e:
        print(f"  ⚠ Rebuild error: {e}")

"""
M1 — Monorepo Router.

Auto-detects monorepo structures and builds per-package knowledge graphs
with cross-package import edges.

Supported layouts (detection in priority order):
  1. pnpm         — pnpm-workspace.yaml
  2. Nx           — nx.json
  3. Lerna        — lerna.json
  4. Turborepo    — turbo.json
  5. Rush         — rush.json
  6. npm/yarn     — package.json "workspaces" field
  7. Python       — multiple pyproject.toml / setup.py in subdirs
  8. Generic      — packages/ apps/ libs/ services/ dirs with ≥2 sub-packages

Cost: pure filesystem + regex — zero LLM calls.

Usage:
    from pruvagraph.monorepo import detect_monorepo, build_monorepo_graph

    layout = detect_monorepo(Path("."))
    if layout:
        result = build_monorepo_graph(Path("."), cfg)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PackageInfo:
    """Metadata for a single package within a monorepo."""
    name:         str
    root:         Path
    language:     str             # "python" | "javascript" | "mixed" | "unknown"
    package_file: Path | None = None   # package.json / pyproject.toml

    def __repr__(self) -> str:
        return f"<Package {self.name!r} at {self.root}>"


@dataclass
class MonorepoLayout:
    """Detected monorepo structure."""
    root:     Path
    tool:     str                    # pnpm | nx | lerna | turborepo | rush | npm-workspaces | python | generic
    packages: list[PackageInfo]      = field(default_factory=list)

    def summary(self) -> str:
        return f"{self.tool} monorepo: {len(self.packages)} packages at {self.root}"


@dataclass
class MonorepoBuildResult:
    """Result of building all packages in a monorepo."""
    layout:              MonorepoLayout
    package_results:     dict[str, Any]          = field(default_factory=dict)  # pkg_name → BuildResult
    cross_package_edges: list[tuple[str, str, str]] = field(default_factory=list)
    cross_graph_path:    Path | None              = None

    def summary(self) -> str:
        n = len(self.package_results)
        e = len(self.cross_package_edges)
        return f"Monorepo built: {n} packages, {e} cross-package edges"


# ──────────────────────────────────────────────────────────────────────────────
# Detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_monorepo(root: Path) -> MonorepoLayout | None:
    """
    Detect if root is a monorepo and return its layout, or None for single-repo.

    Checks config files first (most reliable), then well-known directory names.
    """
    root = Path(root).resolve()

    # 1. pnpm workspaces
    pnpm_ws = root / "pnpm-workspace.yaml"
    if pnpm_ws.exists():
        packages = _parse_pnpm_workspace(root, pnpm_ws)
        if packages:
            return MonorepoLayout(root=root, tool="pnpm", packages=packages)

    # 2. Nx
    if (root / "nx.json").exists():
        packages = _scan_dirs(root, ["apps", "libs", "packages"])
        if packages:
            return MonorepoLayout(root=root, tool="nx", packages=packages)

    # 3. Lerna
    lerna_json = root / "lerna.json"
    if lerna_json.exists():
        packages = _parse_lerna(root, lerna_json)
        if packages:
            return MonorepoLayout(root=root, tool="lerna", packages=packages)

    # 4. Turborepo
    if (root / "turbo.json").exists():
        packages = _parse_npm_workspaces(root)
        if packages:
            return MonorepoLayout(root=root, tool="turborepo", packages=packages)

    # 5. Rush
    rush_json = root / "rush.json"
    if rush_json.exists():
        packages = _parse_rush(root, rush_json)
        if packages:
            return MonorepoLayout(root=root, tool="rush", packages=packages)

    # 6. npm/yarn workspaces in root package.json
    root_pkg = root / "package.json"
    if root_pkg.exists():
        packages = _parse_npm_workspaces(root)
        if packages:
            return MonorepoLayout(root=root, tool="npm-workspaces", packages=packages)

    # 7. Python monorepo (≥2 sub-dirs with pyproject.toml or setup.py)
    py_packages = _detect_python_monorepo(root)
    if py_packages:
        return MonorepoLayout(root=root, tool="python", packages=py_packages)

    # 8. Generic: well-known directory names with ≥2 sub-packages
    generic = _scan_dirs(root, ["packages", "apps", "libs", "services", "modules"])
    if len(generic) >= 2:
        return MonorepoLayout(root=root, tool="generic", packages=generic)

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Layout-specific parsers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_pnpm_workspace(root: Path, ws_file: Path) -> list[PackageInfo]:
    patterns: list[str] = []
    try:
        import yaml  # optional — falls back to regex if not installed
        data = yaml.safe_load(ws_file.read_text(encoding="utf-8"))
        patterns = data.get("packages", [])
    except ImportError:
        text = ws_file.read_text(encoding="utf-8")
        patterns = re.findall(r"^\s*-\s+['\"]?([^'\"#\n]+?)['\"]?\s*$", text, re.MULTILINE)
    except Exception:
        return []

    return _resolve_glob_patterns(root, patterns)


def _parse_npm_workspaces(root: Path) -> list[PackageInfo]:
    pkg_json = root / "package.json"
    if not pkg_json.exists():
        return []
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        workspaces = data.get("workspaces", [])
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])
    except Exception:
        return []
    return _resolve_glob_patterns(root, workspaces)


def _parse_lerna(root: Path, lerna_json: Path) -> list[PackageInfo]:
    try:
        data = json.loads(lerna_json.read_text(encoding="utf-8"))
        patterns = data.get("packages", ["packages/*"])
    except Exception:
        patterns = ["packages/*"]
    return _resolve_glob_patterns(root, patterns)


def _parse_rush(root: Path, rush_json: Path) -> list[PackageInfo]:
    try:
        # Rush JSON allows // comments — strip before parsing
        text = rush_json.read_text(encoding="utf-8")
        text = re.sub(r"//[^\n]*", "", text)
        data = json.loads(text)
        projects = data.get("projects", [])
    except Exception:
        return []

    packages: list[PackageInfo] = []
    for proj in projects:
        folder = proj.get("projectFolder", "")
        if folder:
            pkg_dir = root / folder
            if pkg_dir.is_dir():
                packages.append(_make_package(pkg_dir, name=proj.get("packageName")))
    return packages


def _detect_python_monorepo(root: Path) -> list[PackageInfo]:
    """Find subdirectories that each contain their own pyproject.toml or setup.py."""
    packages: list[PackageInfo] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "pyproject.toml").exists() or (child / "setup.py").exists():
            packages.append(_make_package(child))
    # Only return if it looks like an intentional monorepo (≥2 packages)
    return packages if len(packages) >= 2 else []


def _scan_dirs(root: Path, dir_names: list[str]) -> list[PackageInfo]:
    """Scan root for well-known monorepo parent directories."""
    packages: list[PackageInfo] = []
    for dir_name in dir_names:
        parent = root / dir_name
        if not parent.is_dir():
            continue
        for pkg_dir in sorted(parent.iterdir()):
            if pkg_dir.is_dir() and not pkg_dir.name.startswith("."):
                packages.append(_make_package(pkg_dir))
    return packages


def _resolve_glob_patterns(root: Path, patterns: list[str]) -> list[PackageInfo]:
    """Resolve glob patterns (e.g. 'packages/*') to PackageInfo list."""
    packages: list[PackageInfo] = []
    for pattern in patterns:
        pattern = str(pattern).strip().rstrip("/*").rstrip("\\*")
        # Handle direct path (no glob)
        candidate = root / pattern
        if candidate.is_dir():
            # Check if it IS a package itself
            if (candidate / "package.json").exists() or (candidate / "pyproject.toml").exists():
                packages.append(_make_package(candidate))
            else:
                # It's a parent — iterate children
                for pkg_dir in sorted(candidate.iterdir()):
                    if pkg_dir.is_dir() and not pkg_dir.name.startswith("."):
                        packages.append(_make_package(pkg_dir))
    return packages


def _make_package(pkg_dir: Path, name: str | None = None) -> PackageInfo:
    """Create a PackageInfo by inspecting a directory."""
    pkg_name: str | None = name
    pkg_file: Path | None = None
    lang = "unknown"

    # JavaScript / TypeScript
    npm_pkg = pkg_dir / "package.json"
    if npm_pkg.exists():
        pkg_file = npm_pkg
        lang = "javascript"
        if not pkg_name:
            try:
                data = json.loads(npm_pkg.read_text(encoding="utf-8"))
                pkg_name = data.get("name")
            except Exception:
                pass

    # Python
    py_pkg = pkg_dir / "pyproject.toml"
    if py_pkg.exists():
        lang = "python" if lang == "unknown" else "mixed"
        if not pkg_file:
            pkg_file = py_pkg
        if not pkg_name:
            try:
                text = py_pkg.read_text(encoding="utf-8")
                m = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
                pkg_name = m.group(1) if m else None
            except Exception:
                pass

    setup_py = pkg_dir / "setup.py"
    if setup_py.exists() and lang == "unknown":
        lang = "python"
        if not pkg_name:
            try:
                text = setup_py.read_text(encoding="utf-8")
                m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', text)
                pkg_name = m.group(1) if m else None
            except Exception:
                pass

    return PackageInfo(
        name=pkg_name or pkg_dir.name,
        root=pkg_dir,
        language=lang,
        package_file=pkg_file,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Cross-package dependency detection
# ──────────────────────────────────────────────────────────────────────────────

def find_cross_package_edges(
    packages: list[PackageInfo],
) -> list[tuple[str, str, str]]:
    """
    Detect cross-package imports by scanning source files.

    Returns list of (src_pkg_name, tgt_pkg_name, "imports_from") tuples.
    Only unique edges are returned.
    """
    cross_edges: set[tuple[str, str, str]] = set()

    for src_pkg in packages:
        for src_file in _iter_source_files(src_pkg.root):
            content = _safe_read(src_file)
            if not content:
                continue
            for tgt_pkg in packages:
                if tgt_pkg.name == src_pkg.name:
                    continue
                if _imports_package(content, tgt_pkg.name, src_file.suffix):
                    cross_edges.add((src_pkg.name, tgt_pkg.name, "imports_from"))

    return sorted(cross_edges)


def _imports_package(content: str, pkg_name: str, ext: str) -> bool:
    """Return True if content contains an import from pkg_name."""
    escaped = re.escape(pkg_name)
    patterns = [
        rf"from\s+{escaped}[\.\s]",                         # Python: from pkg import ...
        rf"import\s+{escaped}[\.\s]",                       # Python: import pkg.sub
        rf'from\s+["\']@?{escaped}["\'/]',                  # JS/TS: from 'pkg' or '@scope/pkg'
        rf'require\s*\(\s*["\']@?{escaped}["\']',           # JS: require('pkg')
    ]
    for pattern in patterns:
        if re.search(pattern, content):
            return True
    return False


_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "pruvagraph-out",
}
_SOURCE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt", ".swift",
}


def _iter_source_files(root: Path):
    """Yield source files under root, skipping common non-source directories."""
    for p in root.rglob("*"):
        if any(s in p.parts for s in _SKIP_DIRS):
            continue
        if p.is_file() and p.suffix in _SOURCE_EXTS:
            yield p


def _safe_read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Monorepo graph build orchestration
# ──────────────────────────────────────────────────────────────────────────────

def build_monorepo_graph(root: Path, cfg: Any) -> MonorepoBuildResult:
    """
    Build per-package graphs and a root cross-package graph.

    Args:
        root: Repository root.
        cfg:  BuildConfig instance (from pipeline.py).

    Returns:
        MonorepoBuildResult with per-package BuildResults + cross-package edges.
    """
    from pruvagraph.pipeline import BuildConfig, _run_pipeline  # local import

    layout = detect_monorepo(root)
    if not layout:
        raise ValueError(f"{root} is not a detected monorepo. Run without --monorepo.")

    _rich_print(f"\n[M1] {layout.summary()}", "cyan")

    import json as _json

    package_results: dict[str, Any] = {}
    for pkg in layout.packages:
        _rich_print(f"  → Building package: {pkg.name} ({pkg.root})", "cyan")
        pkg_cfg = BuildConfig(
            root=pkg.root,
            backend=cfg.backend,
            cascade=cfg.cascade,
            budget_usd=None,
            dry_run=cfg.dry_run,
            force=cfg.force,
            dedup_threshold=cfg.dedup_threshold,
            max_tokens_per_batch=cfg.max_tokens_per_batch,
            no_viz=True,      # no HTML per-package (build root cross-graph instead)
            out_dir=cfg.out_dir,
            streaming=False,
        )
        try:
            result = _run_pipeline(pkg_cfg)
            package_results[pkg.name] = result
            _rich_print(f"    ✓ {pkg.name}: {result.node_count} nodes, {result.edge_count} edges", "green")
        except Exception as e:
            _rich_print(f"    ✗ {pkg.name} failed: {e}", "red")

    # Detect cross-package edges
    cross_edges = find_cross_package_edges(layout.packages)
    if cross_edges:
        _rich_print(f"  [M1] {len(cross_edges)} cross-package import edges detected", "green")

    # Write cross-package graph JSON (lightweight — just packages + edges)
    out_dir = root / cfg.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cross_data = {
        "monorepo_tool": layout.tool,
        "packages": [
            {
                "name":     p.name,
                "root":     str(p.root.relative_to(root)),
                "language": p.language,
                "graph":    str((p.root / cfg.out_dir / "graph.json").relative_to(root))
                            if (p.root / cfg.out_dir / "graph.json").exists() else None,
            }
            for p in layout.packages
        ],
        "cross_edges": [
            {"source": e[0], "target": e[1], "relation": e[2]}
            for e in cross_edges
        ],
    }
    cross_graph_path = out_dir / "cross_graph.json"
    cross_graph_path.write_text(_json.dumps(cross_data, indent=2), encoding="utf-8")
    _rich_print(f"  [M1] Cross-package graph → {cross_graph_path}", "green")

    return MonorepoBuildResult(
        layout=layout,
        package_results=package_results,
        cross_package_edges=cross_edges,
        cross_graph_path=cross_graph_path,
    )


def _rich_print(msg: str, color: str = "white") -> None:
    try:
        from rich.console import Console
        Console().print(f"[{color}]{msg}[/{color}]")
    except ImportError:
        print(msg)

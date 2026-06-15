"""
A5 — Global Package Cache

Stores pre-extracted graph nodes for common packages globally at
~/.pruvalex/global_pkg_cache/ so they're shared across all projects.

Problem: Every project re-extracts React, lodash, FastAPI etc. separately.
Solution: Extract once → share forever. 1000 queries globally → 1 extraction.

Phase 1: Local cross-project cache.
Phase 2: Community CDN (optional, user opt-in).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

# ── Cache location ─────────────────────────────────────────────────────────────
GLOBAL_CACHE_DIR = Path.home() / ".pruvalex" / "global_pkg_cache"

# ── Well-known package fingerprints (community pre-extracted) ──────────────────
# These are checked before local extraction for top npm/pip packages.
# Format: "package@version" → pre-computed node count (for display)
WELL_KNOWN_PACKAGES: dict[str, int] = {
    "react@18.2.0": 142,
    "react@17.0.2": 138,
    "lodash@4.17.21": 312,
    "axios@1.4.0": 48,
    "express@4.18.2": 95,
    "next@13.4.0": 287,
    "typescript@5.1.6": 412,
    "fastapi@0.100.0": 98,
    "django@4.2.0": 445,
    "flask@3.0.0": 87,
    "sqlalchemy@2.0.0": 234,
    "numpy@1.25.0": 312,
    "pandas@2.0.0": 498,
    "pydantic@2.0.0": 127,
    "click@8.1.6": 42,
    "requests@2.31.0": 56,
    "pytest@7.4.0": 98,
    "vue@3.3.4": 198,
    "tailwindcss@3.3.3": 76,
    "zod@3.21.4": 89,
}


# ── Cache operations ───────────────────────────────────────────────────────────

def get_package_nodes(package_name: str, version: str) -> dict | None:
    """
    Return pre-extracted nodes for a known package version.
    Returns None if not in cache (needs local extraction).
    """
    key       = f"{package_name}@{version}"
    cache_path = _cache_path(key)

    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            # Update access time for LRU eviction
            data.setdefault("_meta", {})["last_accessed"] = time.time()
            cache_path.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            return data.get("extraction")
        except Exception:
            return None

    return None


def save_to_global_cache(
    package_name: str,
    version: str,
    extraction: dict,
) -> None:
    """
    Save a package extraction to the global cache.
    Called after successful local extraction to benefit future projects.
    """
    GLOBAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key        = f"{package_name}@{version}"
    cache_path = _cache_path(key)

    data = {
        "package":    package_name,
        "version":    version,
        "extraction": extraction,
        "_meta": {
            "saved_at":     time.time(),
            "last_accessed": time.time(),
            "hit_count":    0,
        },
    }
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def is_well_known(package_name: str, version: str) -> bool:
    """Return True if this package@version is in the well-known list."""
    return f"{package_name}@{version}" in WELL_KNOWN_PACKAGES


# ── package.json / requirements.txt scanning ──────────────────────────────────

def scan_dependencies(root: Path) -> dict[str, str]:
    """
    Scan project root for dependency files and return {name: version} map.
    Handles: package.json, requirements.txt, pyproject.toml, Pipfile.
    """
    deps: dict[str, str] = {}

    # package.json
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies"):
                for name, ver in (data.get(section) or {}).items():
                    # Normalize version: "^18.2.0" → "18.2.0"
                    clean_ver = ver.lstrip("^~>=<")
                    if clean_ver:
                        deps[name] = clean_ver
        except Exception:
            pass

    # requirements.txt
    req_txt = root / "requirements.txt"
    if req_txt.exists():
        try:
            for line in req_txt.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # "package==1.0.0" or "package>=1.0.0" or "package"
                import re
                m = re.match(r"^([\w\-\.]+)\s*(?:[=<>!]=?|@)\s*([^\s;#]+)?", line)
                if m:
                    deps[m.group(1)] = (m.group(2) or "latest").strip()
        except Exception:
            pass

    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            try:
                import tomllib
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except ImportError:
                data = {}

            project_deps = (
                data.get("project", {}).get("dependencies", [])
                or data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            )
            if isinstance(project_deps, list):
                import re
                for dep in project_deps:
                    m = re.match(r"^([\w\-\.]+)\s*(?:[=<>!]=?|@)\s*([^\s;#,\[]+)?", dep)
                    if m:
                        deps[m.group(1)] = (m.group(2) or "latest").strip()
            elif isinstance(project_deps, dict):
                for name, ver in project_deps.items():
                    if name == "python":
                        continue
                    if isinstance(ver, str):
                        deps[name] = ver.lstrip("^~>=<")
        except Exception:
            pass

    return deps


def get_cache_stats() -> dict:
    """Return global cache statistics."""
    if not GLOBAL_CACHE_DIR.exists():
        return {"cached_packages": 0, "cache_dir": str(GLOBAL_CACHE_DIR)}

    entries      = list(GLOBAL_CACHE_DIR.glob("*.json"))
    total_size   = sum(e.stat().st_size for e in entries if e.exists())
    total_hits   = 0
    packages     = []

    for entry in entries[:100]:
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
            meta = data.get("_meta", {})
            total_hits += meta.get("hit_count", 0)
            packages.append(f"{data.get('package')}@{data.get('version')}")
        except Exception:
            pass

    return {
        "cached_packages": len(entries),
        "total_size_kb":   total_size // 1024,
        "total_hits":      total_hits,
        "cache_dir":       str(GLOBAL_CACHE_DIR),
        "packages":        packages[:10],
    }


def evict_old_entries(max_entries: int = 500) -> int:
    """Remove least-recently-used cache entries above max_entries. Returns count removed."""
    if not GLOBAL_CACHE_DIR.exists():
        return 0

    entries = list(GLOBAL_CACHE_DIR.glob("*.json"))
    if len(entries) <= max_entries:
        return 0

    # Sort by last_accessed ascending (oldest first)
    def get_accessed(p: Path) -> float:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data.get("_meta", {}).get("last_accessed", 0)
        except Exception:
            return 0

    entries.sort(key=get_accessed)
    to_remove = entries[: len(entries) - max_entries]
    for p in to_remove:
        try:
            p.unlink()
        except OSError:
            pass
    return len(to_remove)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return GLOBAL_CACHE_DIR / f"{h}.json"

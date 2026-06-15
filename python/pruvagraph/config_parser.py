"""
N5 — Structural Config Parser

Parses JSON / YAML / TOML config files into graph nodes without any LLM call.
Handles special cases: package.json, docker-compose, pyproject.toml, GitHub Actions.

Estimated savings: All config-type files skip LLM entirely (10–25% of repo files).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def parse_config_file(path: Path) -> dict | None:
    """
    Parse a config file into {nodes, edges} without any LLM.
    Returns None if this file type is unknown → falls back to LLM.
    """
    ext = path.suffix.lower()
    name = path.name.lower()

    try:
        if ext == ".json":
            return _parse_json(path)
        if ext in (".yaml", ".yml"):
            return _parse_yaml(path)
        if ext == ".toml":
            return _parse_toml(path)
        if ext in (".env", ".env.example", ".env.local"):
            return _parse_dotenv(path)
        if name in ("dockerfile", ".dockerignore"):
            return _parse_dockerfile(path)
    except Exception:
        return None  # Parsing failed → let LLM handle

    return None


# ── JSON ────────────────────────────────────────────────────────────────────────

def _parse_json(path: Path) -> dict:
    data: dict = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    nodes, edges = [], []
    file_id = str(path)

    if path.name == "package.json":
        return _parse_package_json(path, data)

    if path.name == "tsconfig.json" or path.name.startswith("tsconfig"):
        return _parse_tsconfig(path, data)

    # Generic JSON
    nodes.append({
        "id": file_id, "label": path.name, "type": "config",
        "file": str(path),
        "summary": f"JSON config with {len(data)} top-level keys: {', '.join(list(data.keys())[:5])}",
    })
    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


def _parse_package_json(path: Path, data: dict) -> dict:
    nodes, edges = [], []
    file_id = str(path)
    name    = data.get("name", path.parent.name)
    version = data.get("version", "?")
    desc    = data.get("description", "")

    nodes.append({
        "id": file_id, "label": name, "type": "module",
        "file": str(path),
        "summary": desc or f"npm package {name}@{version}",
    })

    # Dependencies
    for dep_section in ("dependencies", "devDependencies", "peerDependencies"):
        relation = "depends_on" if dep_section == "dependencies" else "dev_depends_on"
        for dep, ver in (data.get(dep_section) or {}).items():
            dep_id = f"pkg:{dep}"
            if not any(n["id"] == dep_id for n in nodes):
                nodes.append({
                    "id": dep_id, "label": dep, "type": "external",
                    "summary": f"npm {dep}@{ver}",
                })
            edges.append({"source": file_id, "target": dep_id, "relation": relation})

    # Scripts
    for script_name, cmd in (data.get("scripts") or {}).items():
        sid = f"{file_id}::script:{script_name}"
        nodes.append({
            "id": sid, "label": script_name, "type": "function",
            "file": str(path),
            "summary": f"npm script: {str(cmd)[:80]}",
        })
        edges.append({"source": file_id, "target": sid, "relation": "defines"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


def _parse_tsconfig(path: Path, data: dict) -> dict:
    nodes, edges = [], []
    file_id = str(path)
    co = data.get("compilerOptions", {})
    target = co.get("target", "?")
    module = co.get("module", "?")

    nodes.append({
        "id": file_id, "label": path.name, "type": "config",
        "file": str(path),
        "summary": f"TypeScript config: target={target}, module={module}",
    })

    # Path aliases → edges
    paths_map: dict = co.get("paths", {})
    for alias, targets in paths_map.items():
        alias_id = f"{file_id}::alias:{alias}"
        nodes.append({
            "id": alias_id, "label": alias, "type": "module",
            "file": str(path), "summary": f"TS path alias → {targets[0] if targets else '?'}",
        })
        edges.append({"source": file_id, "target": alias_id, "relation": "defines"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── YAML ────────────────────────────────────────────────────────────────────────

def _parse_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    except ImportError:
        data = _simple_yaml_keys(path.read_text(encoding="utf-8", errors="replace"))

    nodes, edges = [], []
    file_id = str(path)
    name = path.name.lower()

    # docker-compose
    if "services" in data and ("docker" in name or "compose" in name):
        nodes.append({
            "id": file_id, "label": path.name, "type": "config",
            "file": str(path), "summary": f"Docker Compose: {len(data['services'])} services",
        })
        for svc, cfg in (data.get("services") or {}).items():
            cfg = cfg or {}
            image = cfg.get("image", "custom")
            svc_id = f"{file_id}::svc:{svc}"
            nodes.append({
                "id": svc_id, "label": svc, "type": "class",
                "file": str(path), "summary": f"Docker service: {svc} ({image})",
            })
            edges.append({"source": file_id, "target": svc_id, "relation": "defines"})
            for dep in (cfg.get("depends_on") or []):
                edges.append({"source": svc_id, "target": f"{file_id}::svc:{dep}", "relation": "depends_on"})
        return {"nodes": nodes, "edges": edges, "source_file": str(path)}

    # GitHub Actions workflow
    if "jobs" in data and ".github" in str(path):
        jobs = data.get("jobs", {})
        nodes.append({
            "id": file_id, "label": path.stem, "type": "config",
            "file": str(path), "summary": f"GitHub Actions: {len(jobs)} jobs",
        })
        for job_name, job_cfg in jobs.items():
            job_id = f"{file_id}::job:{job_name}"
            runs_on = (job_cfg or {}).get("runs-on", "?")
            nodes.append({
                "id": job_id, "label": job_name, "type": "function",
                "file": str(path), "summary": f"CI job on {runs_on}",
            })
            edges.append({"source": file_id, "target": job_id, "relation": "defines"})
        return {"nodes": nodes, "edges": edges, "source_file": str(path)}

    # Generic YAML
    keys = list((data or {}).keys())[:6]
    nodes.append({
        "id": file_id, "label": path.name, "type": "config",
        "file": str(path), "summary": f"YAML config: {', '.join(str(k) for k in keys)}",
    })
    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


def _simple_yaml_keys(text: str) -> dict:
    """Minimal YAML key extractor without pyyaml dependency."""
    keys = re.findall(r"^(\w[\w-]*):", text, re.MULTILINE)
    return {k: None for k in keys}


# ── TOML ────────────────────────────────────────────────────────────────────────

def _parse_toml(path: Path) -> dict:
    try:
        try:
            import tomllib  # Python 3.11+
            data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
        except ImportError:
            import tomli as tomllib  # type: ignore
            data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        data = {}

    nodes, edges = [], []
    file_id = str(path)

    if path.name == "pyproject.toml":
        proj = data.get("project", data.get("tool", {}).get("poetry", {}))
        pname   = proj.get("name", path.parent.name)
        version = proj.get("version", "?")
        desc    = proj.get("description", "")

        nodes.append({
            "id": file_id, "label": pname, "type": "module",
            "file": str(path),
            "summary": desc or f"Python package {pname}@{version}",
        })

        deps = proj.get("dependencies", {})
        if isinstance(deps, list):
            deps = {d.split(">=")[0].split("==")[0].strip(): "?" for d in deps}
        for dep, ver in deps.items():
            if dep == "python":
                continue
            dep_id = f"pkg:{dep}"
            nodes.append({
                "id": dep_id, "label": dep, "type": "external",
                "summary": f"Python package {dep}",
            })
            edges.append({"source": file_id, "target": dep_id, "relation": "depends_on"})
    else:
        sections = list(data.keys())[:5]
        nodes.append({
            "id": file_id, "label": path.name, "type": "config",
            "file": str(path),
            "summary": f"TOML config: sections={', '.join(sections)}",
        })

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── .env ────────────────────────────────────────────────────────────────────────

def _parse_dotenv(path: Path) -> dict:
    """Extract env var names (not values) as concept nodes."""
    content = path.read_text(encoding="utf-8", errors="replace")
    keys = re.findall(r"^([A-Z_][A-Z0-9_]{2,})\s*=", content, re.MULTILINE)

    file_id = str(path)
    nodes = [{
        "id": file_id, "label": path.name, "type": "config",
        "file": str(path),
        "summary": f"Environment config: {len(keys)} variables",
    }]
    edges = []

    for key in keys[:20]:
        kid = f"{file_id}::{key}"
        nodes.append({
            "id": kid, "label": key, "type": "concept",
            "file": str(path), "summary": f"Env variable: {key}",
        })
        edges.append({"source": file_id, "target": kid, "relation": "defines"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


def _parse_dockerfile(path: Path) -> dict:
    content = path.read_text(encoding="utf-8", errors="replace")
    file_id = str(path)

    from_images = re.findall(r"^FROM\s+(\S+)", content, re.MULTILINE | re.I)
    expose_ports = re.findall(r"^EXPOSE\s+(\d+)", content, re.MULTILINE | re.I)
    re.search(r"^(?:CMD|ENTRYPOINT)\s+(.+)$", content, re.MULTILINE | re.I)

    nodes = [{
        "id": file_id, "label": "Dockerfile", "type": "config",
        "file": str(path),
        "summary": (f"Docker image from {from_images[0] if from_images else '?'}"
                    + (f", ports: {','.join(expose_ports)}" if expose_ports else "")),
    }]
    edges = []

    for img in from_images:
        img_id = f"docker:{img}"
        nodes.append({"id": img_id, "label": img, "type": "external",
                      "summary": f"Base Docker image: {img}"})
        edges.append({"source": file_id, "target": img_id, "relation": "extends"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── File-type suitability check ─────────────────────────────────────────────────

CONFIG_EXTENSIONS = frozenset({
    ".json", ".yaml", ".yml", ".toml",
    ".env", ".env.example", ".env.local", ".env.test",
})

CONFIG_NAMES = frozenset({
    "dockerfile", ".dockerignore", ".editorconfig",
    ".gitattributes", ".npmrc", ".yarnrc",
})


def is_parseable_config(path: Path) -> bool:
    """Return True if this file can be handled by parse_config_file()."""
    return (
        path.suffix.lower() in CONFIG_EXTENSIONS
        or path.name.lower() in CONFIG_NAMES
    )

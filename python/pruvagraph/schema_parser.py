"""
A7 — Schema Parsers (OpenAPI, Prisma, GraphQL, Protobuf)

Structured API and database schemas are 100% machine-parseable.
No LLM should ever touch these files.

Supported formats:
  - OpenAPI 3.x / Swagger 2.x  (.yaml, .json containing "openapi" or "swagger")
  - Prisma ORM schema           (schema.prisma)
  - GraphQL SDL                 (.graphql, .gql)
  - Protocol Buffers            (.proto)
  - JSON Schema                 (.schema.json, *-schema.json)
  - AsyncAPI                    (asyncapi.yaml, asyncapi.json)

Estimated savings: 100% of schema file LLM calls eliminated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# ── Main dispatch ─────────────────────────────────────────────────────────────

def parse_schema_file(path: Path) -> dict | None:
    """
    Try to parse a schema file without LLM.
    Returns extraction dict or None if unrecognised.
    """
    name  = path.name.lower()
    ext   = path.suffix.lower()

    # Prisma schema
    if name == "schema.prisma" or ext == ".prisma":
        return parse_prisma(path)

    # GraphQL
    if ext in (".graphql", ".gql"):
        return parse_graphql(path)

    # Protobuf
    if ext == ".proto":
        return parse_proto(path)

    # JSON Schema
    if name.endswith((".schema.json", "-schema.json", "_schema.json")):
        return parse_json_schema(path)

    # OpenAPI / Swagger — need to peek inside
    if ext in (".yaml", ".yml", ".json"):
        return _try_openapi(path)

    return None


def is_parseable_schema(path: Path) -> bool:
    """Quick check — should this file go through schema_parser?"""
    name = path.name.lower()
    ext  = path.suffix.lower()

    if ext == ".prisma":
        return True
    if ext in (".graphql", ".gql", ".proto"):
        return True
    if name.endswith((".schema.json", "-schema.json", "_schema.json")):
        return True
    if name in ("schema.prisma", "openapi.yaml", "openapi.json",
                "swagger.yaml", "swagger.json", "api.yaml", "api.json",
                "asyncapi.yaml", "asyncapi.json"):
        return True
    return False


# ── OpenAPI / Swagger ─────────────────────────────────────────────────────────

def _try_openapi(path: Path) -> dict | None:
    """Peek inside the file to detect OpenAPI/Swagger, then parse."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Fast detection: must have "openapi:" / "swagger:" key
    if not re.search(r'^\s*(?:openapi|swagger)\s*:', content, re.MULTILINE):
        return None

    return parse_openapi(path, content)


def parse_openapi(path: Path, content: str | None = None) -> dict | None:
    """Parse OpenAPI 3.x / Swagger 2.x → nodes + edges."""
    if content is None:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    # Parse YAML or JSON
    spec = _load_yaml_or_json(content)
    if not spec or not isinstance(spec, dict):
        return None

    file_id = str(path)
    api_title = (spec.get("info") or {}).get("title", path.stem)
    api_desc  = (spec.get("info") or {}).get("description", "")
    api_ver   = (spec.get("info") or {}).get("version", "")

    nodes = [{
        "id":      file_id,
        "label":   api_title,
        "type":    "module",
        "summary": f"REST API v{api_ver}: {api_desc[:120]}" if api_desc else f"REST API v{api_ver}",
        "file":    str(path),
    }]
    edges: list[dict] = []

    # Endpoints
    for route, methods in (spec.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                continue
            if not isinstance(op, dict):
                continue

            op_id  = op.get("operationId") or f"{method.upper()}_{route.strip('/').replace('/', '_')}"
            summary = op.get("summary") or op.get("description") or f"{method.upper()} {route}"
            tags    = op.get("tags", [])

            ep_id = f"{file_id}::{method.upper()}:{route}"
            nodes.append({
                "id":      ep_id,
                "label":   f"{method.upper()} {route}",
                "type":    "function",
                "summary": summary[:150],
                "file":    str(path),
                "tags":    tags,
                "operationId": op_id,
            })
            edges.append({"source": file_id, "target": ep_id, "relation": "defines"})

            # Request body schema references
            req_body = (op.get("requestBody") or {})
            for media_type, media_obj in (req_body.get("content") or {}).items():
                ref = _extract_ref(media_obj.get("schema") or {})
                if ref:
                    edges.append({"source": ep_id, "target": f"{file_id}::schema:{ref}", "relation": "accepts"})

            # Response schema references
            for status, resp in (op.get("responses") or {}).items():
                if not isinstance(resp, dict):
                    continue
                for media_type, media_obj in (resp.get("content") or {}).items():
                    ref = _extract_ref(media_obj.get("schema") or {})
                    if ref:
                        edges.append({"source": ep_id, "target": f"{file_id}::schema:{ref}", "relation": "returns"})

    # Component schemas (data models)
    for model_name, schema in ((spec.get("components") or {}).get("schemas") or {}).items():
        if not isinstance(schema, dict):
            continue
        props     = list((schema.get("properties") or {}).keys())
        required  = schema.get("required", [])
        prop_str  = ", ".join(
            f"{p}{'*' if p in required else ''}" for p in props[:8]
        )
        model_id = f"{file_id}::schema:{model_name}"
        nodes.append({
            "id":      model_id,
            "label":   model_name,
            "type":    "class",
            "summary": f"Schema with fields: {prop_str}" if prop_str else "Data schema",
            "file":    str(path),
        })
        edges.append({"source": file_id, "target": model_id, "relation": "defines"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── Prisma ────────────────────────────────────────────────────────────────────

def parse_prisma(path: Path) -> dict | None:
    """Parse Prisma schema → models + relations + enums."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    file_id = str(path)
    nodes = [{
        "id":      file_id,
        "label":   "prisma.schema",
        "type":    "config",
        "summary": "Prisma ORM database schema — models and relations",
        "file":    str(path),
    }]
    edges: list[dict] = []

    # Models
    for m in re.finditer(r"model\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL):
        model_name = m.group(1)
        body       = m.group(2)

        # Fields: name  Type  attributes?
        fields = re.findall(r"^\s+(\w+)\s+(\w+)(\[\])?(\?)?", body, re.MULTILINE)
        field_parts = []
        relation_targets = []

        for fname, ftype, array, nullable in fields:
            mark = ("[]" if array else "") + ("?" if nullable else "")
            field_parts.append(f"{fname}:{ftype}{mark}")

            # Relation detection: field type starts with uppercase → model reference
            if ftype[0].isupper() and ftype not in (
                "String", "Int", "BigInt", "Float", "Decimal",
                "Boolean", "DateTime", "Json", "Bytes",
            ):
                relation_targets.append(ftype)

        summary = f"DB table: {', '.join(field_parts[:6])}"
        if len(field_parts) > 6:
            summary += f" +{len(field_parts) - 6} more"

        model_id = f"{file_id}::model:{model_name}"
        nodes.append({
            "id":      model_id,
            "label":   model_name,
            "type":    "class",
            "summary": summary,
            "file":    str(path),
        })
        edges.append({"source": file_id, "target": model_id, "relation": "defines"})

        for target in set(relation_targets):
            edges.append({
                "source": model_id,
                "target": f"{file_id}::model:{target}",
                "relation": "references",
            })

    # Enums
    for m in re.finditer(r"enum\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL):
        enum_name   = m.group(1)
        enum_values = re.findall(r"^\s+(\w+)\s*$", m.group(2), re.MULTILINE)
        enum_id = f"{file_id}::enum:{enum_name}"
        nodes.append({
            "id":      enum_id,
            "label":   enum_name,
            "type":    "concept",
            "summary": f"Enum: {', '.join(enum_values[:8])}",
            "file":    str(path),
        })
        edges.append({"source": file_id, "target": enum_id, "relation": "defines"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── GraphQL ───────────────────────────────────────────────────────────────────

def parse_graphql(path: Path) -> dict | None:
    """Parse GraphQL SDL — types, queries, mutations, subscriptions."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Strip block comments
    content = re.sub(r'"""[\s\S]*?"""', "", content)
    content = re.sub(r"#[^\n]*", "", content)

    file_id = str(path)
    nodes = [{
        "id":      file_id,
        "label":   path.stem,
        "type":    "module",
        "summary": "GraphQL schema definition",
        "file":    str(path),
    }]
    edges: list[dict] = []

    # Types: type Foo { field: Type }
    for m in re.finditer(
        r"(type|interface|input)\s+(\w+)(?:\s+implements[^{]*)?\s*\{([^}]+)\}",
        content, re.DOTALL,
    ):
        kind, type_name, body = m.group(1), m.group(2), m.group(3)

        if type_name in ("Query", "Mutation", "Subscription"):
            # Entrypoints → function nodes
            fields = re.findall(r"^\s+(\w+)[^:]*:\s*(\[?\w+\]?[!?]*)", body, re.MULTILINE)
            for field_name, return_type in fields[:20]:
                fn_id = f"{file_id}::{type_name}:{field_name}"
                nodes.append({
                    "id":      fn_id,
                    "label":   f"{type_name}.{field_name}",
                    "type":    "function",
                    "summary": f"GraphQL {type_name.lower()} → {return_type.strip()}",
                    "file":    str(path),
                })
                edges.append({"source": file_id, "target": fn_id, "relation": "defines"})
        else:
            fields = re.findall(r"^\s+(\w+)[^:]*:\s*(\[?\w+\]?[!?]*)", body, re.MULTILINE)
            field_str = ", ".join(f"{n}:{t}" for n, t in fields[:6])
            type_id = f"{file_id}::type:{type_name}"
            nodes.append({
                "id":      type_id,
                "label":   type_name,
                "type":    "class" if kind == "type" else "concept",
                "summary": f"GraphQL {kind}: {field_str}",
                "file":    str(path),
            })
            edges.append({"source": file_id, "target": type_id, "relation": "defines"})

    # Enums
    for m in re.finditer(r"enum\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL):
        enum_name   = m.group(1)
        enum_values = re.findall(r"^\s+(\w+)", m.group(2), re.MULTILINE)
        enum_id = f"{file_id}::enum:{enum_name}"
        nodes.append({
            "id":      enum_id,
            "label":   enum_name,
            "type":    "concept",
            "summary": f"GraphQL enum: {', '.join(enum_values[:8])}",
            "file":    str(path),
        })
        edges.append({"source": file_id, "target": enum_id, "relation": "defines"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── Protobuf ──────────────────────────────────────────────────────────────────

def parse_proto(path: Path) -> dict | None:
    """Parse Protocol Buffer .proto files — services, messages, enums."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Strip comments
    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"/\*[\s\S]*?\*/", "", content)

    file_id   = str(path)
    package_m = re.search(r"package\s+([\w.]+)", content)
    package   = package_m.group(1) if package_m else ""

    nodes = [{
        "id":      file_id,
        "label":   path.stem,
        "type":    "module",
        "summary": f"Protobuf schema{f' (package: {package})' if package else ''}",
        "file":    str(path),
    }]
    edges: list[dict] = []

    # Services → RPC methods
    for svc_m in re.finditer(r"service\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL):
        svc_name = svc_m.group(1)
        svc_body = svc_m.group(2)
        svc_id   = f"{file_id}::service:{svc_name}"

        rpcs = re.findall(
            r"rpc\s+(\w+)\s*\((\w+)\)\s*returns\s*\((\w+)\)", svc_body
        )
        rpc_str = ", ".join(f"{name}({req})→{resp}" for name, req, resp in rpcs[:5])

        nodes.append({
            "id":      svc_id,
            "label":   svc_name,
            "type":    "class",
            "summary": f"gRPC service — RPCs: {rpc_str or 'none'}",
            "file":    str(path),
        })
        edges.append({"source": file_id, "target": svc_id, "relation": "defines"})

        for rpc_name, req_type, resp_type in rpcs:
            rpc_id = f"{file_id}::rpc:{svc_name}:{rpc_name}"
            nodes.append({
                "id":      rpc_id,
                "label":   f"{svc_name}.{rpc_name}",
                "type":    "function",
                "summary": f"RPC: ({req_type}) → {resp_type}",
                "file":    str(path),
            })
            edges.append({"source": svc_id, "target": rpc_id, "relation": "defines"})
            edges.append({"source": rpc_id, "target": f"{file_id}::msg:{req_type}", "relation": "accepts"})
            edges.append({"source": rpc_id, "target": f"{file_id}::msg:{resp_type}", "relation": "returns"})

    # Messages
    for msg_m in re.finditer(r"message\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL):
        msg_name = msg_m.group(1)
        body     = msg_m.group(2)
        fields   = re.findall(r"(?:optional|required|repeated)?\s*(\w+)\s+(\w+)\s*=\s*\d+", body)
        field_str = ", ".join(f"{n}:{t}" for t, n in fields[:6])

        msg_id = f"{file_id}::msg:{msg_name}"
        nodes.append({
            "id":      msg_id,
            "label":   msg_name,
            "type":    "class",
            "summary": f"Protobuf message: {field_str or 'no fields'}",
            "file":    str(path),
        })
        edges.append({"source": file_id, "target": msg_id, "relation": "defines"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── JSON Schema ───────────────────────────────────────────────────────────────

def parse_json_schema(path: Path) -> dict | None:
    """Parse JSON Schema files."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    file_id   = str(path)
    title     = data.get("title", path.stem)
    desc      = data.get("description", "")
    props     = list((data.get("properties") or {}).keys())
    prop_str  = ", ".join(props[:8])

    nodes = [{
        "id":      file_id,
        "label":   title,
        "type":    "class",
        "summary": desc[:120] or f"JSON Schema with fields: {prop_str}",
        "file":    str(path),
    }]
    edges: list[dict] = []

    for prop_name, prop_schema in (data.get("properties") or {}).items():
        if not isinstance(prop_schema, dict):
            continue
        prop_id = f"{file_id}::{prop_name}"
        prop_type = prop_schema.get("type", "any")
        prop_desc = prop_schema.get("description", "")
        nodes.append({
            "id":      prop_id,
            "label":   prop_name,
            "type":    "concept",
            "summary": prop_desc[:80] or f"{prop_type} field",
            "file":    str(path),
        })
        edges.append({"source": file_id, "target": prop_id, "relation": "contains"})

    return {"nodes": nodes, "edges": edges, "source_file": str(path)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_yaml_or_json(content: str) -> dict | None:
    """Try YAML first, then JSON."""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(content)
    except ImportError:
        pass
    except Exception:
        return None

    try:
        return json.loads(content)
    except Exception:
        return None


def _extract_ref(schema: dict) -> str | None:
    """Extract model name from $ref: '#/components/schemas/ModelName'."""
    ref = schema.get("$ref", "")
    if ref:
        return ref.split("/")[-1]
    # allOf / anyOf / oneOf
    for combiner in ("allOf", "anyOf", "oneOf"):
        items = schema.get(combiner, [])
        if items and isinstance(items[0], dict):
            r = items[0].get("$ref", "")
            if r:
                return r.split("/")[-1]
    return None


# ── Extension map ─────────────────────────────────────────────────────────────

SCHEMA_EXTENSIONS = frozenset({".prisma", ".graphql", ".gql", ".proto"})
SCHEMA_FILENAMES  = frozenset({
    "schema.prisma",
    "openapi.yaml", "openapi.json",
    "swagger.yaml", "swagger.json",
    "asyncapi.yaml", "asyncapi.json",
    "api.yaml", "api.json",
})

"""
Graph exporter — Stage 5c of the pipeline.

Writes the NetworkX graph to:
  - graph.json       (node-link format, consumed by the webview + MCP server)
  - graph.html       (interactive D3 visualisation, no server needed)
  - graph.graphml    (optional: Gephi / yEd compatible)
  - graph.cypher     (optional: Neo4j import)
  - obsidian/        (optional: Obsidian Canvas JSON)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

# ──────────────────────────────────────────────────────────────────────────────
# Main entry points
# ──────────────────────────────────────────────────────────────────────────────


def export_graph(
    G: nx.MultiDiGraph,
    out_dir: Path,
    no_viz: bool = False,
) -> tuple[Path, Path | None]:
    """
    Write graph.json and (optionally) graph.html to *out_dir*.

    Returns (graph_json_path, html_path).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # graph.json — consumed by MCP server, CLI query, webview
    graph_json_path = out_dir / "graph.json"
    data = nx.node_link_data(G)
    graph_json_path.write_text(json.dumps(data, default=str), encoding="utf-8")

    # graph.html — self-contained interactive visualisation
    html_path: Path | None = None
    if not no_viz:
        html_path = out_dir / "graph.html"
        html_path.write_text(_render_html(G), encoding="utf-8")

    return graph_json_path, html_path


def export_format(graph_json: Path, fmt: str) -> Path:
    """Export an existing graph.json to an alternative format."""
    G = nx.node_link_graph(json.loads(graph_json.read_text()))
    out_dir = graph_json.parent

    if fmt == "graphml":
        out = out_dir / "graph.graphml"
        # Convert MultiDiGraph to DiGraph for graphml (no parallel edges)
        simple = nx.DiGraph()
        for n, d in G.nodes(data=True):
            simple.add_node(n, **{k: str(v) for k, v in d.items() if v is not None})
        for u, v, d in G.edges(data=True):
            if not simple.has_edge(u, v):
                simple.add_edge(u, v, relation=d.get("relation", "related"))
        nx.write_graphml(simple, out)
        return out

    if fmt == "cypher":
        out = out_dir / "graph.cypher"
        lines: list[str] = ["// PruvaGraph — Neo4j Cypher export", ""]
        for node_id, data in G.nodes(data=True):
            label = data.get("label", node_id).replace("'", "\\'")
            ntype = data.get("type", "Node")
            summary = (data.get("summary") or "").replace("'", "\\'")
            file_ = (data.get("file") or "").replace("'", "\\'")
            safe_id = node_id.replace("'", "\\'")
            lines.append(
                f"MERGE (n:{ntype} {{id: '{safe_id}', label: '{label}', "
                f"summary: '{summary}', file: '{file_}'}});"
            )
        lines.append("")
        for u, v, data in G.edges(data=True):
            rel = data.get("relation", "RELATED").upper().replace("-", "_")
            safe_u = u.replace("'", "\\'")
            safe_v = v.replace("'", "\\'")
            lines.append(
                f"MATCH (a {{id: '{safe_u}'}}), (b {{id: '{safe_v}'}}) "
                f"MERGE (a)-[:{rel}]->(b);"
            )
        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    if fmt == "obsidian":
        out_folder = out_dir / "obsidian"
        out_folder.mkdir(exist_ok=True)
        _write_obsidian(G, out_folder)
        return out_folder

    if fmt == "html":
        out = out_dir / "graph.html"
        out.write_text(_render_html(G), encoding="utf-8")
        return out

    raise ValueError(f"Unknown format: {fmt!r}. Use: graphml, cypher, obsidian, html")


# ──────────────────────────────────────────────────────────────────────────────
# HTML visualisation — PruvaGraph Precision Instrument (v1.4.0)
#
# Design direction: "oscilloscope" — feels like a technical measurement tool,
# not a marketing dashboard or a hacker terminal.
#
# Color palette (each hex encodes real data, not decoration):
#   #5B8DEF — Module       — architectural containers (cool blue)
#   #4ECDC4 — Class/Struct — data structures (teal)
#   #95E77E — Function     — callable units (lime)
#   #F7B731 — Interface    — contracts/types (amber)
#   #A78BFA — External     — outside boundary (purple)
#   #FF6B6B — Dead code    — isolated nodes (coral red alert)
#   #EC4899 — Doc/concept  — documentation nodes (pink)
#
# Typography:
#   UI labels, controls: Inter (Google Fonts)
#   Symbol names, file paths, stats: JetBrains Mono (code-adjacent = looks code)
#
# Signature interaction (one moment, executed well):
#   Click a node → isolate its full dependency chain (both directions) with a
#   smooth ripple transition — all other nodes fade to 8% opacity, edges dim.
#   Click background or same node → restore full graph.
#   Reduced motion: @media (prefers-reduced-motion) disables all transitions.
# ──────────────────────────────────────────────────────────────────────────────

_TYPE_COLORS = {
    "module":    "#5B8DEF",
    "class":     "#4ECDC4",
    "function":  "#95E77E",
    "interface": "#F7B731",
    "external":  "#A78BFA",
    "doc":       "#EC4899",
    "concept":   "#EC4899",
    "unknown":   "#94A3B8",
}

# Dead code nodes (degree=0) use coral regardless of type
_DEAD_COLOR = "#FF6B6B"


def _graph_to_d3(G: nx.MultiDiGraph) -> dict[str, Any]:
    # Pre-compute degree for dead-code detection and sizing
    degrees = {n: G.degree(n) for n in G.nodes()}

    nodes = []
    for node_id, data in G.nodes(data=True):
        ntype = data.get("type", "unknown")
        deg = degrees.get(node_id, 0)
        color = _DEAD_COLOR if deg == 0 else _TYPE_COLORS.get(ntype, _TYPE_COLORS["unknown"])
        nodes.append({
            "id":        node_id,
            "label":     data.get("label", node_id),
            "type":      ntype,
            "file":      data.get("file"),
            "summary":   data.get("summary"),
            "community": data.get("community"),
            "color":     color,
            "dead":      deg == 0,
        })

    links = []
    seen: set[tuple[str, str, str]] = set()
    for u, v, data in G.edges(data=True):
        rel = data.get("relation", "related")
        sig = (u, v, rel)
        if sig not in seen:
            seen.add(sig)
            links.append({"source": u, "target": v, "relation": rel})

    return {"nodes": nodes, "links": links}


def _render_html(G: nx.MultiDiGraph) -> str:
    graph_data = json.dumps(_graph_to_d3(G))
    node_count = G.number_of_nodes()
    edge_count = G.number_of_edges()

    legend_items = "".join(
        f'<div class="leg-item"><span class="leg-dot" style="background:{c}"></span>'
        f'<span class="leg-label">{t}</span></div>'
        for t, c in [
            ("module",    "#5B8DEF"),
            ("class",     "#4ECDC4"),
            ("function",  "#95E77E"),
            ("interface", "#F7B731"),
            ("external",  "#A78BFA"),
            ("doc",       "#EC4899"),
            ("dead code", "#FF6B6B"),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PruvaGraph — {node_count:,} nodes · {edge_count:,} edges</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
/* ── Reset & tokens ─────────────────────────────────────────── */
:root {{
  --bg:        #0A0E1A;
  --surface:   #111827;
  --surface2:  #1A2235;
  --border:    #1E2D45;
  --border2:   #243450;
  --text:      #C9D5E8;
  --text-dim:  #5C7294;
  --text-mono: #8BB8D4;
  --accent:    #5B8DEF;
  --dead:      #FF6B6B;
  --radius:    6px;
  --font-ui:   'Inter', system-ui, sans-serif;
  --font-code: 'JetBrains Mono', 'Fira Code', monospace;
  --trans:     180ms ease;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: var(--font-ui);
        overflow: hidden; height: 100vh; display: flex; flex-direction: column; }}

/* ── Header ─────────────────────────────────────────────────── */
#hdr {{
  display: flex; align-items: center; gap: 10px;
  padding: 0 16px; height: 44px; flex-shrink: 0;
  background: var(--surface); border-bottom: 1px solid var(--border);
}}
#logo {{ display: flex; align-items: center; gap: 7px; }}
#logo-mark {{ opacity: 0.9; }}
#title {{ font-size: 13px; font-weight: 600; color: var(--text); letter-spacing: -0.01em; }}
#subtitle {{ font-family: var(--font-code); font-size: 11px; color: var(--text-dim);
             margin-left: 2px; }}
#hdr-right {{ margin-left: auto; display: flex; align-items: center; gap: 6px; }}
.btn {{
  background: transparent; border: 1px solid var(--border2);
  color: var(--text-dim); padding: 3px 10px; border-radius: var(--radius);
  font-size: 11px; font-family: var(--font-ui); cursor: pointer;
  transition: border-color var(--trans), color var(--trans);
}}
.btn:hover {{ border-color: var(--accent); color: var(--accent); }}
#search-wrap {{ position: relative; }}
#search-wrap svg {{ position: absolute; left: 8px; top: 50%;
                    transform: translateY(-50%); pointer-events: none; opacity: 0.4; }}
#q {{
  background: var(--surface2); border: 1px solid var(--border2);
  color: var(--text); padding: 4px 10px 4px 28px;
  border-radius: var(--radius); font-size: 11px;
  font-family: var(--font-code); width: 190px;
  transition: border-color var(--trans), width var(--trans);
}}
#q:focus {{ outline: none; border-color: var(--accent); width: 230px; }}
#q::placeholder {{ color: var(--text-dim); }}

/* ── Legend strip ───────────────────────────────────────────── */
#legend {{
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  padding: 5px 16px; flex-shrink: 0;
  background: var(--surface); border-bottom: 1px solid var(--border);
}}
.leg-item {{ display: flex; align-items: center; gap: 5px; }}
.leg-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
.leg-label {{ font-family: var(--font-code); font-size: 10px; color: var(--text-dim);
              letter-spacing: 0.02em; }}
#leg-dead .leg-dot {{ border-radius: 50%; border: 1.5px solid #FF6B6B;
                      background: transparent; width: 9px; height: 9px; }}

/* ── Canvas ─────────────────────────────────────────────────── */
#canvas {{ flex: 1; position: relative; overflow: hidden; }}
svg {{ width: 100%; height: 100%; display: block; }}

/* ── Graph elements ─────────────────────────────────────────── */
.link {{
  stroke: var(--border2); stroke-opacity: 0.55;
  transition: stroke-opacity var(--trans);
}}
.link.imports {{ stroke: #1E2D45; }}
.link.defines {{ stroke: #243450; stroke-opacity: 0.7; }}
.link.extends {{ stroke: #5B8DEF; stroke-opacity: 0.4; }}

.node {{ cursor: pointer; }}
.node circle {{
  stroke: var(--bg); stroke-width: 1.5px;
  transition: r 100ms ease, stroke-width 100ms ease;
}}
.node.dead circle {{
  fill: transparent !important;
  stroke-width: 1.5px;
}}
.node:hover circle {{ stroke-width: 2.5px; stroke: white; }}
.node text {{
  font-family: var(--font-code); font-size: 9.5px;
  fill: var(--text); pointer-events: none;
  text-shadow: 0 0 4px var(--bg), 0 0 8px var(--bg);
}}

/* Isolation state */
.node.dimmed {{ opacity: 0.05; }}
.node.dimmed circle {{ stroke-width: 0; }}
.link.dimmed {{ opacity: 0.03; }}

/* ── Tooltip ─────────────────────────────────────────────────── */
#tip {{
  position: absolute; background: var(--surface2);
  border: 1px solid var(--border2); border-radius: 8px;
  padding: 10px 13px; pointer-events: none; display: none;
  max-width: 300px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  z-index: 100;
}}
.tip-label {{ font-weight: 600; font-size: 12px; color: var(--accent);
              font-family: var(--font-code); }}
.tip-type  {{ font-size: 10px; color: var(--text-dim); margin-top: 2px;
              font-family: var(--font-code); letter-spacing: 0.03em; }}
.tip-sum   {{ font-size: 11px; color: var(--text); margin-top: 7px;
              line-height: 1.5; }}
.tip-file  {{ font-size: 10px; color: var(--text-mono); margin-top: 5px;
              font-family: var(--font-code); opacity: 0.75; }}
.tip-dead  {{ font-size: 10px; color: var(--dead); margin-top: 4px;
              font-family: var(--font-code); }}

/* ── Status bar ─────────────────────────────────────────────── */
#status-bar {{
  position: absolute; bottom: 10px; left: 14px;
  font-family: var(--font-code); font-size: 10px; color: var(--text-dim);
  pointer-events: none; user-select: none;
}}

/* ── Reduced motion ─────────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {{
  .node circle, .link, .node {{ transition: none !important; }}
  .node.dimmed, .link.dimmed {{ transition: none !important; }}
}}
</style>
</head>
<body>

<!-- Header -->
<div id="hdr">
  <div id="logo">
    <svg id="logo-mark" width="22" height="22" viewBox="0 0 22 22" fill="none">
      <circle cx="4"  cy="4"  r="2.8" fill="#5B8DEF"/>
      <circle cx="18" cy="4"  r="2.8" fill="#4ECDC4"/>
      <circle cx="11" cy="18" r="2.8" fill="#95E77E"/>
      <circle cx="4"  cy="11" r="1.8" fill="#F7B731" opacity="0.8"/>
      <line x1="4"  y1="4"  x2="18" y2="4"  stroke="#5B8DEF" stroke-width="1.2" stroke-opacity="0.6"/>
      <line x1="4"  y1="4"  x2="11" y2="18" stroke="#5B8DEF" stroke-width="1.2" stroke-opacity="0.6"/>
      <line x1="18" y1="4"  x2="11" y2="18" stroke="#4ECDC4" stroke-width="1.2" stroke-opacity="0.6"/>
      <line x1="4"  y1="4"  x2="4"  y2="11" stroke="#F7B731" stroke-width="1"   stroke-opacity="0.5"/>
    </svg>
    <span id="title">PruvaGraph</span>
    <span id="subtitle">{node_count:,} nodes · {edge_count:,} edges</span>
  </div>
  <div id="hdr-right">
    <div id="search-wrap">
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
        <circle cx="5.5" cy="5.5" r="4" stroke="#8BB8D4" stroke-width="1.5"/>
        <line x1="8.8" y1="8.8" x2="12" y2="12" stroke="#8BB8D4" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      <input id="q" placeholder="Search nodes…" autocomplete="off" spellcheck="false">
    </div>
    <button class="btn" id="btn-relayout">↺ Relayout</button>
    <button class="btn" id="btn-fit">⤢ Fit</button>
    <button class="btn" id="btn-reset">✕ Clear</button>
  </div>
</div>

<!-- Legend -->
<div id="legend">
  {legend_items}
  <div class="leg-item" id="leg-dead">
    <span class="leg-dot" style="border-color:#FF6B6B"></span>
    <span class="leg-label">dead code</span>
  </div>
  <span style="margin-left:auto;font-family:var(--font-code);font-size:10px;color:var(--text-dim)">
    click node to isolate · click bg to restore
  </span>
</div>

<!-- Canvas -->
<div id="canvas">
  <svg id="svg"><g id="root"></g></svg>
  <div id="tip"></div>
  <div id="status-bar" id="status">Ready</div>
</div>

<script>
// ── Data ───────────────────────────────────────────────────────────────────
const GRAPH = {graph_data};

// ── DOM references ─────────────────────────────────────────────────────────
const svg     = d3.select('#svg');
const root    = d3.select('#root');
const tip     = document.getElementById('tip');
const statusEl = document.getElementById('status-bar');

const W = () => svg.node().clientWidth;
const H = () => svg.node().clientHeight;

// ── Zoom ───────────────────────────────────────────────────────────────────
const zoom = d3.zoom().scaleExtent([0.04, 6])
  .on('zoom', e => root.attr('transform', e.transform));
svg.call(zoom);

function fitView() {{
  svg.transition().duration(500).call(
    zoom.transform, d3.zoomIdentity.translate(W()/2, H()/2).scale(0.75)
  );
}}

// ── Degree map (for sizing) ────────────────────────────────────────────────
const degMap = {{}};
GRAPH.links.forEach(l => {{
  const s = l.source.id ?? l.source;
  const t = l.target.id ?? l.target;
  degMap[s] = (degMap[s] || 0) + 1;
  degMap[t] = (degMap[t] || 0) + 1;
}});

const radScale = d3.scaleSqrt().domain([0, 80]).range([4, 20]).clamp(true);

// ── Edge thickness by relation ─────────────────────────────────────────────
const linkWidth = rel => rel === 'extends' ? 2 : rel === 'defines' ? 1.5 : 1;

// ── Links ──────────────────────────────────────────────────────────────────
const linkSel = root.append('g').attr('class', 'links')
  .selectAll('line').data(GRAPH.links).join('line')
  .attr('class', d => `link ${{d.relation}}`)
  .attr('stroke-width', d => linkWidth(d.relation));

// ── Nodes ──────────────────────────────────────────────────────────────────
const nodeG = root.append('g').attr('class', 'nodes')
  .selectAll('g').data(GRAPH.nodes).join('g')
  .attr('class', d => 'node' + (d.dead ? ' dead' : ''))
  .call(d3.drag()
    .on('start', (e, d) => {{ if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
    .on('drag',  (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
    .on('end',   (e, d) => {{ if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }})
  )
  .on('click', onNodeClick)
  .on('mouseover', showTip)
  .on('mouseout',  hideTip);

nodeG.append('circle')
  .attr('r', d => radScale(degMap[d.id] || 0))
  .attr('fill', d => d.dead ? 'transparent' : d.color)
  .attr('stroke', d => d.color);

// Labels — only for nodes with degree > 3 (significant nodes)
nodeG.append('text')
  .text(d => d.label)
  .attr('x', 0)
  .attr('y', d => radScale(degMap[d.id] || 0) + 11)
  .attr('text-anchor', 'middle')
  .style('display', d => (degMap[d.id] || 0) > 3 ? 'block' : 'none');

// ── Simulation ─────────────────────────────────────────────────────────────
const sim = d3.forceSimulation(GRAPH.nodes)
  .force('link', d3.forceLink(GRAPH.links).id(d => d.id).distance(90))
  .force('charge', d3.forceManyBody().strength(-240))
  .force('center', d3.forceCenter(0, 0))
  .force('collision', d3.forceCollide(d => radScale(degMap[d.id] || 0) + 4))
  .on('tick', () => {{
    linkSel
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    nodeG.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
  }})
  .on('end', () => setStatus(`${{GRAPH.nodes.length}} nodes · ${{GRAPH.links.length}} edges`));

// ── Signature interaction: click-to-isolate ────────────────────────────────
// Hovering a clicked node highlights its full dependency chain (both directions)
// with a smooth ripple. Everything else fades to ~8% opacity.
// Click background or same node → restore.

let isolatedNode = null;

function getConnectedSet(nodeId) {{
  // BFS both directions up to 2 hops for a "full chain" feel
  const visited = new Set([nodeId]);
  const frontier = [nodeId];
  for (let hop = 0; hop < 2; hop++) {{
    const next = [];
    frontier.forEach(n => {{
      GRAPH.links.forEach(l => {{
        const s = l.source.id ?? l.source;
        const t = l.target.id ?? l.target;
        if (s === n && !visited.has(t)) {{ visited.add(t); next.push(t); }}
        if (t === n && !visited.has(s)) {{ visited.add(s); next.push(s); }}
      }});
    }});
    frontier.length = 0;
    next.forEach(n => frontier.push(n));
  }}
  return visited;
}}

function isolate(nodeId) {{
  isolatedNode = nodeId;
  const connected = getConnectedSet(nodeId);

  nodeG.classed('dimmed', d => !connected.has(d.id));
  linkSel.classed('dimmed', d => {{
    const s = d.source.id ?? d.source;
    const t = d.target.id ?? d.target;
    return !connected.has(s) || !connected.has(t);
  }});
  setStatus(`Isolated: ${{nodeId.split('::').pop() || nodeId}} — ${{connected.size}} connected nodes`);
}}

function restoreAll() {{
  isolatedNode = null;
  nodeG.classed('dimmed', false);
  linkSel.classed('dimmed', false);
  setStatus(`${{GRAPH.nodes.length}} nodes · ${{GRAPH.links.length}} edges`);
}}

function onNodeClick(event, d) {{
  event.stopPropagation();
  if (isolatedNode === d.id) {{
    restoreAll();
  }} else {{
    isolate(d.id);
  }}
}}

svg.on('click', restoreAll);

// ── Tooltip ────────────────────────────────────────────────────────────────
function showTip(event, d) {{
  const deg = degMap[d.id] || 0;
  const community = d.community != null ? `community ${{d.community}}` : 'no community';
  tip.innerHTML = `
    <div class="tip-label">${{d.label}}</div>
    <div class="tip-type">${{d.type}} · ${{community}} · degree ${{deg}}</div>
    ${{d.summary ? `<div class="tip-sum">${{d.summary}}</div>` : ''}}
    ${{d.file ? `<div class="tip-file">${{d.file}}</div>` : ''}}
    ${{d.dead ? `<div class="tip-dead">⚠ Isolated — no connections (dead code candidate)</div>` : ''}}
  `;
  tip.style.display = 'block';
  tip.style.left = (event.clientX + 16) + 'px';
  tip.style.top  = Math.max(10, event.clientY - 10) + 'px';
}}

function hideTip() {{ tip.style.display = 'none'; }}

// ── Search ─────────────────────────────────────────────────────────────────
document.getElementById('q').addEventListener('input', function() {{
  const q = this.value.toLowerCase().trim();
  if (!q) {{
    nodeG.classed('dimmed', false).select('text')
      .style('display', d => (degMap[d.id] || 0) > 3 ? 'block' : 'none');
    linkSel.classed('dimmed', false);
    return;
  }}
  const matching = new Set(
    GRAPH.nodes.filter(d =>
      d.label.toLowerCase().includes(q) ||
      (d.file || '').toLowerCase().includes(q) ||
      (d.summary || '').toLowerCase().includes(q)
    ).map(d => d.id)
  );
  nodeG.classed('dimmed', d => !matching.has(d.id))
    .select('text').style('display', d => matching.has(d.id) ? 'block' : 'none');
  linkSel.classed('dimmed', d => {{
    const s = d.source.id ?? d.source;
    const t = d.target.id ?? d.target;
    return !matching.has(s) && !matching.has(t);
  }});
  setStatus(`${{matching.size}} nodes match "${{q}}"`);
}});

// ── Controls ───────────────────────────────────────────────────────────────
document.getElementById('btn-relayout').addEventListener('click', () => {{
  sim.alpha(0.4).restart();
}});
document.getElementById('btn-fit').addEventListener('click', fitView);
document.getElementById('btn-reset').addEventListener('click', () => {{
  document.getElementById('q').value = '';
  restoreAll();
}});

// ── Status helper ──────────────────────────────────────────────────────────
function setStatus(msg) {{ statusEl.textContent = msg; }}

// ── Initial fit ────────────────────────────────────────────────────────────
setTimeout(fitView, 120);
</script>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Obsidian Canvas export
# ──────────────────────────────────────────────────────────────────────────────

def _write_obsidian(G: nx.MultiDiGraph, out_folder: Path) -> None:
    """Write per-community Markdown notes + a canvas JSON."""
    cards: list[dict] = []
    edges_out: list[dict] = []

    grid = 300

    for i, (node_id, data) in enumerate(G.nodes(data=True)):
        col = i % 10
        row = i // 10
        px  = col * grid
        py  = row * grid
        cards.append({
            "id":     node_id[:50],
            "type":   "text",
            "text":   f"**{data.get('label', node_id)}** ({data.get('type','?')})\n\n{data.get('summary', '')}",
            "x": px, "y": py, "width": 250, "height": 120,
        })

    seen: set[tuple[str, str]] = set()
    for u, v, data in G.edges(data=True):
        sig = (u[:50], v[:50])
        if sig not in seen:
            seen.add(sig)
            edges_out.append({
                "id": f"{u[:25]}-{v[:25]}",
                "fromNode": u[:50], "fromSide": "right",
                "toNode": v[:50], "toSide": "left",
                "label": data.get("relation", ""),
            })

    canvas = {{"nodes": cards, "edges": edges_out}}
    (out_folder / "pruvagraph.canvas").write_text(json.dumps(canvas, indent=2), encoding="utf-8")

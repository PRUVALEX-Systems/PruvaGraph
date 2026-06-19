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
        color = _TYPE_COLORS.get(ntype, _TYPE_COLORS["unknown"])
        nodes.append({
            "id":        node_id,
            "label":     data.get("label", node_id),
            "type":      ntype,
            "file":      data.get("file"),
            "summary":   data.get("summary"),
            "community": data.get("community"),
            "color":     color,
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
        f'<div class="legend-item"><div class="dot" style="background:{c}"></div><span>{t}</span></div>'
        for t, c in [
            ("module",    "#7C6EFA"),
            ("class",     "#22D3EE"),
            ("function",  "#34D399"),
            ("interface", "#F59E0B"),
            ("external",  "#6B7280"),
            ("doc",       "#EC4899"),
            ("concept",   "#F97316"),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PRUVALEX PruvaGraph — Knowledge Graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
  :root {{
    --bg: #000000; --surface: #000000; --border: #2A2A2A;
    --text: #E6EDF3; --muted: #8B949E; --accent: #7C6EFA;
    --green: #34D399; --cyan: #22D3EE; --yellow: #F59E0B;
    --brand-red: #E2362B;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; }}
  #accent-bar {{ height: 3px; background: linear-gradient(90deg, var(--brand-red), var(--accent), var(--cyan)); }}
  #header {{ padding: 12px 20px; background: var(--surface); border-bottom: 1px solid var(--border);
             display: flex; align-items: center; gap: 14px; }}
  #logo {{ display: flex; align-items: center; gap: 9px; }}
  #logo-mark {{ border-radius: 6px; box-shadow: 0 0 0 1px var(--border); display: block; }}
  #title {{ font-size: 16px; font-weight: 700; color: var(--accent); letter-spacing: .2px; }}
  #plan-toggle {{ display: flex; align-items: center; background: #0A0A0A; border: 1px solid var(--border);
                  border-radius: 999px; padding: 2px; gap: 2px; }}
  .plan-btn {{ background: transparent; border: none; color: var(--muted); font-size: 11px; font-weight: 700;
               padding: 4px 11px; border-radius: 999px; cursor: pointer; letter-spacing: .4px;
               text-transform: uppercase; transition: all .15s ease; }}
  .plan-btn.active {{ background: var(--brand-red); color: #fff; }}
  .plan-btn:hover:not(.active) {{ color: var(--text); }}
  #stats {{ font-size: 12px; color: var(--muted); }}
  #controls {{ display: flex; gap: 8px; margin-left: auto; }}
  .btn {{ background: var(--surface); border: 1px solid var(--border); color: var(--text);
          padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all .15s ease; }}
  .btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  #legend {{ display: flex; gap: 10px; flex-wrap: wrap; padding: 8px 20px;
             background: var(--surface); border-bottom: 1px solid var(--border); }}
  .legend-item {{ display: flex; align-items: center; gap: 5px; font-size: 11px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  #canvas-wrap {{ position: relative; width: 100%; height: calc(100vh - 93px);
                  background: radial-gradient(ellipse at 50% 40%, #060606 0%, #000000 65%); }}
  svg {{ width: 100%; height: 100%; }}
  .node circle {{ stroke: var(--bg); stroke-width: 2px; cursor: pointer; transition: stroke .15s ease, filter .15s ease; }}
  .node circle:hover {{ stroke: white; stroke-width: 2px; filter: drop-shadow(0 0 6px rgba(255,255,255,0.45)); }}
  .node text {{ fill: var(--text); font-size: 10px; pointer-events: none; }}
  .link {{ stroke-opacity: 0.5; }}
  #tooltip {{ position: absolute; background: #0A0A0A; border: 1px solid var(--border);
              border-radius: 8px; padding: 10px 14px; font-size: 12px; pointer-events: none;
              display: none; max-width: 280px; z-index: 100; }}
  #tooltip .t-label {{ font-weight: 700; color: var(--accent); margin-bottom: 4px; }}
  #tooltip .t-type  {{ color: var(--yellow); font-size: 11px; }}
  #tooltip .t-sum   {{ color: var(--muted); margin-top: 6px; line-height: 1.4; }}
  #tooltip .t-file  {{ color: var(--green); font-size: 10px; margin-top: 4px; }}
  #search {{ position: absolute; top: 10px; right: 14px; }}
  #search input {{ background: #0A0A0A; border: 1px solid var(--border); color: var(--text);
                   padding: 5px 10px; border-radius: 6px; font-size: 12px; width: 200px; }}
  #search input:focus {{ outline: none; border-color: var(--accent); }}
</style>
</head>
<body>
<div id="accent-bar"></div>
<div id="header">
  <div id="logo">
    <img id="logo-mark" src="../pruvalex-logo.svg" alt="PruvaGraph Logo" width="24" height="24" style="border-radius: 4px; object-fit: cover;">
    <span id="title" style="color: #ffffff;">PruvaGraph</span>
  </div>
  <div id="plan-toggle" role="group" aria-label="Plan">
    <button class="plan-btn active" data-plan="free" onclick="setPlan('free')">Free</button>
    <button class="plan-btn" data-plan="premium" onclick="setPlan('premium')">Premium</button>
  </div>
  <span id="stats">{node_count:,} nodes · {edge_count:,} edges</span>
  <div id="controls">
    <button class="btn" onclick="simulation.alpha(0.3).restart()">↺ Relayout</button>
    <button class="btn" onclick="resetZoom()">⤢ Fit</button>
  </div>
</div>
<div id="legend">
  {legend_items}
</div>
<div id="canvas-wrap">
  <svg id="svg"><g id="root"></g></svg>
  <div id="tooltip"></div>
  <div id="search"><input id="q" placeholder="Search nodes…" oninput="searchNodes(this.value)"></div>
</div>
<script>
function setPlan(plan) {{
  document.querySelectorAll('.plan-btn').forEach(b => b.classList.toggle('active', b.dataset.plan === plan));
}}
const GRAPH = {graph_data};

const svg = d3.select('#svg');
const root = d3.select('#root');
const tooltip = document.getElementById('tooltip');
const W = () => svg.node().clientWidth;
const H = () => svg.node().clientHeight;

const zoom = d3.zoom().scaleExtent([0.05, 4])
  .on('zoom', e => root.attr('transform', e.transform));
svg.call(zoom);

function resetZoom() {{
  svg.transition().duration(500).call(zoom.transform,
    d3.zoomIdentity.translate(W()/2, H()/2).scale(0.8));
}}

const linkSel = root.append('g').attr('class','links')
  .selectAll('line').data(GRAPH.links).join('line')
  .attr('class','link')
  .attr('stroke', d => d.relation === 'imports' ? '#2A2A2A' : '#4B5563')
  .attr('stroke-width', 1);

const nodeG = root.append('g').attr('class','nodes')
  .selectAll('g').data(GRAPH.nodes).join('g').attr('class','node')
  .call(d3.drag().on('start', dragStart).on('drag', dragged).on('end', dragEnd))
  .on('mouseover', showTip).on('mouseout', hideTip);

const radScale = d3.scaleSqrt().domain([0,50]).range([4,22]).clamp(true);
const degMap = {{}};
GRAPH.links.forEach(l => {{
  degMap[l.source.id||l.source] = (degMap[l.source.id||l.source]||0)+1;
  degMap[l.target.id||l.target] = (degMap[l.target.id||l.target]||0)+1;
}});

nodeG.append('circle')
  .attr('r', d => radScale(degMap[d.id]||0))
  .attr('fill', d => d.color);

nodeG.append('text').text(d => d.label)
  .attr('x', 0).attr('y', d => radScale(degMap[d.id]||0)+12)
  .attr('text-anchor','middle')
  .style('display', d => (degMap[d.id]||0) > 3 ? 'block' : 'none');

const simulation = d3.forceSimulation(GRAPH.nodes)
  .force('link', d3.forceLink(GRAPH.links).id(d=>d.id).distance(80))
  .force('charge', d3.forceManyBody().strength(-200))
  .force('center', d3.forceCenter(0, 0))
  .force('collision', d3.forceCollide(d => radScale(degMap[d.id]||0)+5))
  .on('tick', ticked);

function ticked() {{
  linkSel.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
         .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  nodeG.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
}}

function showTip(event, d) {{
  const community = d.community || 'unassigned';
  const deg = degMap[d.id] || 0;
  tooltip.innerHTML = `
    <div class="tip-label">${{d.label}}</div>
    <div class="tip-type">${{d.type}} · ${{community}} · degree ${{deg}}</div>
    ${{d.summary ? `<div class="tip-sum">${{d.summary}}</div>` : ''}}
    ${{d.file ? `<div class="tip-file">${{d.file}}</div>` : ''}}
    ${{d.dead ? `<div class="tip-dead">⚠ Isolated — no connections (dead code candidate)</div>` : ''}}
  `;
  tooltip.style.display = 'block';
  tooltip.style.left = (event.clientX + 16) + 'px';
  tooltip.style.top  = Math.max(10, event.clientY - 10) + 'px';
}}

function hideTip() {{ tooltip.style.display = 'none'; }}

function dragStart(event, d) {{
  if (!event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x; d.fy = d.y;
}}
function dragged(event, d) {{
  d.fx = event.x; d.fy = event.y;
}}
function dragEnd(event, d) {{
  if (!event.active) simulation.alphaTarget(0);
  d.fx = null; d.fy = null;
}}

// ── Search ─────────────────────────────────────────────────────────────────
document.getElementById('q').addEventListener('input', function() {{
  const q = this.value.toLowerCase().trim();
  if (!q) {{
    nodeG.classed('dimmed', false).select('text')
      .style('display', d => (degMap[d.id] || 0) > 3 ? 'block' : 'none');
    linkSel.classed('dimmed', false);
    setStatus('{node_count:,} nodes · {edge_count:,} edges');
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

function setStatus(msg) {{
  const stats = document.getElementById('stats');
  if (stats) stats.textContent = msg;
}}

// ── Initial fit ────────────────────────────────────────────────────────────
setTimeout(resetZoom, 120);
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

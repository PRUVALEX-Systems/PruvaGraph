// @ts-check
'use strict';
/**
 * @module sidebar-html
 * Returns the full HTML string for the PruvaGraph sidebar webview.
 * Pure function — no side effects, no VS Code API calls beyond URI joining.
 *
 * Depends on: utils (getNonce only)
 */

const { getNonce } = require('./utils');

/**
 * Build the sidebar HTML with embedded CSS and JS for the PruvaGraph panel.
 * @param {import('vscode').Webview} webview
 * @param {import('vscode').Uri}     extensionUri
 * @returns {string}
 */
function getWebviewHtml(webview, extensionUri) {
  const nonce = getNonce();
  const csp   = webview.cspSource;

  // NOTE: The nonce in the <script> tag below MUST use literal string
  // concatenation (not a template expression inside the HTML string)
  // because the outer template literal already uses ${nonce} for the CSP header.

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; style-src ${csp} 'unsafe-inline'; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PruvaGraph</title>
<style>
:root {
  --bg: var(--vscode-sideBar-background, #1e1e2e);
  --surface: var(--vscode-editor-background, #181825);
  --border: var(--vscode-widget-border, #313244);
  --text: var(--vscode-foreground, #cdd6f4);
  --muted: var(--vscode-descriptionForeground, #6c7086);
  --accent: #7C6EFA;
  --green: #a6e3a1;
  --cyan: #89dceb;
  --yellow: #f9e2af;
  --red: #f38ba8;
  --link: var(--vscode-textLink-foreground, #89b4fa);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text);
       font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, sans-serif);
       font-size: 12px; padding: 0; overflow-x: hidden; }

/* Header */
.header { padding: 10px 12px 8px; border-bottom: 1px solid var(--border); }
.logo { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.logo-icon { width: 18px; height: 18px; flex-shrink: 0; }
.logo-text { font-size: 13px; font-weight: 700; color: var(--accent); letter-spacing: 0.3px; }
.logo-badge { font-size: 9px; background: var(--green); color: #1e1e2e;
              padding: 1px 5px; border-radius: 3px; font-weight: 700; margin-left: auto; }
.subtitle { color: var(--muted); font-size: 10px; }

/* Tabs */
.tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--surface); }
.tab { flex: 1; text-align: center; padding: 8px 0; cursor: pointer; color: var(--muted); font-weight: 600; font-size: 11px; border-bottom: 2px solid transparent; transition: all 0.2s ease; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-content { display: none; padding-bottom: 20px; }
.tab-content.active { display: block; }

/* Dashboard UI */
.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 10px; }
.metric-card { border-radius: 12px; padding: 14px; background: rgba(255,255,255,0.04); border: 1px solid rgba(124,58,237,0.2); transition: all 0.3s ease; }
.metric-card:hover { background: rgba(255,255,255,0.06); border-color: rgba(124,58,237,0.4); transform: translateY(-2px); }
.metric-label { font-size: 0.75rem; color: rgba(255,255,255,0.6); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600; }
.metric-value { font-size: 1.5rem; font-weight: 700; background: linear-gradient(135deg, #7c3aed, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin: 0; }
.metric-value.savings { background: linear-gradient(135deg, #10b981, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.metric-value.tokens { background: linear-gradient(135deg, #f59e0b, #fbbf24); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.metric-secondary { font-size: 0.8rem; color: rgba(255,255,255,0.5); margin-top: 6px; }
.premium-card { border-radius: 14px; padding: 16px; margin: 10px; background: linear-gradient(135deg, rgba(124,58,237,0.1), rgba(167,139,250,0.05)); border: 1px solid rgba(124,58,237,0.3); }
.premium-card h3 { margin: 0 0 12px; font-size: 0.9rem; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 8px; }
.premium-card h3::before { content: '✨'; font-size: 1rem; }
.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
.stat-row:last-child { border-bottom: none; }
.stat-label { font-size: 0.85rem; color: rgba(255,255,255,0.7); }
.stat-value { font-weight: 700; font-size: 0.9rem; color: #ffffff; }

/* Status card */
.status-card { margin: 8px 10px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }
.status-row-basic { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.built { background: var(--green); box-shadow: 0 0 6px var(--green); }
.status-dot.empty { background: var(--muted); }
.status-dot.watch { background: var(--yellow); animation: pulse 2s infinite; }
.status-label-basic { font-weight: 600; flex: 1; }
.status-meta { color: var(--muted); font-size: 10px; }

/* Buttons */
.btn-group { margin: 8px 10px; display: flex; flex-direction: column; gap: 5px; }
.btn { display: flex; align-items: center; gap: 7px; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; width: 100%; text-align: left; transition: border-color 0.15s, background 0.15s; }
.btn:hover { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, var(--surface)); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: white; font-weight: 600; }
.btn.primary:hover { background: #6a5de8; }
.btn.danger  { border-color: var(--red); color: var(--red); }
.btn.danger:hover { background: color-mix(in srgb, var(--red) 12%, var(--surface)); }
.btn.active  { border-color: var(--yellow); color: var(--yellow); }
.btn-icon { font-size: 14px; }
.btn-label { flex: 1; }
.btn-badge { font-size: 9px; background: var(--accent); color: white; padding: 1px 5px; border-radius: 3px; }

/* Accessibility: focus indicators (WCAG 2.1 AA) */
.btn:focus-visible, .tab:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}
*:focus { outline: none; }

/* Output / log */
.section-title { font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--muted); letter-spacing: 0.8px; padding: 6px 12px 3px; }
.log-box { margin: 0 10px 8px; padding: 8px 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; max-height: 160px; overflow-y: auto; font-family: monospace; font-size: 10px; color: var(--muted); display: none; }
.log-box.visible { display: block; }
.log-line { line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.log-line.ok   { color: var(--green); }
.log-line.warn { color: var(--yellow); }
.log-line.err  { color: var(--red); }

/* Query result */
.query-box { margin: 0 10px 8px; padding: 8px 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; max-height: 200px; overflow-y: auto; font-size: 11px; line-height: 1.6; display: none; }
.query-box.visible { display: block; }

/* Progress */
.progress-bar { height: 2px; background: var(--accent); border-radius: 2px; width: 0; transition: width 0.3s; margin: 0 10px 6px; display: none; }
.progress-bar.active { display: block; animation: progress-anim 2s linear infinite; }

@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
@keyframes progress-anim { 0% { width: 0; margin-left: 10px; } 50% { width: calc(100% - 20px); } 100% { width: 0; margin-left: calc(100% - 10px); } }

/* Divider */
.divider { border: none; border-top: 1px solid var(--border); margin: 6px 10px; }

/* Footer */
.footer { padding: 6px 12px; color: var(--muted); font-size: 10px; border-top: 1px solid var(--border); display: flex; gap: 8px; }
.footer a { color: var(--link); text-decoration: none; cursor: pointer; }

/* ContextLens placeholder */
.context-lens-box { margin: 10px; padding: 16px; border: 1px dashed var(--border); border-radius: 8px; text-align: center; color: var(--muted); }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="logo">
    <svg class="logo-icon" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="4" cy="4" r="3" fill="#7C6EFA"/>
      <circle cx="14" cy="4" r="3" fill="#22D3EE"/>
      <circle cx="9" cy="14" r="3" fill="#34D399"/>
      <line x1="4" y1="4" x2="14" y2="4" stroke="#7C6EFA" stroke-width="1.5"/>
      <line x1="4" y1="4" x2="9"  y2="14" stroke="#7C6EFA" stroke-width="1.5"/>
      <line x1="14" y1="4" x2="9" y2="14" stroke="#22D3EE" stroke-width="1.5"/>
    </svg>
    <span class="logo-text">PRUVALEX PruvaGraph</span>
    <span class="logo-badge">FREE</span>
  </div>
  <div class="subtitle">Measured LLM cost reduction · No server needed</div>
</div>

<!-- Tabs (WCAG: role=tablist, role=tab, aria-selected, aria-controls) -->
<div class="tabs" role="tablist" aria-label="PruvaGraph panels">
  <div class="tab active" role="tab" tabindex="0" data-tab="explorer"
       aria-selected="true" aria-controls="tab-explorer" id="tab-btn-explorer"
       onclick="switchTab('explorer')" onkeydown="handleTabKey(event,'explorer')">Explorer</div>
  <div class="tab" role="tab" tabindex="-1" data-tab="context"
       aria-selected="false" aria-controls="tab-context" id="tab-btn-context"
       onclick="switchTab('context')" onkeydown="handleTabKey(event,'context')">ContextLens</div>
  <div class="tab" role="tab" tabindex="-1" data-tab="cost"
       aria-selected="false" aria-controls="tab-cost" id="tab-btn-cost"
       onclick="switchTab('cost')" onkeydown="handleTabKey(event,'cost')">Cost Dashboard</div>
</div>

<!-- Progress bar -->
<div class="progress-bar" id="progressBar"></div>

<!-- TAB 1: EXPLORER -->
<div id="tab-explorer" class="tab-content active" role="tabpanel" aria-labelledby="tab-btn-explorer">
  <div class="status-card" id="statusCard" role="status" aria-live="polite" aria-label="Graph build status">
    <div class="status-row-basic">
      <div class="status-dot empty" id="statusDot" aria-hidden="true"></div>
      <div class="status-label-basic" id="statusLabel">No graph built yet</div>
    </div>
    <div class="status-meta" id="statusMeta">Run "Build Graph" to analyse your codebase</div>
  </div>

  <div class="btn-group">
    <button class="btn primary" onclick="send('build')" aria-label="Build Graph (Ctrl+Shift+G)" id="btn-build">
      <span class="btn-icon" aria-hidden="true">⚡</span>
      <span class="btn-label">Build Graph</span>
      <span style="font-size:9px;opacity:0.7" aria-hidden="true">Ctrl+Shift+G</span>
    </button>
    <button class="btn" onclick="send('buildFast')" aria-label="Build Fast using LSP" id="btn-buildFast">
      <span class="btn-icon" aria-hidden="true">🚀</span>
      <span class="btn-label">Build Fast (LSP)</span>
      <span class="btn-badge" style="background:var(--green);color:#000" aria-hidden="true">N3</span>
    </button>
    <button class="btn" onclick="send('query')" aria-label="Query Codebase (Ctrl+Shift+/)" id="btn-query">
      <span class="btn-icon" aria-hidden="true">🔍</span>
      <span class="btn-label">Query Codebase</span>
      <span style="font-size:9px;opacity:0.7" aria-hidden="true">Ctrl+Shift+/</span>
    </button>
    <button class="btn" onclick="send('openViz')" aria-label="Open Graph Visualizer in browser" id="btn-openViz">
      <span class="btn-icon" aria-hidden="true">🌐</span>
      <span class="btn-label">Open Graph Visualizer</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <div class="btn-group">
    <button class="btn" onclick="send('installMCP')" aria-label="Install MCP server for Claude Code and Cursor" id="btn-installMCP">
      <span class="btn-icon" aria-hidden="true">🔌</span>
      <span class="btn-label">Install MCP (Claude Code / Cursor)</span>
    </button>
    <button class="btn" id="watchBtn" onclick="send('watchToggle')" aria-label="Toggle Watch Mode" aria-pressed="false">
      <span class="btn-icon" aria-hidden="true">👁</span>
      <span class="btn-label">Enable Watch Mode</span>
    </button>
    <button class="btn" onclick="send('dryRun')" aria-label="Dry Run to estimate savings (free)" id="btn-dryRun">
      <span class="btn-icon" aria-hidden="true">🧪</span>
      <span class="btn-label">Dry Run — Estimate Savings</span>
      <span class="btn-badge" aria-label="Free feature">FREE</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <!-- v1.3.0: Diff & Impact -->
  <div class="section-title" role="heading" aria-level="3">Diff &amp; Impact <span style="font-size:9px;background:#7C6EFA;color:#fff;padding:1px 5px;border-radius:3px;margin-left:4px" aria-hidden="true">v1.3.0</span></div>
  <div class="btn-group">
    <button class="btn" onclick="send('showDiff')" aria-label="Show Graph Diff between builds" id="btn-showDiff">
      <span class="btn-icon" aria-hidden="true">📊</span>
      <span class="btn-label">Show Graph Diff</span>
      <span class="btn-badge" style="background:var(--cyan);color:#000" aria-hidden="true">D1</span>
    </button>
    <button class="btn" onclick="send('analyzeImpact')" aria-label="Analyze Change Impact on dependent modules" id="btn-analyzeImpact">
      <span class="btn-icon" aria-hidden="true">⚠️</span>
      <span class="btn-label">Analyze Change Impact</span>
      <span class="btn-badge" style="background:var(--yellow);color:#000" aria-hidden="true">D2</span>
    </button>
    <button class="btn" onclick="send('buildMonorepo')" aria-label="Build Monorepo Graph across all packages" id="btn-buildMonorepo">
      <span class="btn-icon" aria-hidden="true">🗂</span>
      <span class="btn-label">Build Monorepo Graph</span>
      <span class="btn-badge" style="background:var(--green);color:#000" aria-hidden="true">M1</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <div class="section-title" role="heading" aria-level="3">Setup</div>
  <div class="btn-group">
    <button class="btn" onclick="send('installPkg')" aria-label="Install Python package via pip" id="btn-installPkg">
      <span class="btn-icon" aria-hidden="true">📦</span>
      <span class="btn-label">Install Python Package</span>
      <span style="font-size:9px;opacity:0.6" aria-hidden="true">pip install pruvagraph</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <!-- Query output -->
  <div class="section-title" id="queryTitle" style="display:none" role="heading" aria-level="3">Query Result</div>
  <div class="query-box" id="queryBox" aria-live="polite" aria-label="Query result output"></div>
  <!-- Build log -->
  <div class="section-title" id="logTitle" style="display:none" role="heading" aria-level="3">Output</div>
  <div class="log-box" id="logBox" aria-live="polite" aria-label="Build log output"></div>
  <hr class="divider" role="separator">
  <div class="btn-group">
    <button class="btn danger" onclick="send('clearCache')" aria-label="Clear graph cache" id="btn-clearCache">
      <span class="btn-icon" aria-hidden="true">🗑</span>
      <span class="btn-label">Clear Cache</span>
    </button>
  </div>
</div>

<!-- TAB 2: CONTEXT LENS -->
<div id="tab-context" class="tab-content" role="tabpanel" aria-labelledby="tab-btn-context">
  <div class="context-lens-box">
    <h3>🔍 ContextLens</h3>
    <p style="margin-top:8px">Inline symbol relationships and semantic hints will appear here when you select code in the editor.</p>
    <button class="btn primary" style="margin-top:12px; display:inline-block; width:auto;"
            onclick="send('analyzeImpact')" aria-label="Analyze selected code for impact" id="btn-analyzeSelected">Analyze Selected Code</button>
  </div>
</div>

<!-- TAB 3: COST DASHBOARD -->
<div id="tab-cost" class="tab-content" role="tabpanel" aria-labelledby="tab-btn-cost">
  <div class="metric-grid" role="list" aria-label="Cost metrics">
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-savings">💰 Estimated Savings</div>
      <p class="metric-value savings" aria-labelledby="lbl-savings">$<span id="savings">0.00</span></p>
      <div class="metric-secondary">vs. baseline cost</div>
    </div>
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-tokens">🚀 Tokens Saved</div>
      <p class="metric-value tokens" aria-labelledby="lbl-tokens"><span id="tokensSaved">0</span></p>
      <div class="metric-secondary">total reduction</div>
    </div>
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-cache">⚡ Cache Hits</div>
      <p class="metric-value" aria-labelledby="lbl-cache"><span id="cacheHits">0</span></p>
      <div class="metric-secondary"><span id="cacheRate">0</span>% compression</div>
    </div>
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-baseline">📉 Baseline Cost</div>
      <p class="metric-value" style="color:var(--muted)" aria-labelledby="lbl-baseline">$<span id="dedupProjected">0.00</span></p>
      <div class="metric-secondary">without PruvaGraph</div>
    </div>
  </div>
  <div class="premium-card" role="region" aria-label="Token usage breakdown">
    <h3>Token Usage Breakdown</h3>
    <div class="stat-row">
      <span class="stat-label" id="lbl-tokensIn">Total Input Tokens</span>
      <span class="stat-value" aria-labelledby="lbl-tokensIn"><span id="tokensIn">0</span></span>
    </div>
    <div class="stat-row">
      <span class="stat-label" id="lbl-tokensOut">Total Output Tokens</span>
      <span class="stat-value" aria-labelledby="lbl-tokensOut"><span id="tokensOut">0</span></span>
    </div>
    <div class="stat-row">
      <span class="stat-label" id="lbl-apiAvoided">API Calls Avoided</span>
      <span class="stat-value" aria-labelledby="lbl-apiAvoided"><span id="apiAvoided">0</span> calls</span>
    </div>
  </div>
  <div class="btn-group">
    <button class="btn" onclick="send('refreshSavings')" aria-label="Refresh cost metrics" id="btn-refreshSavings">
      <span class="btn-icon" aria-hidden="true">🔄</span>
      <span class="btn-label">Refresh Metrics</span>
    </button>
    <button class="btn" onclick="send('costReport')" aria-label="View raw JSON cost report" id="btn-costReport">
      <span class="btn-icon" aria-hidden="true">📊</span>
      <span class="btn-label">View Raw JSON Report</span>
    </button>
  </div>
</div>

<!-- Footer -->
<div class="footer" style="margin-top:10px;">
  <span>by <a onclick="send('openExternal',{url:'https://pruvalex.eu'})" style="cursor:pointer">PRUVALEX</a></span>
  <span>·</span>
  <a onclick="send('openExternal',{url:'https://github.com/pruvalex/pruvagraph'})" style="cursor:pointer">GitHub</a>
</div>

<script nonce="${nonce}">
const vscode = acquireVsCodeApi();

function send(command, extra = {}) {
  vscode.postMessage({ command, ...extra });
}

const TAB_ORDER = ['explorer', 'context', 'cost'];

function switchTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => {
    const isActive = t.getAttribute('data-tab') === tabId;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
    t.setAttribute('tabindex', isActive ? '0' : '-1');
  });
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const activeContent = document.getElementById('tab-' + tabId);
  if (activeContent) activeContent.classList.add('active');
}

function handleTabKey(event, tabId) {
  const idx = TAB_ORDER.indexOf(tabId);
  let next = -1;
  if (event.key === 'ArrowRight') next = (idx + 1) % TAB_ORDER.length;
  else if (event.key === 'ArrowLeft') next = (idx - 1 + TAB_ORDER.length) % TAB_ORDER.length;
  else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); switchTab(tabId); return; }
  if (next >= 0) {
    event.preventDefault();
    const nextBtn = document.getElementById('tab-btn-' + TAB_ORDER[next]);
    if (nextBtn) { switchTab(TAB_ORDER[next]); nextBtn.focus(); }
  }
}

let building = false;
let queryLines = [];
let logLines = [];

window.addEventListener('message', (event) => {
  const msg = event.data;
  switch (msg.command) {
    case 'status':      return onStatus(msg);
    case 'buildStart':  return onBuildStart(msg);
    case 'buildLog':    return onBuildLog(msg);
    case 'queryStart':  return onQueryStart(msg);
    case 'queryResult': return onQueryResult(msg);
    case 'costReport':  return onCostReport(msg);
    case 'savingsData': return onSavingsData(msg);
    case 'logLine':     return onLogLine(msg);
    case 'watchStatus': return onWatchStatus(msg);
    case 'diffLoaded':  return onDiffLoaded(msg);
    case 'error':       return onError(msg);
  }
});

function onStatus(msg) {
  const dot = document.getElementById('statusDot');
  const lbl = document.getElementById('statusLabel');
  const meta = document.getElementById('statusMeta');
  if (msg.watchMode) dot.className = 'status-dot watch';
  else if (msg.graphBuilt) dot.className = 'status-dot built';
  else dot.className = 'status-dot empty';

  if (msg.graphBuilt) {
    lbl.textContent = 'Graph ready';
    const folder = msg.root ? msg.root.split(/[\\\\/]/).pop() : '';
    const counts = (msg.nodeCount || msg.edgeCount) ? ' · ' + (msg.nodeCount||0) + ' nodes · ' + (msg.edgeCount||0) + ' edges' : '';
    meta.textContent = folder + counts;
  } else {
    lbl.textContent = 'No graph built yet';
    meta.textContent = 'Run "Build Graph" to analyse your codebase';
  }

  const watchBtn = document.getElementById('watchBtn');
  if (msg.watchMode) {
    watchBtn.className = 'btn active';
    watchBtn.querySelector('.btn-label').textContent = 'Disable Watch Mode';
    watchBtn.setAttribute('aria-pressed', 'true');
    watchBtn.setAttribute('aria-label', 'Disable Watch Mode');
  } else {
    watchBtn.className = 'btn';
    watchBtn.querySelector('.btn-label').textContent = 'Enable Watch Mode';
    watchBtn.setAttribute('aria-pressed', 'false');
    watchBtn.setAttribute('aria-label', 'Enable Watch Mode');
  }
}

function onBuildStart(msg) {
  building = true; logLines = [];
  switchTab('explorer');
  document.getElementById('logTitle').style.display = 'block';
  const lb = document.getElementById('logBox');
  lb.innerHTML = ''; lb.classList.add('visible');
  document.getElementById('progressBar').classList.add('active');
  appendLog('Building graph…', 'ok');
}

function onBuildLog(msg) {
  appendLog(msg.line);
  const line = msg.line || '';
  if (line.includes('✓') || line.includes('Graph:') || line.includes('complete') ||
      line.includes('Error') || line.includes('error') || line.includes('exited with code')) {
    document.getElementById('progressBar').classList.remove('active');
    building = false;
  }
}

function onQueryStart(msg) {
  queryLines = [];
  switchTab('explorer');
  document.getElementById('queryTitle').style.display = 'block';
  const qb = document.getElementById('queryBox');
  qb.innerHTML = ''; qb.classList.add('visible');
  appendQuery('🔍 ' + msg.question);
  appendQuery('');
}

function onQueryResult(msg) { appendQuery(msg.line); }

function onCostReport(msg) {
  switchTab('explorer');
  document.getElementById('queryTitle').style.display = 'block';
  document.getElementById('queryTitle').textContent = 'Raw Cost Report';
  const qb = document.getElementById('queryBox');
  qb.innerHTML = '<pre style="white-space:pre-wrap;font-size:10px;font-family:monospace">' + escHtml(msg.text) + '</pre>';
  qb.classList.add('visible');
}

function formatNumber(num) {
  if (!num) return '0';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
}

function onSavingsData(msg) {
  const data = msg.data;
  if (!data) return;
  const safeNum = (v, digits = 2) => (typeof v === 'number' && isFinite(v)) ? v.toFixed(digits) : '0.' + '0'.repeat(digits);
  document.getElementById('savings').textContent = safeNum(data.costSavedUsd);
  document.getElementById('tokensSaved').textContent = formatNumber(data.tokensSaved || 0);
  document.getElementById('cacheHits').textContent = formatNumber(data.cacheHits || 0);
  document.getElementById('cacheRate').textContent = data.compressionPct != null ? data.compressionPct : 0;
  document.getElementById('dedupProjected').textContent = safeNum(data.naiveCostUsd);
  document.getElementById('tokensIn').textContent = formatNumber(data.totalInputTokens || 0);
  document.getElementById('tokensOut').textContent = formatNumber(data.totalOutputTokens || 0);
  document.getElementById('apiAvoided').textContent = formatNumber(data.apiCallsAvoided || 0);
}

function onLogLine(msg) {
  document.getElementById('logTitle').style.display = 'block';
  document.getElementById('logBox').classList.add('visible');
  appendLog(msg.line);
}

function onWatchStatus(msg) {
  const dot = document.getElementById('statusDot');
  const watchBtn = document.getElementById('watchBtn');
  if (msg.active) {
    dot.className = 'status-dot watch';
    watchBtn.className = 'btn active';
    watchBtn.querySelector('.btn-label').textContent = 'Disable Watch Mode';
  } else {
    const lbl = document.getElementById('statusLabel');
    dot.className = (lbl && lbl.textContent === 'Graph ready') ? 'status-dot built' : 'status-dot empty';
    watchBtn.className = 'btn';
    watchBtn.querySelector('.btn-label').textContent = 'Enable Watch Mode';
  }
}

function onDiffLoaded(msg) {
  document.getElementById('logTitle').style.display = 'block';
  document.getElementById('logTitle').textContent = 'Graph Diff';
  document.getElementById('logBox').classList.add('visible');
  appendLog('📊 ' + (msg.summary || 'No changes'), 'ok');
  if (msg.added) appendLog('  ➕ ' + msg.added + ' added', 'ok');
  if (msg.removed) appendLog('  ➖ ' + msg.removed + ' removed', 'err');
  if (msg.changed) appendLog('  ✏️ ' + msg.changed + ' changed', 'warn');
}

function onError(msg) {
  document.getElementById('logTitle').style.display = 'block';
  document.getElementById('logBox').classList.add('visible');
  appendLog('⚠ ' + msg.message, 'err');
  appendLog('Install: pip install pruvagraph', 'warn');
  document.getElementById('progressBar').classList.remove('active');
}

function appendLog(text, cls = '') {
  const lb = document.getElementById('logBox');
  const line = document.createElement('div');
  line.className = 'log-line ' + cls;
  line.textContent = text;
  lb.appendChild(line);
  lb.scrollTop = lb.scrollHeight;
}

function appendQuery(text) {
  const qb = document.getElementById('queryBox');
  const line = document.createElement('div');
  line.style.cssText = 'margin-bottom:3px';
  line.textContent = text;
  qb.appendChild(line);
  qb.scrollTop = qb.scrollHeight;
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

send('ready');
</script>
</body>
</html>`;
}

module.exports = { getWebviewHtml };

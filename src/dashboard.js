// @ts-check
'use strict';
/**
 * @module dashboard
 * PruvaGraphDashboard — WebviewPanel hosting 4 analytics tabs:
 *   1. Cost Savings Dashboard (benchmark_results.jsonl)
 *   2. Cascade Tier Map        (method_used per question)
 *   3. Agent Run Timeline      (TaskWeaver checkpoints)
 *   4. Token Budget Meter      (BudgetGovernor)
 *
 * Depends on: vscode (implicit), child_process (spawn)
 */

const vscode = require('vscode');
const path   = require('path');
const fs     = require('fs');
const { spawn } = require('child_process');

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Run a pruvagraph CLI subcommand and return stdout as a string.
 * Uses async spawn with a 15s timeout to avoid blocking the host.
 * @param {string[]} args  CLI args after "python -m pruvagraph.cli"
 * @param {string}   [cwd] Working directory
 * @returns {Promise<string>}
 */
function _runPythonCLI(args, cwd) {
  return new Promise((resolve) => {
    const wsFolder = vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath || '.';
    const root = cwd || wsFolder;
    const proc = spawn('python', ['-m', 'pruvagraph.cli', ...args], {
      cwd: root,
      shell: false,
      env: { ...process.env, PYTHONUTF8: '1' },
    });

    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => { proc.kill(); resolve(JSON.stringify({ error: 'CLI timeout (15s)' })); }, 15000);

    proc.stdout?.on('data', (d) => { stdout += d.toString(); });
    proc.stderr?.on('data', (d) => { stderr += d.toString(); });
    proc.on('error', (err) => { clearTimeout(timer); resolve(JSON.stringify({ error: err.message })); });
    proc.on('exit', () => { clearTimeout(timer); resolve(stdout || JSON.stringify({ error: stderr || 'no output' })); });
  });
}

/**
 * Load benchmark results from pruvagraph-out/benchmark_results.jsonl
 * @param {string} root
 * @returns {{ summary: any, questions: any[] } | null}
 */
function _loadBenchmarkData(root) {
  try {
    const p = path.join(root, 'pruvagraph-out', 'benchmark_results.jsonl');
    if (!fs.existsSync(p)) return null;
    const lines = fs.readFileSync(p, 'utf-8').trim().split('\n').filter(Boolean);
    const summary   = JSON.parse(lines[0]);
    const questions = lines.slice(1).map(l => JSON.parse(l));
    return { summary, questions };
  } catch { return null; }
}

// ── Dashboard Panel ──────────────────────────────────────────────────────────

class PruvaGraphDashboard {
  /** @type {PruvaGraphDashboard | undefined} */
  static currentPanel = undefined;
  static viewType = 'pruvagraphDashboard';

  /**
   * @param {import('vscode').ExtensionContext} context
   * @param {string} [initialTab]
   */
  static createOrShow(context, initialTab = 'dashboard') {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : vscode.ViewColumn.One;

    if (PruvaGraphDashboard.currentPanel) {
      PruvaGraphDashboard.currentPanel._panel.reveal(column);
      PruvaGraphDashboard.currentPanel._initialTab = initialTab;
      PruvaGraphDashboard.currentPanel._refresh();
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      PruvaGraphDashboard.viewType,
      'PruvaGraph Analytics',
      column,
      { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [] }
    );

    PruvaGraphDashboard.currentPanel = new PruvaGraphDashboard(panel, context, initialTab);
  }

  /**
   * @param {import('vscode').WebviewPanel} panel
   * @param {import('vscode').ExtensionContext} context
   * @param {string} [initialTab]
   */
  constructor(panel, context, initialTab = 'dashboard') {
    this._panel = panel;
    this._context = context;
    /** @type {import('vscode').Disposable[]} */
    this._disposables = [];
    this._initialTab = initialTab;
    this._refresh();
    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    this._panel.webview.onDidReceiveMessage(msg => this._handleMessage(msg), null, this._disposables);
  }

  /** @param {{ command: string, [key: string]: any }} msg */
  _handleMessage(msg) {
    const wsFolder = vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath || '.';
    if (msg.command === 'refresh') { this._refresh(); return; }
    if (msg.command === 'setBudget') {
      vscode.window.showInputBox({ prompt: 'Token budget cap (e.g. 50000)', value: '50000' })
        .then(async (val) => { if (val && /^\d+$/.test(val)) { await _runPythonCLI(['budget', 'set', val], wsFolder); this._refresh(); } });
      return;
    }
    if (msg.command === 'openViz') {
      const htmlPath = path.join(wsFolder, 'pruvagraph-out', 'graph.html');
      if (fs.existsSync(htmlPath)) vscode.env.openExternal(vscode.Uri.file(htmlPath));
      else vscode.window.showWarningMessage('No graph.html found. Run pruvagraph build first.');
    }
  }

  async _refresh() {
    const wsFolder = vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath || '.';
    const benchData = _loadBenchmarkData(wsFolder);
    let budget = { session_set: false, cap: 0, spent: 0, remaining: 0, pct_used: 0, status: 'NO_BUDGET' };
    let checkpoints = [];
    try { budget = JSON.parse(await _runPythonCLI(['budget', 'check', '--format', 'json'], wsFolder)); } catch {}
    try { checkpoints = JSON.parse(await _runPythonCLI(['task-progress', '--all', '--format', 'json'], wsFolder)); } catch {}
    this._panel.webview.html = this._buildHtml(benchData, budget, checkpoints);
  }

  /**
   * @param {any} benchData
   * @param {any} budget
   * @param {any} checkpoints
   * @returns {string}
   */
  _buildHtml(benchData, budget, checkpoints) {
    const errorObj = (budget && budget.error) ? budget : ((checkpoints && checkpoints.error) ? checkpoints : null);
    if (errorObj) {
      const _escErr = (/** @type {string} */ s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
      return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><style>body{font-family:sans-serif;padding:20px;color:#ccc;background:#0d1117;}code{background:#21262d;padding:4px;border-radius:4px;}</style></head>
<body><h2>&#9888; PRUVALEX Engine Error</h2><p>Python CLI execution failed. Ensure python is installed and pruvagraph is accessible.</p>
<pre style="background:#21262d;padding:10px;border-radius:4px;white-space:pre-wrap;"><code>${_escErr(errorObj.error)}</code></pre>
<p>Run: <code>pip install pruvalex-pruvagraph</code> to resolve this.</p></body></html>`;
    }

    const s = benchData ? benchData.summary : {};
    const savingsPct  = +(s.avg_savings_pct || 0);
    const tokensGraph = +(s.avg_tokens_graph || 0);
    const tokensRaw   = +(s.avg_tokens_raw   || 0);
    const qCount      = +(s.question_count   || 0);

    // Tier counts
    /** @type {Record<string, number>} */
    const tierCounts = { tier0_cache: 0, tier1_deterministic: 0, tier2_embedding: 0, tier3_subgraph: 0, tier_unknown: 0 };
    (benchData ? benchData.questions : []).forEach((/** @type {any} */ q) => {
      const k = q.method_used || 'tier_unknown';
      tierCounts[k] = (tierCounts[k] || 0) + 1;
    });

    // Top 8 questions sorted by savings
    const topQ = (benchData ? benchData.questions : [])
      .filter((/** @type {any} */ q) => q.savings_pct > 0).sort((/** @type {any} */ a, /** @type {any} */ b) => b.savings_pct - a.savings_pct).slice(0, 8);

    // Budget arc
    const budgetPct    = Math.min(+(budget.pct_used || 0), 100);
    const budgetArcLen = (budgetPct / 100 * 339).toFixed(1);
    const budgetColor  = budget.status === 'EXCEEDED' ? '#ff4d4d'
                       : budget.status === 'WARNING'  ? '#f5a623' : '#4ecdc4';

    // Timeline: group by task_id
    /** @type {Record<string, any[]>} */
    const taskMap = {};
    const cpArray = Array.isArray(checkpoints) ? checkpoints : [];
    cpArray.forEach((/** @type {any} */ cp) => { if (!taskMap[cp.task_id]) taskMap[cp.task_id] = []; taskMap[cp.task_id].push(cp); });
    const taskIds = Object.keys(taskMap);

    // ── Tier donut arcs
    const tierDefs = [
      { key: 'tier0_cache',          label: 'Tier 0 — Cache',         color: '#3fb950', desc: 'Free: exact match' },
      { key: 'tier1_deterministic',  label: 'Tier 1 — Deterministic', color: '#4ecdc4', desc: 'Free: graph traversal' },
      { key: 'tier2_embedding',      label: 'Tier 2 — Embedding',     color: '#58a6ff', desc: 'Low: local embed' },
      { key: 'tier3_subgraph',       label: 'Tier 3 — LLM Subgraph',  color: '#f5a623', desc: 'LLM on 2-hop only' },
      { key: 'tier_unknown',         label: 'Unknown',                color: '#8b949e', desc: 'Not detected' },
    ];
    const tierTotal = Object.values(tierCounts).reduce((a, b) => a + b, 0) || 1;
    const cx = 70, cy = 70, r = 50;
    let startAngle = -Math.PI / 2;
    const tierArcs = tierDefs.map(t => {
      const count = tierCounts[t.key] || 0;
      const pct   = count / tierTotal;
      const angle = pct * 2 * Math.PI;
      const x1    = cx + r * Math.cos(startAngle);
      const y1    = cy + r * Math.sin(startAngle);
      startAngle += angle;
      const x2   = cx + r * Math.cos(startAngle);
      const y2   = cy + r * Math.sin(startAngle);
      const large = pct > 0.5 ? 1 : 0;
      return { ...t, count, pct: (pct * 100).toFixed(1),
               path: pct > 0.001 ? `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z` : '' };
    });

    const _esc = (/** @type {string} */ s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

    return `<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PruvaGraph Analytics</title>
<style>
:root{
  --bg:var(--vscode-editor-background, #0d1117); --surface:var(--vscode-sideBar-background, #161b22);
  --bdr:var(--vscode-widget-border, #30363d); --txt:var(--vscode-foreground, #e6edf3);
  --mut:var(--vscode-descriptionForeground, #8b949e);
  --tel:#4ecdc4; --amb:#f5a623; --red:#ff4d4d; --grn:#3fb950; --blu:#58a6ff;
  --acc:var(--vscode-button-background, #7c6efa); --fnt:var(--vscode-font-family, system-ui, sans-serif);
  --mono:var(--vscode-editor-font-family, monospace);
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--txt);font-family:var(--fnt);font-size:13px;padding:0;overflow-x:hidden;}
.tab-bar{display:flex;background:var(--surface);border-bottom:1px solid var(--bdr);position:sticky;top:0;z-index:10;}
.tab{flex:1;text-align:center;padding:10px 6px;cursor:pointer;color:var(--mut);font-size:11px;font-weight:600;
  border-bottom:2px solid transparent;transition:all 0.2s;letter-spacing:0.3px;}
.tab:hover{color:var(--txt);}
.tab.active{color:var(--acc);border-bottom-color:var(--acc);}
.panel{display:none;padding:16px;}
.panel.active{display:block;}
.kpi-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px;}
.kpi{background:var(--surface);border:1px solid var(--bdr);border-radius:10px;padding:14px;transition:border-color 0.2s;}
.kpi:hover{border-color:var(--acc);}
.kpi-label{font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;font-weight:600;}
.kpi-value{font-size:22px;font-weight:700;font-family:var(--mono);}
.kpi-value.g{color:var(--grn);} .kpi-value.t{color:var(--tel);} .kpi-value.b{color:var(--blu);}
.card{background:var(--surface);border:1px solid var(--bdr);border-radius:10px;padding:14px;margin-bottom:12px;}
.card-title{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--mut);letter-spacing:0.6px;margin-bottom:12px;}
.bar-chart{display:flex;flex-direction:column;gap:6px;}
.bar-row{display:flex;align-items:center;gap:8px;}
.bar-label{font-size:11px;color:var(--mut);width:160px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.bar-track{flex:1;display:flex;flex-direction:column;gap:3px;}
.bar-seg{display:flex;align-items:center;gap:4px;height:10px;}
.bar-fill{height:10px;border-radius:4px;transition:width 0.4s ease;}
.bar-fill.g{background:var(--grn);} .bar-fill.r{background:var(--red);}
.bar-tok{font-size:10px;color:var(--mut);font-family:var(--mono);width:40px;flex-shrink:0;}
.bar-pct{font-size:11px;font-weight:700;color:var(--grn);width:36px;text-align:right;flex-shrink:0;font-family:var(--mono);}
.donut-wrap{display:flex;align-items:center;gap:20px;}
.legend{display:flex;flex-direction:column;gap:8px;}
.legend-row{display:flex;align-items:flex-start;gap:8px;font-size:12px;}
.dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:2px;}
.timeline{display:flex;flex-direction:column;gap:12px;}
.timeline-task{border-left:2px solid var(--acc);padding-left:12px;}
.t-task-id{font-size:11px;font-weight:700;color:var(--acc);margin-bottom:6px;}
.t-track{display:flex;flex-direction:column;gap:6px;}
.t-item{background:var(--bg);border:1px solid var(--bdr);border-radius:6px;padding:8px 10px;}
.t-item.done{border-left:3px solid var(--grn);}
.t-item.pending{border-left:3px solid var(--amb);}
.t-item.failed{border-left:3px solid var(--red);}
.t-desc{font-size:12px;margin-bottom:3px;}
.t-meta{font-size:10px;color:var(--mut);font-family:var(--mono);}
.sbadge{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700;margin-left:4px;}
.sbadge.done{background:rgba(63,185,80,0.15);color:var(--grn);}
.sbadge.pending{background:rgba(245,166,35,0.15);color:var(--amb);}
.sbadge.failed{background:rgba(255,77,77,0.15);color:var(--red);}
.sha{font-family:var(--mono);font-size:10px;background:#21262d;padding:1px 4px;border-radius:3px;}
.budget-wrap{display:flex;align-items:center;gap:24px;}
.budget-details{display:flex;flex-direction:column;gap:8px;flex:1;}
.b-row{display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid var(--bdr);}
.b-row:last-child{border:none;}
.b-row .val{font-weight:700;font-family:var(--mono);}
.bstatus{font-size:10px;font-weight:700;text-align:center;margin-top:4px;text-transform:uppercase;letter-spacing:0.5px;}
.bstatus.OK{color:var(--tel);} .bstatus.WARNING{color:var(--amb);} .bstatus.EXCEEDED{color:var(--red);} .bstatus.NO_BUDGET{color:var(--mut);}
.btn{display:inline-flex;align-items:center;gap:6px;background:var(--acc);color:#fff;
  border:none;border-radius:6px;padding:7px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .15s;}
.btn:hover{opacity:.85;}
.btn.ghost{background:transparent;color:var(--mut);border:1px solid var(--bdr);}
.btn.ghost:hover{color:var(--txt);border-color:var(--txt);}
.btn-row{display:flex;gap:8px;margin-bottom:16px;}
.empty{color:var(--mut);font-size:12px;padding:20px;text-align:center;
  border:1px dashed var(--bdr);border-radius:8px;}
code{font-family:var(--mono);background:#21262d;padding:1px 5px;border-radius:3px;font-size:11px;}
table{width:100%;border-collapse:collapse;font-size:12px;}
th{text-align:left;padding:6px 8px;color:var(--mut);border-bottom:1px solid var(--bdr);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:0.4px;}
td{padding:6px 8px;border-bottom:1px solid var(--bdr);}
tr:last-child td{border:none;}
</style></head><body>

<div class="tab-bar">
  <div class="tab ${this._initialTab === 'dashboard' ? 'active' : ''}"  id="tab-dashboard" onclick="sw('dashboard')">&#128200; Cost Dashboard</div>
  <div class="tab ${this._initialTab === 'tiermap' ? 'active' : ''}"   id="tab-tiermap"   onclick="sw('tiermap')">&#9685; Tier Map</div>
  <div class="tab ${this._initialTab === 'timeline' ? 'active' : ''}"  id="tab-timeline"  onclick="sw('timeline')">&#9201; Agent Timeline</div>
  <div class="tab ${this._initialTab === 'budget' ? 'active' : ''}"    id="tab-budget"    onclick="sw('budget')">&#128180; Budget Meter</div>
</div>

<!-- PANEL 1 — Cost Savings Dashboard -->
<div id="dashboard" class="panel ${this._initialTab === 'dashboard' ? 'active' : ''}">
  <div class="btn-row">
    <button class="btn" onclick="post('refresh')">&#8635; Refresh</button>
    <button class="btn ghost" onclick="post('openViz')">&#128200; Open Graph</button>
  </div>
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-label">Avg Token Savings</div>
      <div class="kpi-value g">${savingsPct.toFixed(1)}%</div></div>
    <div class="kpi"><div class="kpi-label">Avg Tokens — Graph</div>
      <div class="kpi-value t">${Math.round(tokensGraph).toLocaleString()}</div></div>
    <div class="kpi"><div class="kpi-label">Avg Tokens — Raw</div>
      <div class="kpi-value b">${Math.round(tokensRaw).toLocaleString()}</div></div>
    <div class="kpi"><div class="kpi-label">Questions Benchmarked</div>
      <div class="kpi-value">${qCount}</div></div>
  </div>
  <div class="card">
    <div class="card-title">Top 8 Questions by Savings (&#9646; Graph &nbsp; &#9646; Raw)</div>
    ${topQ.length > 0 ? `<div class="bar-chart">${topQ.map((/** @type {any} */ q) => {
      const mx = Math.max(q.tokens_raw, q.tokens_graph, 1);
      const gw = (q.tokens_graph / mx * 100).toFixed(1);
      const rw = (q.tokens_raw   / mx * 100).toFixed(1);
      const lbl = _esc(q.question.length > 42 ? q.question.slice(0,40)+'…' : q.question);
      return `<div class="bar-row" title="${_esc(q.question)}">
        <div class="bar-label">${lbl}</div>
        <div class="bar-track">
          <div class="bar-seg"><div class="bar-fill g" style="width:${gw}%"></div><span class="bar-tok">${q.tokens_graph}</span></div>
          <div class="bar-seg"><div class="bar-fill r" style="width:${rw}%"></div><span class="bar-tok">${q.tokens_raw}</span></div>
        </div>
        <div class="bar-pct">${q.savings_pct.toFixed(0)}%</div>
      </div>`;}).join('')}</div>`
    : '<div class="empty">No benchmark data. Run: <code>pruvagraph benchmark-suite</code></div>'}
  </div>
  <div class="card" style="font-size:11px;color:var(--mut);">
    <strong style="color:var(--txt);">Truth Machine</strong> &mdash;
    Numbers from <code>benchmark_results.jsonl</code> (real run, 84 questions on this repo).
    Regenerate: <code>pruvagraph benchmark-suite</code>
  </div>
</div>

<!-- PANEL 2 — Cascade Tier Map -->
<div id="tiermap" class="panel ${this._initialTab === 'tiermap' ? 'active' : ''}">
  <div class="btn-row"><button class="btn" onclick="post('refresh')">&#8635; Refresh</button></div>
  <div class="card">
    <div class="card-title">Query Tier Distribution</div>
    ${qCount > 0 ? `<div class="donut-wrap">
      <svg width="140" height="140" viewBox="0 0 140 140">
        ${tierArcs.filter(a => a.path).map(a => `<path d="${a.path}" fill="${a.color}" opacity="0.9"/>`).join('')}
        <circle cx="${cx}" cy="${cy}" r="34" fill="var(--bg)"/>
        <text x="${cx}" y="${cy - 5}" text-anchor="middle" font-size="18"
              font-family="var(--mono)" fill="var(--txt)" font-weight="700">${tierTotal}</text>
        <text x="${cx}" y="${cy + 14}" text-anchor="middle" font-size="9"
              font-family="var(--fnt)" fill="var(--mut)">queries</text>
      </svg>
      <div class="legend">${tierDefs.filter(t => tierCounts[t.key] > 0).map(t => `
        <div class="legend-row">
          <div class="dot" style="background:${t.color}"></div>
          <div>
            <div>${t.label} <strong style="font-family:var(--mono)">${tierCounts[t.key]}</strong> (${(tierCounts[t.key]/tierTotal*100).toFixed(1)}%)</div>
            <div style="font-size:11px;color:var(--mut);">${t.desc}</div>
          </div>
        </div>`).join('')}</div>
    </div>` : '<div class="empty">No benchmark data. Run benchmark first.</div>'}
  </div>
  <div class="card">
    <div class="card-title">Tier Cost Reference</div>
    <table>
      <tr><th>Tier</th><th>Cost/Query</th><th>Mechanism</th></tr>
      <tr><td style="color:#3fb950;">0 — Cache</td><td>$0.000</td><td style="color:var(--mut);">Exact query cache hit</td></tr>
      <tr><td style="color:#4ecdc4;">1 — Deterministic</td><td>$0.000</td><td style="color:var(--mut);">Graph traversal, no LLM</td></tr>
      <tr><td style="color:#58a6ff;">2 — Embedding</td><td>~$0.00001</td><td style="color:var(--mut);">Local BAAI embed, no API</td></tr>
      <tr><td style="color:#f5a623;">3 — LLM Subgraph</td><td>~$0.0001</td><td style="color:var(--mut);">LLM on 2-hop graph (~450 tokens avg)</td></tr>
    </table>
  </div>
</div>

<!-- PANEL 3 — Agent Run Timeline -->
<div id="timeline" class="panel ${this._initialTab === 'timeline' ? 'active' : ''}">
  <div class="btn-row"><button class="btn" onclick="post('refresh')">&#8635; Refresh</button></div>
  <div class="card">
    <div class="card-title">TaskWeaver — Agent Checkpoints</div>
    ${taskIds.length > 0 ? `<div class="timeline">${taskIds.map(tid => `
      <div class="timeline-task">
        <div class="t-task-id">&#128204; Task: ${tid}</div>
        <div class="t-track">${taskMap[tid].map((/** @type {any} */ cp, /** @type {number} */ i) => `
          <div class="t-item ${cp.status}">
            <div class="t-desc">${i+1}. ${cp.description}
              &nbsp;<span class="sbadge ${cp.status}">${cp.status}</span></div>
            <div class="t-meta">
              ${cp.git_sha ? `<span class="sha">${cp.git_sha.slice(0,8)}</span>&nbsp;` : ''}
              ${(cp.created_at||'').replace('T',' ').replace('Z','')}</div>
          </div>`).join('')}
        </div>
      </div>`).join('')}</div>`
    : '<div class="empty">No checkpoints yet.<br>Use the MCP tool <code>create_checkpoint</code> or CLI:<br><code>pruvagraph checkpoint --task my-task --description "..."</code></div>'}
  </div>
</div>

<!-- PANEL 4 — Token Budget Meter -->
<div id="budget" class="panel ${this._initialTab === 'budget' ? 'active' : ''}">
  <div class="btn-row">
    <button class="btn" onclick="post('setBudget')">&#43; Set Budget</button>
    <button class="btn ghost" onclick="post('refresh')">&#8635; Refresh</button>
  </div>
  <div class="card">
    <div class="card-title">Session Token Budget</div>
    <div class="budget-wrap">
      <div>
        <svg width="120" height="120" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" fill="none" stroke="#21262d" stroke-width="12"/>
          <circle cx="60" cy="60" r="54" fill="none" stroke="${budgetColor}" stroke-width="12"
            stroke-dasharray="${budgetArcLen} 339.29" stroke-linecap="round"
            transform="rotate(-90 60 60)" style="transition:stroke-dasharray .5s;"/>
          <text x="60" y="56" text-anchor="middle" font-family="var(--mono)"
            font-size="18" font-weight="700" fill="${budgetColor}">${budgetPct.toFixed(0)}%</text>
          <text x="60" y="72" text-anchor="middle" font-family="var(--fnt)"
            font-size="9" fill="var(--mut)">used</text>
        </svg>
        <div class="bstatus ${budget.status}">${budget.status}</div>
      </div>
      <div class="budget-details">
        ${budget.session_set ? `
        <div class="b-row"><span>Budget Cap</span><span class="val">${(budget.cap||0).toLocaleString()} tokens</span></div>
        <div class="b-row"><span>Spent</span><span class="val">${(budget.spent||0).toLocaleString()} (${budgetPct.toFixed(1)}%)</span></div>
        <div class="b-row"><span>Remaining</span><span class="val" style="color:${budgetColor}">${(budget.remaining||0).toLocaleString()} tokens</span></div>
        <div class="b-row"><span>Status</span><span class="val" style="color:${budgetColor}">${budget.status}</span></div>
        ` : `<div style="color:var(--mut);font-size:12px;padding:8px 0;">No budget set for this session.<br><br>
        Click <strong>+ Set Budget</strong> to configure a token cap.<br>
        Budget tracks automatically via <code>_dispatch()</code> on every MCP tool call.</div>`}
      </div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">How Budget Tracking Works</div>
    <div style="font-size:12px;color:var(--mut);line-height:1.8;">
      Every MCP tool call flows through <code>_dispatch()</code>, which estimates tokens
      as <code>len(result)&nbsp;//&nbsp;4</code> and records spend automatically &mdash; zero agent effort.<br>
      Thresholds:&nbsp;
      <span style="color:var(--tel);">OK</span> (&lt;80%)&nbsp;
      <span style="color:var(--amb);">WARNING</span> (80&ndash;99%)&nbsp;
      <span style="color:var(--red);">EXCEEDED</span> (&ge;100%)
    </div>
  </div>
</div>

<script>
const vscode = acquireVsCodeApi();
function post(cmd) { vscode.postMessage({ command: cmd }); }
function sw(name) {
  ['dashboard','tiermap','timeline','budget'].forEach((id, i) => {
    document.getElementById(id).classList.toggle('active', id === name);
    document.querySelectorAll('.tab')[i].classList.toggle('active', id === name);
  });
}
</script>
</body></html>`;
  }

  dispose() {
    PruvaGraphDashboard.currentPanel = undefined;
    this._panel.dispose();
    this._disposables.forEach(d => d.dispose());
    this._disposables = [];
  }
}

module.exports = { PruvaGraphDashboard, _loadBenchmarkData };

// @ts-check
'use strict';
/**
 * @module commands
 * All 15 command handlers for PruvaGraph (excluding Dashboard commands).
 * Dashboard commands (showDashboard, showTierMap, showTimeline, showBudget)
 * are wired directly to PruvaGraphDashboard.createOrShow in extension.js.
 *
 * Depends on: utils, cli-runner
 */

const vscode = require('vscode');
const path   = require('path');
const fs     = require('fs');

const { log, escapeHtml, getWorkspaceRoot, noWorkspace } = require('./utils');
const { runCLI, spawnCLI, sendStatus, sendSavingsReceipt } = require('./cli-runner');

// ── Module-level state ──────────────────────────────────────────────────────
let watchMode = false;

/**
 * @returns {boolean}
 */
function getWatchMode() { return watchMode; }

// ── Build ────────────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function runBuild(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');
  const dedup   = cfg.get('dedupThreshold', 0.82);

  provider.post('buildStart', { root });
  log(`Building graph for ${root} …`);

  const args = ['.', '--backend', String(backend), '--dedup-threshold', String(dedup), '--stream'];

  await runCLI('pruvagraph', args, root, provider, (line) => {
    provider.post('buildLog', { line });
  });

  await sendStatus(provider, watchMode);
  await sendSavingsReceipt(provider);
}

// ── N3: LSP Extraction ──────────────────────────────────────────────────────

/**
 * @param {import('vscode').Uri} uri
 * @returns {Promise<object[]>}
 */
async function extractSymbolsViaLSP(uri) {
  try {
    const symbols = await vscode.commands.executeCommand('vscode.executeDocumentSymbolProvider', uri);
    if (!symbols) return [];
    return /** @type {any[]} */(symbols).map(sym => ({
      name: sym.name,
      detail: sym.detail || '',
      kind: vscode.SymbolKind[sym.kind] || 'Unknown',
      range: {
        start: { line: sym.range.start.line, character: sym.range.start.character },
        end:   { line: sym.range.end.line,   character: sym.range.end.character },
      },
    }));
  } catch { return []; }
}

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function runBuildFast(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  provider.post('buildStart', { root });
  log(`[N3] Fast Building via LSP for ${root} …`);

  const files = await vscode.workspace.findFiles('**/*.{py,js,ts,jsx,tsx,java,go,rs}', '**/node_modules/**');
  /** @type {Record<string, object[]>} */
  const extractions = {};
  provider.post('buildLog', { line: `[N3] Found ${files.length} files. Extracting LSP symbols...` });

  let count = 0;
  for (const file of files.slice(0, 50)) {
    const syms = await extractSymbolsViaLSP(file);
    if (syms && syms.length > 0) { extractions[file.fsPath] = syms; count++; }
  }

  provider.post('buildLog', { line: `[N3] Extracted symbols for ${count} files. Passing to pipeline...` });

  const outDir  = path.join(root, 'pruvagraph-out');
  if (!fs.existsSync(outDir)) { fs.mkdirSync(outDir, { recursive: true }); }
  const tmpPath = path.join(outDir, 'lsp_extractions.json');
  fs.writeFileSync(tmpPath, JSON.stringify(extractions, null, 2), 'utf-8');

  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');

  await runCLI('pruvagraph', ['build-from-lsp', tmpPath, '--backend', String(backend), '--stream'], root, provider, (line) => {
    provider.post('buildLog', { line });
  });

  await sendStatus(provider, watchMode);
  await sendSavingsReceipt(provider);
}

// ── Query ────────────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 * @param {string} [prefill]
 */
async function runQuery(provider, prefill = '') {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const question = await vscode.window.showInputBox({
    prompt: 'Ask your codebase anything',
    placeHolder: 'How does auth connect to the database?',
    value: prefill,
  });
  if (!question) return;

  provider.post('queryStart', { question });
  log(`Querying: ${question}`);

  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');

  await runCLI('pruvagraph', ['query', question, '--backend', String(backend)], root, provider, (line) => {
    provider.post('queryResult', { line });
  });

  await sendSavingsReceipt(provider);
}

// ── Cost Report ──────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function runCostReport(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  /** @type {string[]} */
  const lines = [];
  await runCLI('pruvagraph', ['cost-report'], root, provider, (line) => {
    lines.push(line);
    provider.post('logLine', { line });
  });

  if (lines.length > 0) {
    provider.post('costReport', { text: lines.join('\n') });
  }
  await sendSavingsReceipt(provider);
}

// ── Disabled-modules helper ──────────────────────────────────────────────────

/**
 * Read VS Code workspace settings and return a list of disabled module keys.
 * @returns {string[]}
 */
function getDisabledModules() {
  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const modules = ['ghostmemory', 'driftguard', 'contextlens', 'taskweaver', 'budgetgovernor', 'rulesforge'];
  return modules.filter(m => /** @type {boolean} */(cfg.get(`modules.${m}.enabled`, true)) === false);
}

// ── Install MCP ──────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function runInstallMCP(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const choice = await vscode.window.showQuickPick(
    ['VS Code + Cursor + Claude Code (All)', 'VS Code only', 'Cursor only', 'Claude Code only'],
    { placeHolder: 'Choose where to install PruvaGraph MCP' }
  );
  if (!choice) return;

  /** @type {Record<string, string[]>} */
  const flagMap = {
    'VS Code + Cursor + Claude Code (All)': [],
    'VS Code only': ['--vscode'],
    'Cursor only':  ['--cursor'],
    'Claude Code only': ['--claude-code'],
  };

  const flags    = flagMap[choice] || [];
  const disabled = getDisabledModules();
  if (disabled.length > 0) {
    flags.push('--disable-modules', disabled.join(','));
    log(`[settings-gating] Disabled modules: ${disabled.join(', ')}`);
  }

  await runCLI('pruvagraph', ['install', ...flags], root, provider, (line) => {
    provider.post('logLine', { line }); log(line);
  });

  vscode.window.showInformationMessage('✓ PruvaGraph MCP installed! Restart your IDE to activate.');
}

// ── Open Visualizer ──────────────────────────────────────────────────────────

async function openVisualizer() {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const htmlPath = path.join(root, 'pruvagraph-out', 'graph.html');
  if (!fs.existsSync(htmlPath)) {
    const build = await vscode.window.showWarningMessage('No graph found. Build one first?', 'Build Now', 'Cancel');
    if (build === 'Build Now') await vscode.commands.executeCommand('pruvagraph.build');
    return;
  }
  vscode.env.openExternal(vscode.Uri.file(htmlPath));
}

// ── Clear Cache ──────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function clearCache(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const cacheDir = path.join(root, 'pruvagraph-out');
  const confirm  = await vscode.window.showWarningMessage(
    'Clear PruvaGraph cache? The next build will re-extract all files.',
    'Clear Cache', 'Cancel'
  );
  if (confirm !== 'Clear Cache') return;

  try {
    fs.rmSync(cacheDir, { recursive: true, force: true });
    provider.post('logLine', { line: '✓ Cache cleared.' });
    vscode.window.showInformationMessage('PruvaGraph cache cleared.');
    sendStatus(provider, watchMode);
  } catch (e) {
    provider.post('logLine', { line: `⚠ Error: ${/** @type {Error} */(e).message}` });
  }
}

// ── Watch Toggle ─────────────────────────────────────────────────────────────

/**
 * @param {any} provider
 */
function toggleWatch(provider) {
  watchMode = !watchMode;
  provider.post('watchStatus', { active: watchMode });

  if (watchMode) {
    const root = getWorkspaceRoot();
    if (!root) { watchMode = false; return; }

    log('Watch mode ON');
    vscode.window.showInformationMessage('PruvaGraph watch mode ON — auto-rebuilds on file save.');

    const proc = spawnCLI('pruvagraph', ['watch', '.'], root);
    provider._watchProc = proc;

    proc.stdout?.on('data', (/** @type {Buffer} */ d) => {
      const line = d.toString().trim();
      if (line) provider.post('buildLog', { line });
    });
    proc.on('exit', () => { watchMode = false; provider.post('watchStatus', { active: false }); });
  } else {
    log('Watch mode OFF');
    provider._watchProc?.kill();
    provider._watchProc = undefined;
    vscode.window.showInformationMessage('PruvaGraph watch mode OFF.');
  }
}

// ── Find Callers ─────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function findCallers(provider) {
  const editor = vscode.window.activeTextEditor;
  const symbol = editor?.document.getText(editor.selection) || '';
  const q = symbol.trim() || await vscode.window.showInputBox({ prompt: 'Enter function/class name to find callers', placeHolder: 'MyClass or myFunction' });
  if (!q) return;

  const root = getWorkspaceRoot();
  if (!root) return;

  provider.post('queryStart', { question: `Callers of: ${q}` });
  await runCLI('pruvagraph', ['query', `who calls ${q}`, '--backend', 'none'], root, provider, (line) => {
    provider.post('queryResult', { line });
  });
}

// ── Get Dependencies ─────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function getDependencies(provider) {
  const editor = vscode.window.activeTextEditor;
  const symbol = editor?.document.getText(editor.selection) || '';
  const q = symbol.trim() || await vscode.window.showInputBox({ prompt: 'Enter module/function to get dependencies', placeHolder: 'AuthService or src/auth/index.ts' });
  if (!q) return;

  const root = getWorkspaceRoot();
  if (!root) return;

  provider.post('queryStart', { question: `Dependencies of: ${q}` });
  await runCLI('pruvagraph', ['query', `dependencies of ${q}`, '--backend', 'none'], root, provider, (line) => {
    provider.post('queryResult', { line });
  });
}

// ── Install Pkg ──────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function runInstallPkg(provider) {
  const choice = await vscode.window.showQuickPick(
    [
      { label: '$(terminal) pip install pruvagraph', description: 'Standard pip install', value: 'pip' },
      { label: '$(zap) uvx pruvagraph (faster)', description: 'Install via uv — faster, recommended', value: 'uvx' },
    ],
    { placeHolder: 'Choose installation method' }
  );
  if (!choice) return;

  const isWin = process.platform === 'win32';
  const cmd   = choice.value === 'uvx' ? 'uvx' : (isWin ? 'pip' : 'pip3');
  const args  = choice.value === 'uvx' ? ['pruvagraph', '.'] : ['install', '--upgrade', 'pruvagraph'];

  provider.post('buildStart', { root: 'Installing pruvagraph…' });
  log(`Running: ${cmd} ${args.join(' ')}`);

  await runCLI(cmd, args, getWorkspaceRoot() || process.cwd(), provider, (line) => {
    provider.post('buildLog', { line });
  });

  vscode.window.showInformationMessage('✓ pruvagraph installed! Now run Build Graph.');
  provider.post('buildLog', { line: '\n✓ Installation complete. Click "Build Graph" to start.' });
}

// ── Dry Run ──────────────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function runDryRun(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  provider.post('buildStart', { root });
  log('Dry run: estimating cost savings…');

  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');

  /** @type {string[]} */
  const lines = [];
  await runCLI('pruvagraph', ['.', '--dry-run', '--backend', String(backend)], root, provider, (line) => {
    lines.push(line); provider.post('buildLog', { line });
  });

  if (lines.length > 0) {
    provider.post('costReport', { text: lines.join('\n') });
  }
  await sendSavingsReceipt(provider);
}

// ── Show Diff (D1) ───────────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function showDiff(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const diffPath = path.join(root, 'pruvagraph-out', 'last_diff.json');
  if (!fs.existsSync(diffPath)) {
    vscode.window.showInformationMessage('No diff available. Run PruvaGraph build at least twice to see what changed.', 'Build Now')
      .then(btn => { if (btn === 'Build Now') vscode.commands.executeCommand('pruvagraph.build'); });
    return;
  }

  /** @type {any} */
  let diff;
  try { diff = JSON.parse(fs.readFileSync(diffPath, 'utf8')); }
  catch (e) { vscode.window.showErrorMessage(`Could not read diff: ${/** @type {Error} */(e).message}`); return; }

  const diffPanel = vscode.window.createWebviewPanel('pruvagraphDiff', 'PruvaGraph — Graph Diff', vscode.ViewColumn.Beside, { enableScripts: false });

  const sha     = diff.git_sha ? ` [${diff.git_sha}]` : '';
  const ts      = diff.timestamp ? new Date(diff.timestamp * 1000).toLocaleString() : '';
  const summary = diff.diff_summary || 'no changes';

  /** @param {any[]} items @param {string} icon @param {string} cls */
  const renderList = (items, icon, cls) =>
    items.length === 0
      ? '<span class="empty">none</span>'
      : items.map(n => `<div class="item ${cls}">${icon} ${escapeHtml(String(n))}</div>`).join('');

  diffPanel.webview.html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
  body { font-family: var(--vscode-font-family, monospace); font-size:12px;
         background:var(--vscode-editor-background); color:var(--vscode-foreground); padding:16px; }
  h2 { font-size:14px; margin-bottom:4px; }
  .meta { color:var(--vscode-descriptionForeground); font-size:11px; margin-bottom:16px; }
  h3 { font-size:12px; font-weight:600; margin:14px 0 6px; }
  .item { padding:2px 6px; border-radius:3px; margin:2px 0; font-family:monospace; font-size:11px; }
  .added   { background:rgba(166,227,161,0.12); color:#a6e3a1; }
  .removed { background:rgba(243,139,168,0.12); color:#f38ba8; }
  .changed { background:rgba(249,226,175,0.12); color:#f9e2af; }
  .empty   { color:var(--vscode-descriptionForeground); font-style:italic; }
  .badge   { display:inline-block; padding:1px 6px; border-radius:3px; font-size:10px;
             font-weight:700; margin-left:6px; background:#7C6EFA; color:#fff; }
</style></head><body>
<h2>📊 Graph Diff${sha} <span class="badge">D1</span></h2>
<div class="meta">${ts ? `Built ${ts} · ` : ''}${summary}</div>
<h3>➕ Added Nodes (${diff.added_nodes.length})</h3>${renderList(diff.added_nodes,'➕','added')}
<h3>➖ Removed Nodes (${diff.removed_nodes.length})</h3>${renderList(diff.removed_nodes,'➖','removed')}
<h3>✏️ Changed Nodes (${diff.changed_nodes.length})</h3>${renderList(diff.changed_nodes,'✏️','changed')}
<h3>🔗 Added Edges (${diff.added_edges.length})</h3>${renderList(diff.added_edges.map(e=>e.join(' → ')),'🔗','added')}
<h3>🗑 Removed Edges (${diff.removed_edges.length})</h3>${renderList(diff.removed_edges.map(e=>e.join(' → ')),'🗑','removed')}
</body></html>`;

  provider.post('diffLoaded', { summary, added: diff.added_nodes.length, removed: diff.removed_nodes.length, changed: diff.changed_nodes.length });
}

// ── Analyze Impact (D2) ──────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function analyzeImpact(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const editor   = vscode.window.activeTextEditor;
  const selected = editor?.document.getText(editor.selection)?.trim() || '';
  const symbol   = selected || await vscode.window.showInputBox({
    prompt: '[D2] Enter symbol, class, function or file to analyse',
    placeHolder: 'SessionManager  or  auth.py  or  build_graph',
  });
  if (!symbol) return;

  const depth    = await vscode.window.showQuickPick(['3 (default)', '4', '5', '2 (fast)'], { placeHolder: 'BFS depth — how many hops of dependents to include?' });
  const depthNum = depth ? parseInt(depth[0]) : 3;

  const impactPanel = vscode.window.createWebviewPanel('pruvagraphImpact', `Impact: ${symbol}`, vscode.ViewColumn.Beside, { enableScripts: false });

  impactPanel.webview.html = `<!DOCTYPE html><html><body style="font-family:monospace;padding:16px;background:var(--vscode-editor-background);color:var(--vscode-foreground)">
<h2 style="font-size:14px">⚠️ Analyzing impact of <code>${escapeHtml(symbol)}</code>…</h2>
<p style="color:var(--vscode-descriptionForeground);font-size:11px">Running impact analysis (BFS depth ${depthNum})…</p>
</body></html>`;

  /** @type {string[]} */
  const lines = [];
  await runCLI('pruvagraph', ['impact', symbol, '--depth', String(depthNum), '--format', 'table'], root, provider, (line) => { lines.push(line); });

  const escaped = escapeHtml(lines.join('\n'));

  impactPanel.webview.html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
  body { font-family:var(--vscode-font-family,monospace); font-size:12px;
         background:var(--vscode-editor-background); color:var(--vscode-foreground); padding:16px; }
  pre  { font-family:monospace; font-size:11px; line-height:1.6; white-space:pre-wrap; word-break:break-word; }
  .badge { display:inline-block; padding:1px 6px; border-radius:3px;
           font-size:10px; font-weight:700; background:#f9e2af; color:#1e1e2e; margin-left:6px; }
</style></head><body>
<h2 style="font-size:14px">⚠️ Impact: <code>${escapeHtml(symbol)}</code> <span class="badge">D2</span></h2>
<pre>${escaped || 'No output received — is graph built?'}</pre>
</body></html>`;
}

// ── Build Monorepo (M1) ──────────────────────────────────────────────────────

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
async function buildMonorepo(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');

  const confirm = await vscode.window.showInformationMessage('[M1] Build per-package graphs for the entire monorepo?', 'Build Monorepo', 'Cancel');
  if (confirm !== 'Build Monorepo') return;

  provider.post('buildStart', { root });
  log('[M1] Building monorepo graph…');

  await runCLI('pruvagraph', ['.', '--monorepo', '--no-viz', '--backend', String(backend)], root, provider, (line) => { provider.post('buildLog', { line }); });

  await sendStatus(provider, watchMode);
  vscode.window.showInformationMessage('✓ Monorepo graph built. See pruvagraph-out/cross_graph.json');
}

module.exports = {
  runBuild, runBuildFast, runQuery, runCostReport, runInstallMCP, openVisualizer,
  clearCache, toggleWatch, findCallers, getDependencies, runInstallPkg, runDryRun,
  showDiff, analyzeImpact, buildMonorepo,
  getDisabledModules, getWatchMode,
};

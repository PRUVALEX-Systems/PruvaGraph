'use strict';
/**
 * PRUVALEX PruvaGraph — VS Code Extension
 *
 * No server required. All processing is local:
 *   - Code files: regex/tree-sitter (zero cost, zero API key)
 *   - Doc files:  optional LLM (none / ollama / claude / gemini / openai)
 *
 * Works in: VS Code, Cursor, Windsurf, and any VS Code fork.
 * Claude Code integration: via MCP server (separate, stdio transport).
 */

const vscode = require('vscode');
const path = require('path');
const { spawn, execSync } = require('child_process');
const fs = require('fs');

/** @type {vscode.WebviewView | undefined} */
let panel;
let watchMode = false;
let outputChannel;

// ─────────────────────────────────────────────────────────────────────────────
// Activation
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  outputChannel = vscode.window.createOutputChannel('PruvaGraph');

  // Register sidebar webview provider
  const provider = new PruvaGraphViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('pruvagraphPanel', provider)
  );

  // Register commands
  const cmds = [
    ['pruvagraph.build',       () => runBuild(provider)],
    ['pruvagraph.query',       () => runQuery(provider)],
    ['pruvagraph.costReport',  () => runCostReport(provider)],
    ['pruvagraph.installMCP',  () => runInstallMCP(provider)],
    ['pruvagraph.openViz',     () => openVisualizer()],
    ['pruvagraph.clearCache',  () => clearCache(provider)],
    ['pruvagraph.watchToggle', () => toggleWatch(provider)],
    ['pruvagraph.findCallers', () => findCallers(provider)],
    ['pruvagraph.getDeps',     () => getDependencies(provider)],
    ['pruvagraph.installPkg',  () => runInstallPkg(provider)],
    ['pruvagraph.dryRun',      () => runDryRun(provider)],
  ];

  cmds.forEach(([id, fn]) => {
    context.subscriptions.push(vscode.commands.registerCommand(id, fn));
  });

  log('PRUVALEX PruvaGraph activated ✓');
}

function deactivate() {}

module.exports = { activate, deactivate };

// ─────────────────────────────────────────────────────────────────────────────
// WebviewView Provider
// ─────────────────────────────────────────────────────────────────────────────

class PruvaGraphViewProvider {
  static viewType = 'pruvagraphPanel';

  /** @param {vscode.Uri} extensionUri */
  constructor(extensionUri) {
    this._extensionUri = extensionUri;
    this._view = undefined;
  }

  /**
   * @param {vscode.WebviewView} webviewView
   */
  resolveWebviewView(webviewView) {
    this._view = webviewView;
    panel = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.joinPath(this._extensionUri, 'media'),
      ],
    };

    webviewView.webview.html = getWebviewHtml(webviewView.webview, this._extensionUri);

    // Handle messages from the webview
    webviewView.webview.onDidReceiveMessage(msg => {
      switch (msg.command) {
        case 'build':       return runBuild(this);
        case 'query':       return runQuery(this, msg.text);
        case 'costReport':  return runCostReport(this);
        case 'installMCP':  return runInstallMCP(this);
        case 'openViz':     return openVisualizer();
        case 'clearCache':  return clearCache(this);
        case 'watchToggle': return toggleWatch(this);
        case 'showOutput':  return outputChannel.show();
        case 'ready':       return sendStatus(this);
        case 'installPkg':  return runInstallPkg(this);
        case 'dryRun':      return runDryRun(this);
      }
    });

    // Send initial status when view opens
    sendStatus(this);
  }

  /**
   * @param {string} command
   * @param {any} data
   */
  post(command, data) {
    if (this._view) {
      this._view.webview.postMessage({ command, ...data });
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Command implementations
// ─────────────────────────────────────────────────────────────────────────────

async function runBuild(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const cfg = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');
  const dedup   = cfg.get('dedupThreshold', 0.82);

  provider.post('buildStart', { root });
  log(`Building graph for ${root} …`);

  const args = ['.', '--backend', backend, '--dedup-threshold', String(dedup)];

  await runCLI('pruvagraph', args, root, provider, (line) => {
    provider.post('buildLog', { line });
  });

  // After build, send updated status
  await sendStatus(provider);
}

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

  const cfg = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');

  await runCLI('pruvagraph', ['query', question, '--backend', backend], root, provider, (line) => {
    provider.post('queryResult', { line });
  });
}

async function runCostReport(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const lines = [];
  await runCLI('pruvagraph', ['cost-report'], root, provider, (line) => {
    lines.push(line);
    provider.post('logLine', { line });
  });

  if (lines.length > 0) {
    provider.post('costReport', { text: lines.join('\n') });
  }
}

async function runInstallMCP(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const choice = await vscode.window.showQuickPick(
    ['VS Code + Cursor + Claude Code (All)', 'VS Code only', 'Cursor only', 'Claude Code only'],
    { placeHolder: 'Choose where to install PruvaGraph MCP' }
  );
  if (!choice) return;

  const flagMap = {
    'VS Code + Cursor + Claude Code (All)': [],
    'VS Code only': ['--vscode'],
    'Cursor only':  ['--cursor'],
    'Claude Code only': ['--claude-code'],
  };

  const flags = flagMap[choice] || [];
  await runCLI('pruvagraph', ['install', ...flags], root, provider, (line) => {
    provider.post('logLine', { line });
    log(line);
  });

  vscode.window.showInformationMessage('✓ PruvaGraph MCP installed! Restart your IDE to activate.');
}

async function openVisualizer() {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const htmlPath = path.join(root, 'pruvagraph-out', 'graph.html');
  if (!fs.existsSync(htmlPath)) {
    const build = await vscode.window.showWarningMessage(
      'No graph found. Build one first?', 'Build Now', 'Cancel'
    );
    if (build === 'Build Now') {
      await vscode.commands.executeCommand('pruvagraph.build');
    }
    return;
  }

  vscode.env.openExternal(vscode.Uri.file(htmlPath));
}

async function clearCache(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  const cacheDir = path.join(root, 'pruvagraph-out');
  const confirm = await vscode.window.showWarningMessage(
    'Clear PruvaGraph cache? The next build will re-extract all files.',
    'Clear Cache', 'Cancel'
  );
  if (confirm !== 'Clear Cache') return;

  try {
    fs.rmSync(cacheDir, { recursive: true, force: true });
    provider.post('logLine', { line: '✓ Cache cleared.' });
    vscode.window.showInformationMessage('PruvaGraph cache cleared.');
    sendStatus(provider);
  } catch (e) {
    provider.post('logLine', { line: `⚠ Error: ${e.message}` });
  }
}

function toggleWatch(provider) {
  watchMode = !watchMode;
  provider.post('watchStatus', { active: watchMode });

  if (watchMode) {
    const root = getWorkspaceRoot();
    if (!root) { watchMode = false; return; }

    log('Watch mode ON');
    vscode.window.showInformationMessage('PruvaGraph watch mode ON — auto-rebuilds on file save.');

    // Start the CLI watch process
    const proc = spawnCLI('pruvagraph', ['watch', '.'], root);
    provider._watchProc = proc;

    proc.stdout?.on('data', (d) => {
      const line = d.toString().trim();
      if (line) provider.post('buildLog', { line });
    });
    proc.on('exit', () => {
      watchMode = false;
      provider.post('watchStatus', { active: false });
    });
  } else {
    log('Watch mode OFF');
    provider._watchProc?.kill();
    provider._watchProc = undefined;
    vscode.window.showInformationMessage('PruvaGraph watch mode OFF.');
  }
}

async function findCallers(provider) {
  const editor = vscode.window.activeTextEditor;
  const symbol = editor?.document.getText(editor.selection) || '';

  const q = symbol.trim() || await vscode.window.showInputBox({
    prompt: 'Enter function/class name to find callers',
    placeHolder: 'MyClass or myFunction',
  });
  if (!q) return;

  const root = getWorkspaceRoot();
  if (!root) return;

  const lines = [];
  await runCLI('pruvagraph', ['query', `who calls ${q}`, '--backend', 'none'], root, provider, (line) => {
    lines.push(line);
  });

  provider.post('queryResult', { line: lines.join('\n') });
}

async function getDependencies(provider) {
  const editor = vscode.window.activeTextEditor;
  const symbol = editor?.document.getText(editor.selection) || '';

  const q = symbol.trim() || await vscode.window.showInputBox({
    prompt: 'Enter module/function to get dependencies',
    placeHolder: 'AuthService or src/auth/index.ts',
  });
  if (!q) return;

  const root = getWorkspaceRoot();
  if (!root) return;

  const lines = [];
  await runCLI('pruvagraph', ['query', `dependencies of ${q}`, '--backend', 'none'], root, provider, (line) => {
    lines.push(line);
  });

  provider.post('queryResult', { line: lines.join('\n') });
}

// ─────────────────────────────────────────────────────────────────────────────
// New: Install pip package
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
// New: Dry run — estimate cost savings before spending
// ─────────────────────────────────────────────────────────────────────────────

async function runDryRun(provider) {
  const root = getWorkspaceRoot();
  if (!root) { return noWorkspace(); }

  provider.post('buildStart', { root });
  log('Dry run: estimating cost savings…');

  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const backend = cfg.get('llmBackend', 'none');

  const lines = [];
  await runCLI('pruvagraph', ['.', '--dry-run', '--backend', backend], root, provider, (line) => {
    lines.push(line);
    provider.post('buildLog', { line });
  });

  if (lines.length > 0) {
    provider.post('costReport', { text: lines.join('\n') });
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Status helper
// ─────────────────────────────────────────────────────────────────────────────

async function sendStatus(provider) {
  const root = getWorkspaceRoot();
  if (!root) {
    provider.post('status', { graphBuilt: false, watchMode });
    return;
  }

  const graphJson = path.join(root, 'pruvagraph-out', 'graph.json');
  const costJson  = path.join(root, 'pruvagraph-out', 'cost_report.json');
  const graphBuilt = fs.existsSync(graphJson);

  let nodeCount = 0, edgeCount = 0, savingsPct = 0, savedUsd = 0;

  if (graphBuilt) {
    try {
      const data = JSON.parse(fs.readFileSync(graphJson, 'utf8'));
      nodeCount = (data.nodes || []).length;
      edgeCount = (data.links || data.edges || []).length;
    } catch {}

    if (fs.existsSync(costJson)) {
      try {
        const cr = JSON.parse(fs.readFileSync(costJson, 'utf8'));
        savingsPct = cr.savings_pct || 0;
        savedUsd   = cr.cost_saved_usd || 0;
      } catch {}
    }
  }

  provider.post('status', {
    graphBuilt,
    nodeCount,
    edgeCount,
    savingsPct,
    savedUsd,
    watchMode,
    root,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// CLI runner
// ─────────────────────────────────────────────────────────────────────────────

function getWorkspaceRoot() {
  return vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath || null;
}

function noWorkspace() {
  vscode.window.showWarningMessage('PruvaGraph: Please open a folder first.');
}

/**
 * Run a CLI command and stream output.
 * @param {string} cmd
 * @param {string[]} args
 * @param {string} cwd
 * @param {PruvaGraphViewProvider} provider
 * @param {(line: string) => void} onLine
 */
function runCLI(cmd, args, cwd, provider, onLine) {
  return new Promise((resolve) => {
    const proc = spawnCLI(cmd, args, cwd);
    let exitCode = 0;

    const handleData = (data) => {
      const lines = data.toString().split('\n').filter(l => l.trim());
      lines.forEach(line => {
        outputChannel.appendLine(line);
        onLine(line);
      });
    };

    proc.stdout?.on('data', handleData);
    proc.stderr?.on('data', handleData);

    proc.on('error', (err) => {
      const msg = `Error running pruvagraph: ${err.message}.\n` +
                  `Install it with: pip install pruvagraph`;
      outputChannel.appendLine(msg);
      onLine(msg);
      provider.post('error', { message: msg });
      resolve();
    });

    proc.on('exit', (code) => {
      exitCode = code || 0;
      if (code !== 0) {
        const msg = `pruvagraph exited with code ${code}`;
        onLine(msg);
      }
      resolve();
    });
  });
}

function spawnCLI(cmd, args, cwd) {
  const isWin = process.platform === 'win32';
  const shell = isWin;

  // Try to find pruvagraph in PATH, or use python -m pruvagraph
  let command = cmd;
  let fullArgs = args;

  try {
    execSync(`${cmd} --version`, { stdio: 'ignore' });
  } catch {
    // pruvagraph not in PATH — try via python
    command = 'python';
    fullArgs = ['-m', 'pruvagraph', ...args.slice(1)]; // skip 'pruvagraph' arg[0]
    if (cmd === 'pruvagraph') {
      fullArgs = ['-m', 'pruvagraph', ...args];
    }
  }

  return spawn(command, fullArgs, {
    cwd,
    shell,
    env: { ...process.env },
  });
}

function log(msg) {
  outputChannel.appendLine(`[PruvaGraph] ${msg}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// Webview HTML
// ─────────────────────────────────────────────────────────────────────────────

function getWebviewHtml(webview, extensionUri) {
  const nonce = getNonce();
  const csp = webview.cspSource;

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
       font-size: 12px; padding: 0; }

/* Header */
.header { padding: 10px 12px 8px;
          border-bottom: 1px solid var(--border); }
.logo { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.logo-icon { width: 18px; height: 18px; flex-shrink: 0; }
.logo-text { font-size: 13px; font-weight: 700; color: var(--accent); letter-spacing: 0.3px; }
.logo-badge { font-size: 9px; background: var(--green); color: #1e1e2e;
              padding: 1px 5px; border-radius: 3px; font-weight: 700; margin-left: auto; }
.subtitle { color: var(--muted); font-size: 10px; }

/* Status card */
.status-card { margin: 8px 10px; padding: 10px 12px;
               background: var(--surface); border: 1px solid var(--border);
               border-radius: 8px; }
.status-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.built { background: var(--green); box-shadow: 0 0 6px var(--green); }
.status-dot.empty { background: var(--muted); }
.status-dot.watch { background: var(--yellow); animation: pulse 2s infinite; }
.status-label { font-weight: 600; flex: 1; }
.status-meta { color: var(--muted); font-size: 10px; }

.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 8px; }
.metric { background: var(--bg); border-radius: 6px; padding: 6px 8px; }
.metric-val { font-size: 18px; font-weight: 700; color: var(--accent); line-height: 1.1; }
.metric-val.green { color: var(--green); }
.metric-lbl { font-size: 9px; color: var(--muted); text-transform: uppercase; margin-top: 1px; }

/* Buttons */
.btn-group { margin: 8px 10px; display: flex; flex-direction: column; gap: 5px; }
.btn { display: flex; align-items: center; gap: 7px;
       background: var(--surface); border: 1px solid var(--border);
       color: var(--text); padding: 7px 10px; border-radius: 6px;
       cursor: pointer; font-size: 12px; width: 100%; text-align: left;
       transition: border-color 0.15s, background 0.15s; }
.btn:hover { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, var(--surface)); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: white; font-weight: 600; }
.btn.primary:hover { background: #6a5de8; }
.btn.danger  { border-color: var(--red); color: var(--red); }
.btn.danger:hover { background: color-mix(in srgb, var(--red) 12%, var(--surface)); }
.btn.active  { border-color: var(--yellow); color: var(--yellow); }
.btn-icon { font-size: 14px; }
.btn-label { flex: 1; }
.btn-badge { font-size: 9px; background: var(--accent);
             color: white; padding: 1px 5px; border-radius: 3px; }

/* Output / log */
.section-title { font-size: 10px; font-weight: 700; text-transform: uppercase;
                 color: var(--muted); letter-spacing: 0.8px;
                 padding: 6px 12px 3px; }
.log-box { margin: 0 10px 8px; padding: 8px 10px; background: var(--surface);
           border: 1px solid var(--border); border-radius: 6px;
           max-height: 160px; overflow-y: auto; font-family: monospace; font-size: 10px;
           color: var(--muted); display: none; }
.log-box.visible { display: block; }
.log-line { line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.log-line.ok   { color: var(--green); }
.log-line.warn { color: var(--yellow); }
.log-line.err  { color: var(--red); }

/* Query result */
.query-box { margin: 0 10px 8px; padding: 8px 10px; background: var(--surface);
             border: 1px solid var(--border); border-radius: 6px;
             max-height: 200px; overflow-y: auto; font-size: 11px;
             line-height: 1.6; display: none; }
.query-box.visible { display: block; }

/* Progress */
.progress-bar { height: 2px; background: var(--accent);
                border-radius: 2px; width: 0; transition: width 0.3s;
                margin: 0 10px 6px; display: none; }
.progress-bar.active { display: block; animation: progress-anim 2s linear infinite; }

@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
@keyframes progress-anim { 0% { width: 0; margin-left: 10px; }
                            50% { width: calc(100% - 20px); }
                            100% { width: 0; margin-left: calc(100% - 10px); } }

/* Divider */
.divider { border: none; border-top: 1px solid var(--border); margin: 6px 10px; }

/* Footer */
.footer { padding: 6px 12px; color: var(--muted); font-size: 10px;
          border-top: 1px solid var(--border); display: flex; gap: 8px; }
.footer a { color: var(--link); text-decoration: none; cursor: pointer; }
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
  <div class="subtitle">99%+ LLM cost reduction · No server needed</div>
</div>

<!-- Status Card -->
<div class="status-card" id="statusCard">
  <div class="status-row">
    <div class="status-dot empty" id="statusDot"></div>
    <div class="status-label" id="statusLabel">No graph built yet</div>
  </div>
  <div class="status-meta" id="statusMeta">Run "Build Graph" to analyse your codebase</div>
  <div class="metric-grid" id="metrics" style="display:none">
    <div class="metric">
      <div class="metric-val" id="nodeCount">0</div>
      <div class="metric-lbl">Nodes</div>
    </div>
    <div class="metric">
      <div class="metric-val" id="edgeCount">0</div>
      <div class="metric-lbl">Edges</div>
    </div>
    <div class="metric">
      <div class="metric-val green" id="savingsPct">0%</div>
      <div class="metric-lbl">Saved</div>
    </div>
    <div class="metric">
      <div class="metric-val green" id="savedUsd">$0</div>
      <div class="metric-lbl">Cost Saved</div>
    </div>
  </div>
</div>

<!-- Progress bar -->
<div class="progress-bar" id="progressBar"></div>

<!-- Action buttons -->
<div class="btn-group">
  <button class="btn primary" onclick="send('build')">
    <span class="btn-icon">⚡</span>
    <span class="btn-label">Build Graph</span>
    <span style="font-size:9px;opacity:0.7">Ctrl+Shift+G</span>
  </button>
  <button class="btn" onclick="send('query')">
    <span class="btn-icon">🔍</span>
    <span class="btn-label">Query Codebase</span>
    <span style="font-size:9px;opacity:0.7">Ctrl+Shift+/</span>
  </button>
  <button class="btn" onclick="send('openViz')">
    <span class="btn-icon">🌐</span>
    <span class="btn-label">Open Graph Visualizer</span>
  </button>
</div>

<hr class="divider">

<div class="btn-group">
  <button class="btn" onclick="send('installMCP')">
    <span class="btn-icon">🔌</span>
    <span class="btn-label">Install MCP (Claude Code / Cursor)</span>
  </button>
  <button class="btn" id="watchBtn" onclick="send('watchToggle')">
    <span class="btn-icon">👁</span>
    <span class="btn-label">Enable Watch Mode</span>
  </button>
  <button class="btn" onclick="send('costReport')">
    <span class="btn-icon">📊</span>
    <span class="btn-label">Cost Report</span>
  </button>
  <button class="btn" onclick="send('dryRun')">
    <span class="btn-icon">🧪</span>
    <span class="btn-label">Dry Run — Estimate Savings</span>
    <span class="btn-badge">FREE</span>
  </button>
</div>

<hr class="divider">

<div class="section-title">Setup</div>
<div class="btn-group">
  <button class="btn" onclick="send('installPkg')">
    <span class="btn-icon">📦</span>
    <span class="btn-label">Install Python Package</span>
    <span style="font-size:9px;opacity:0.6">pip install pruvagraph</span>
  </button>
</div>

<hr class="divider">

<!-- Query output -->
<div class="section-title" id="queryTitle" style="display:none">Query Result</div>
<div class="query-box" id="queryBox"></div>

<!-- Build log -->
<div class="section-title" id="logTitle" style="display:none">Output</div>
<div class="log-box" id="logBox"></div>

<hr class="divider">

<div class="btn-group">
  <button class="btn danger" onclick="send('clearCache')">
    <span class="btn-icon">🗑</span>
    <span class="btn-label">Clear Cache</span>
  </button>
  <button class="btn" onclick="send('showOutput')">
    <span class="btn-icon">📋</span>
    <span class="btn-label">Show Full Log</span>
  </button>
</div>

<!-- Footer -->
<div class="footer">
  <span>by <a href="https://pruvalex.eu">PRUVALEX</a></span>
  <span>·</span>
  <a href="https://github.com/pruvalex/pruvagraph">GitHub</a>
  <span>·</span>
  <a href="https://github.com/pruvalex/pruvagraph#readme">Docs</a>
</div>

<script nonce="${nonce}">
const vscode = acquireVsCodeApi();

function send(command, extra) {
  vscode.postMessage({ command, ...extra });
}

// State
let building = false;
let queryLines = [];
let logLines = [];

// Handle messages from extension
window.addEventListener('message', (event) => {
  const msg = event.data;
  switch (msg.command) {
    case 'status':      return onStatus(msg);
    case 'buildStart':  return onBuildStart(msg);
    case 'buildLog':    return onBuildLog(msg);
    case 'queryStart':  return onQueryStart(msg);
    case 'queryResult': return onQueryResult(msg);
    case 'costReport':  return onCostReport(msg);
    case 'logLine':     return onLogLine(msg);
    case 'watchStatus': return onWatchStatus(msg);
    case 'error':       return onError(msg);
  }
});

function onStatus(msg) {
  const dot = document.getElementById('statusDot');
  const lbl = document.getElementById('statusLabel');
  const meta = document.getElementById('statusMeta');
  const metrics = document.getElementById('metrics');

  if (msg.watchMode) {
    dot.className = 'status-dot watch';
  } else if (msg.graphBuilt) {
    dot.className = 'status-dot built';
  } else {
    dot.className = 'status-dot empty';
  }

  if (msg.graphBuilt) {
    lbl.textContent = 'Graph ready';
    meta.textContent = msg.root ? msg.root.split(/[\\/]/).pop() : '';
    metrics.style.display = 'grid';
    document.getElementById('nodeCount').textContent = (msg.nodeCount||0).toLocaleString();
    document.getElementById('edgeCount').textContent = (msg.edgeCount||0).toLocaleString();
    document.getElementById('savingsPct').textContent = ((msg.savingsPct||0).toFixed(1)) + '%';
    document.getElementById('savedUsd').textContent = '$' + (msg.savedUsd||0).toFixed(2);
  } else {
    lbl.textContent = 'No graph built yet';
    meta.textContent = 'Run "Build Graph" to analyse your codebase';
    metrics.style.display = 'none';
  }

  const watchBtn = document.getElementById('watchBtn');
  if (msg.watchMode) {
    watchBtn.className = 'btn active';
    watchBtn.querySelector('.btn-label').textContent = 'Disable Watch Mode';
  } else {
    watchBtn.className = 'btn';
    watchBtn.querySelector('.btn-label').textContent = 'Enable Watch Mode';
  }
}

function onBuildStart(msg) {
  building = true;
  logLines = [];
  document.getElementById('logTitle').style.display = 'block';
  const lb = document.getElementById('logBox');
  lb.innerHTML = '';
  lb.classList.add('visible');
  document.getElementById('progressBar').classList.add('active');
  appendLog('Building graph…', 'ok');
}

function onBuildLog(msg) {
  appendLog(msg.line);
  if (msg.line.includes('✓') || msg.line.includes('Graph:')) {
    document.getElementById('progressBar').classList.remove('active');
    building = false;
  }
}

function onQueryStart(msg) {
  queryLines = [];
  document.getElementById('queryTitle').style.display = 'block';
  const qb = document.getElementById('queryBox');
  qb.innerHTML = '';
  qb.classList.add('visible');
  appendQuery('🔍 ' + msg.question);
  appendQuery('');
}

function onQueryResult(msg) {
  appendQuery(msg.line);
}

function onCostReport(msg) {
  document.getElementById('queryTitle').style.display = 'block';
  document.getElementById('queryTitle').textContent = 'Cost Report';
  const qb = document.getElementById('queryBox');
  qb.innerHTML = '<pre style="white-space:pre-wrap;font-size:10px;font-family:monospace">' +
    escHtml(msg.text) + '</pre>';
  qb.classList.add('visible');
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
    dot.className = 'status-dot built';
    watchBtn.className = 'btn';
    watchBtn.querySelector('.btn-label').textContent = 'Enable Watch Mode';
  }
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

// Signal ready
send('ready');
</script>
</body>
</html>`;
}

function getNonce() {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

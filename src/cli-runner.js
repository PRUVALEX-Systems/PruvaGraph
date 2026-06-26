// @ts-check
'use strict';
/**
 * @module cli-runner
 * CLI process management, status helpers, and cost-report loading.
 * Depends on: utils
 */

const vscode   = require('vscode');
const path     = require('path');
const fs       = require('fs');
const { spawn }     = require('child_process');
const { execSync }  = require('child_process');
const { log, getWorkspaceRoot, noWorkspace } = require('./utils');

// ── Module-level injectable state ────────────────────────────────────────────
/** @type {import('vscode').StatusBarItem | undefined} */
let _statusBarItem;
/** @type {import('vscode').WebviewView | undefined} */
let _panel;
let _statusBarPulseTimer;
let _viewBadgeTimeout;
/** @type {{ value: number, tooltip: string } | undefined} */
let _viewBadge;

/**
 * Wire up runtime references injected from activate().
 * @param {{ statusBarItem: import('vscode').StatusBarItem, getPanel: () => import('vscode').WebviewView | undefined }} opts
 */
function initCliRunner({ statusBarItem, getPanel }) {
  _statusBarItem = statusBarItem;
  // Re-read panel lazily so we always get the current reference
  Object.defineProperty(module.exports, '_panel', { get: getPanel, configurable: true });
}

// ── spawnCLI ─────────────────────────────────────────────────────────────────

/**
 * Spawn a CLI sub-process. Attempts `cmd` first; falls back to `python -m pruvagraph`.
 * @param {string}   cmd   e.g. 'pruvagraph'
 * @param {string[]} args
 * @param {string}   cwd
 * @returns {import('child_process').ChildProcess}
 */
function spawnCLI(cmd, args, cwd) {
  let command  = cmd;
  let fullArgs = args;

  try {
    execSync(`${cmd} --version`, { stdio: 'ignore' });
  } catch {
    // Not in PATH — fall back to python -m pruvagraph
    command  = 'python';
    fullArgs = cmd === 'pruvagraph'
      ? ['-m', 'pruvagraph', ...args]
      : ['-m', 'pruvagraph', ...args.slice(1)];
  }

  return spawn(command, fullArgs, {
    cwd,
    shell: false,
    env: { ...process.env },
  });
}

// ── runCLI ───────────────────────────────────────────────────────────────────

/**
 * Spawn a CLI command and stream output line-by-line.
 * @param {string}   cmd
 * @param {string[]} args
 * @param {string}   cwd
 * @param {{ post: (cmd: string, data: object) => void }} provider
 * @param {(line: string) => void} onLine
 * @returns {Promise<void>}
 */
function runCLI(cmd, args, cwd, provider, onLine) {
  return new Promise((resolve) => {
    const proc = spawnCLI(cmd, args, cwd);
    const outputChannel = vscode.window.createOutputChannel('PruvaGraph');

    const handleData = (/** @type {Buffer} */ data) => {
      const lines = data.toString().split('\n').filter(l => l.trim());
      lines.forEach(line => { log(line); onLine(line); });
    };

    proc.stdout?.on('data', handleData);
    proc.stderr?.on('data', handleData);

    proc.on('error', (err) => {
      const msg = `Error running pruvagraph: ${err.message}.\nInstall: pip install pruvagraph`;
      log(msg); onLine(msg);
      provider.post('error', { message: msg });
      resolve();
    });

    proc.on('exit', (code) => {
      if (code !== 0) onLine(`pruvagraph exited with code ${code}`);
      resolve();
    });
  });
}

// ── Cost report helpers ───────────────────────────────────────────────────────

/**
 * @param {string | null} root
 * @returns {object | null}
 */
function loadCostReport(root) {
  if (!root) return null;
  const costJson = path.join(root, 'pruvagraph-out', 'cost_report.json');
  if (!fs.existsSync(costJson)) return null;
  try {
    const data        = JSON.parse(fs.readFileSync(costJson, 'utf8'));
    const naiveCost   = Number(data.naive_cost_usd || 0);
    const naiveTokens = Math.round(naiveCost * 1_000_000 / 3.0);
    const actualTokens = Number(data.total_input_tokens || 0) + Number(data.total_output_tokens || 0);
    const tokensSaved  = Math.max(0, naiveTokens - actualTokens);
    const compressionPct = naiveTokens > 0 ? Math.max(0, Math.round((1 - actualTokens / naiveTokens) * 100)) : 0;
    return {
      cacheHits:           Number(data.cache_hits || 0),
      apiCallsAvoided:     Number(data.calls_saved || 0),
      totalFilesProcessed: Number(data.total_files_processed || 0),
      llmCallsMade:        Number(data.llm_calls_made || 0),
      totalInputTokens:    Number(data.total_input_tokens || 0),
      totalOutputTokens:   Number(data.total_output_tokens || 0),
      actualCostUsd:       Number(data.actual_cost_usd || 0),
      naiveCostUsd:        naiveCost,
      costSavedUsd:        Number(data.cost_saved_usd || 0),
      savingsPct:          Number(data.savings_pct || 0),
      naiveTokens, actualTokens, tokensSaved, compressionPct,
      runDuration:         Number(data.run_duration_seconds || 0),
    };
  } catch { return null; }
}

/**
 * @param {object | null} costData
 */
function updateStatusBar(costData) {
  if (!_statusBarItem) return;
  if (_statusBarPulseTimer) { clearTimeout(_statusBarPulseTimer); _statusBarPulseTimer = undefined; }
  if (_viewBadgeTimeout)    { clearTimeout(_viewBadgeTimeout);    _viewBadgeTimeout    = undefined; }

  const panel = module.exports._panel;

  if (costData && typeof costData.costSavedUsd === 'number' && costData.costSavedUsd > 0) {
    _statusBarItem.text        = `$(graph) PruvaGraph: $${costData.costSavedUsd.toFixed(4)} Saved`;
    _statusBarItem.color       = new vscode.ThemeColor('charts.green');
    _statusBarItem.tooltip     = 'Open the PruvaGraph cost report and savings receipt.';
    _statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentBackground');
    _statusBarItem.show();
    _statusBarPulseTimer = setTimeout(() => { if (_statusBarItem) _statusBarItem.backgroundColor = undefined; }, 1200);

    _viewBadge = { value: 1, tooltip: `$${costData.costSavedUsd.toFixed(4)} saved` };
    const updateBadgePulse = () => {
      if (panel && panel.badge !== undefined) {
        panel.badge = undefined;
        _viewBadgeTimeout = setTimeout(() => {
          if (panel) panel.badge = _viewBadge;
          _viewBadgeTimeout = setTimeout(updateBadgePulse, 600);
        }, 400);
      }
    };
    if (panel) { panel.badge = _viewBadge; _viewBadgeTimeout = setTimeout(updateBadgePulse, 800); }
  } else {
    _statusBarItem.text            = '$(graph) PruvaGraph';
    _statusBarItem.color           = undefined;
    _statusBarItem.tooltip         = 'Run a build or dry run to populate savings data.';
    _statusBarItem.backgroundColor = undefined;
    _statusBarItem.show();
    if (panel) panel.badge = undefined;
  }
}

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 */
function sendSavingsReceipt(provider) {
  const root = getWorkspaceRoot();
  const data = root ? loadCostReport(root) : null;
  provider.post('savingsData', { data });
  updateStatusBar(data);
}

/**
 * @param {{ post: (cmd: string, data: object) => void }} provider
 * @param {boolean} watchMode
 */
async function sendStatus(provider, watchMode) {
  const root = getWorkspaceRoot();
  if (!root) { provider.post('status', { graphBuilt: false, watchMode }); return; }

  const graphJson  = path.join(root, 'pruvagraph-out', 'graph.json');
  const costJson   = path.join(root, 'pruvagraph-out', 'cost_report.json');
  const graphBuilt = fs.existsSync(graphJson);
  let nodeCount = 0, edgeCount = 0, savingsPct = 0, savedUsd = 0;

  if (graphBuilt) {
    try { const d = JSON.parse(fs.readFileSync(graphJson, 'utf8')); nodeCount = (d.nodes||[]).length; edgeCount = (d.links||d.edges||[]).length; } catch {}
    if (fs.existsSync(costJson)) {
      try { const cr = JSON.parse(fs.readFileSync(costJson, 'utf8')); savingsPct = cr.savings_pct||0; savedUsd = cr.cost_saved_usd||0; } catch {}
    }
  }

  provider.post('status', { graphBuilt, nodeCount, edgeCount, savingsPct, savedUsd, watchMode, root });
  updateStatusBar(graphBuilt ? { costSavedUsd: savedUsd } : null);
}

module.exports = { initCliRunner, spawnCLI, runCLI, loadCostReport, updateStatusBar, sendSavingsReceipt, sendStatus };

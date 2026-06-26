// @ts-check
'use strict';
/**
 * @module driftguard
 * v1.6.0 — On-save Python import validation using native VS Code Diagnostics.
 * Depends on: utils, cli-runner
 */

const vscode = require('vscode');
const { log }      = require('./utils');
const { spawnCLI } = require('./cli-runner');

/** @type {import('vscode').DiagnosticCollection | undefined} */
let _diagnostics;

/**
 * Initialize DriftGuard if enabled in settings.
 * Registers a DiagnosticCollection + onDidSaveTextDocument listener.
 * Safe to call multiple times — guards against double-registration.
 * @param {import('vscode').ExtensionContext} context
 */
function initDriftGuard(context) {
  const cfg     = vscode.workspace.getConfiguration('pruvagraph');
  const enabled = cfg.get('modules.driftguard.enabled', false);

  if (!enabled) {
    log('[DriftGuard] Disabled via settings.');
    return;
  }

  _diagnostics = vscode.languages.createDiagnosticCollection('pruvagraph-driftguard');
  context.subscriptions.push(_diagnostics);

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc.languageId !== 'python' && !doc.fileName.endsWith('.py')) return;
      _runDriftGuardOnFile(doc);
    })
  );

  log('[DriftGuard] Enabled — will validate Python imports on save.');
}

/**
 * Extract import lines from a saved Python document and validate each via CLI.
 * Results are rendered as native vscode.Diagnostic warnings.
 * @param {import('vscode').TextDocument} doc
 */
async function _runDriftGuardOnFile(doc) {
  if (!_diagnostics) return;

  const text  = doc.getText();
  const lines = text.split('\n');
  /** @type {import('vscode').Diagnostic[]} */
  const diagnostics = [];
  const root = vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath || '.';
  const importRe = /^\s*(?:from\s+([\w.]+)\s+import\s+([\w*]+)|import\s+([\w.]+))/;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(importRe);
    if (!match) continue;
    const moduleName = match[1] || match[3];
    const symbol     = match[2] || null;
    if (!moduleName) continue;
    if (moduleName.startsWith('.')) continue; // skip relative imports

    try {
      const result = await _runValidateImport(moduleName, symbol, root);
      if (result && !result.valid) {
        const range = new vscode.Range(i, 0, i, lines[i].length);
        const msg   = result.suggestion
          ? `DriftGuard: ${moduleName}${symbol ? '.' + symbol : ''} — ${result.suggestion}`
          : `DriftGuard: ${moduleName}${symbol ? '.' + symbol : ''} not found`;
        const diag  = new vscode.Diagnostic(range, msg, vscode.DiagnosticSeverity.Warning);
        diag.source = 'PruvaGraph DriftGuard';
        diagnostics.push(diag);
      }
    } catch (e) {
      log(`[DriftGuard] Error validating ${moduleName}: ${/** @type {Error} */(e).message}`);
    }
  }

  _diagnostics.set(doc.uri, diagnostics);
}

/**
 * Run `pruvagraph validate-import <module> [symbol] --root <root>` and parse result.
 * @param {string}        moduleName
 * @param {string | null} symbol
 * @param {string}        root
 * @returns {Promise<{ valid: boolean, suggestion: string | null } | null>}
 */
function _runValidateImport(moduleName, symbol, root) {
  return new Promise((resolve) => {
    const args = ['validate-import', moduleName];
    if (symbol && symbol !== '*') args.push(symbol);
    args.push('--root', root);

    const proc = spawnCLI('pruvagraph', args, root);
    let stdout = '', stderr = '';

    proc.stdout?.on('data', (d) => { stdout += d.toString(); });
    proc.stderr?.on('data', (d) => { stderr += d.toString(); });
    proc.on('error', () => resolve(null));
    proc.on('exit', (code) => {
      if (code === 0) { resolve({ valid: true, suggestion: null }); }
      else {
        const m = stderr.match(/→\s*(.+)/);
        resolve({ valid: false, suggestion: m ? m[1].trim() : stderr.trim() || null });
      }
    });
  });
}

module.exports = { initDriftGuard };

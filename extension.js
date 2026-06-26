'use strict';
/**
 * PRUVALEX PruvaGraph — VS Code Extension (Entry Point)
 *
 * This file is the thin activation entry point. All logic is in src/ modules:
 *   src/utils.js           — logging, nonce, escapeHtml, workspace helpers
 *   src/cli-runner.js      — spawnCLI, runCLI, cost-report, status bar
 *   src/commands.js        — all 15 command handlers
 *   src/driftguard.js      — on-save import validation
 *   src/sidebar-provider.js— WebviewViewProvider for the sidebar
 *   src/sidebar-html.js    — sidebar HTML template
 *   src/dashboard.js       — PruvaGraphDashboard (4-tab analytics panel)
 *   src/telemetry.js       — opt-in local telemetry
 *
 * Works in: VS Code, Cursor, Windsurf, and any VS Code fork.
 */

const vscode = require('vscode');

// ── src/ modules ─────────────────────────────────────────────────────────────
const { setOutputChannel, log }                     = require('./src/utils');
const { initCliRunner, spawnCLI, sendStatus, sendSavingsReceipt } = require('./src/cli-runner');
const { initDriftGuard }                            = require('./src/driftguard');
const { PruvaGraphViewProvider, getPanel }          = require('./src/sidebar-provider');
const { PruvaGraphDashboard }                       = require('./src/dashboard');
const { initTelemetry, trackCommand }               = require('./src/telemetry');
const cmds                                          = require('./src/commands');

// ─────────────────────────────────────────────────────────────────────────────
// Activation
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  // 1. Output channel
  const outputChannel = vscode.window.createOutputChannel('PruvaGraph');
  setOutputChannel(outputChannel);

  // 2. Status bar
  const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'pruvagraph.costReport';
  statusBarItem.text = '$(graph) PruvaGraph';
  statusBarItem.tooltip = 'Open PruvaGraph Cost Report';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // 3. Wire CLI runner runtime refs
  initCliRunner({ statusBarItem, getPanel });

  // 4. Sidebar
  const provider = new PruvaGraphViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('pruvagraphPanel', provider)
  );

  // 5. Register commands
  /** @type {[string, () => any][]} */
  const commandDefs = [
    ['pruvagraph.build',         () => cmds.runBuild(provider)],
    ['pruvagraph.buildFast',     () => cmds.runBuildFast(provider)],
    ['pruvagraph.query',         () => cmds.runQuery(provider)],
    ['pruvagraph.costReport',    () => cmds.runCostReport(provider)],
    ['pruvagraph.installMCP',    () => cmds.runInstallMCP(provider)],
    ['pruvagraph.openViz',       () => cmds.openVisualizer()],
    ['pruvagraph.clearCache',    () => cmds.clearCache(provider)],
    ['pruvagraph.watchToggle',   () => cmds.toggleWatch(provider)],
    ['pruvagraph.findCallers',   () => cmds.findCallers(provider)],
    ['pruvagraph.getDeps',       () => cmds.getDependencies(provider)],
    ['pruvagraph.installPkg',    () => cmds.runInstallPkg(provider)],
    ['pruvagraph.dryRun',        () => cmds.runDryRun(provider)],
    ['pruvagraph.showDiff',      () => cmds.showDiff(provider)],
    ['pruvagraph.analyzeImpact', () => cmds.analyzeImpact(provider)],
    ['pruvagraph.buildMonorepo', () => cmds.buildMonorepo(provider)],
    ['pruvagraph.showDashboard', () => PruvaGraphDashboard.createOrShow(context)],
    ['pruvagraph.showTierMap',   () => PruvaGraphDashboard.createOrShow(context, 'tiermap')],
    ['pruvagraph.showTimeline',  () => PruvaGraphDashboard.createOrShow(context, 'timeline')],
    ['pruvagraph.showBudget',    () => PruvaGraphDashboard.createOrShow(context, 'budget')],
  ];

  commandDefs.forEach(([id, fn]) => {
    context.subscriptions.push(
      vscode.commands.registerCommand(id, () => { trackCommand(id); return fn(); })
    );
  });

  // 6. DriftGuard: on-save import validation
  initDriftGuard(context);

  // 7. Telemetry (opt-in, local-only)
  initTelemetry(context);

  // 8. Settings-gating: re-run MCP install on module toggle change
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      const moduleKeys = [
        'pruvagraph.modules.driftguard.enabled',
        'pruvagraph.modules.contextlens.enabled',
        'pruvagraph.modules.ghostmemory.enabled',
        'pruvagraph.modules.taskweaver.enabled',
        'pruvagraph.modules.budgetgovernor.enabled',
        'pruvagraph.modules.rulesforge.enabled',
      ];
      if (!moduleKeys.some(k => event.affectsConfiguration(k))) return;

      const { getWorkspaceRoot } = require('./src/utils');
      const root = getWorkspaceRoot();
      if (!root) return;

      const disabled = cmds.getDisabledModules();
      const flagStr = disabled.length > 0 ? disabled.join(',') : '(none)';
      log(`[settings-gating] Module toggle changed — re-writing MCP configs. Disabled: ${flagStr}`);

      const args = ['install'];
      if (disabled.length > 0) args.push('--disable-modules', disabled.join(','));

      const proc = spawnCLI('pruvagraph', args, root);
      proc.on('exit', (code) => {
        if (code === 0) {
          log('[settings-gating] MCP config files updated ✓ — restart MCP server to apply.');
          vscode.window.showInformationMessage(
            `PruvaGraph: MCP config updated (disabled: ${flagStr}). Restart MCP server to apply.`
          );
        } else {
          log(`[settings-gating] pruvagraph install exited ${code} — MCP config may be stale.`);
        }
      });
      proc.on('error', (err) => {
        log(`[settings-gating] Could not update MCP config: ${err.message}`);
      });
    })
  );

  log('PRUVALEX PruvaGraph activated ✓');
}

function deactivate() {}

module.exports = { activate, deactivate, initDriftGuard, sendStatus, sendSavingsReceipt };

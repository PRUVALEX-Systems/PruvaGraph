// @ts-check
'use strict';
/**
 * @module sidebar-provider
 * PruvaGraphViewProvider — WebviewViewProvider for the sidebar panel.
 * Depends on: utils, cli-runner, commands, sidebar-html
 */

const vscode = require('vscode');
const { sendStatus, sendSavingsReceipt } = require('./cli-runner');
const { getWatchMode } = require('./commands');

// ── Lazy import to break circular dependency ─────────────────────────────────
// sidebar-html.js has no dependencies on sidebar-provider, so this is safe.
let _getWebviewHtml;

/** @type {import('vscode').WebviewView | undefined} */
let _panel;

/**
 * @returns {import('vscode').WebviewView | undefined}
 */
function getPanel() { return _panel; }

class PruvaGraphViewProvider {
  static viewType = 'pruvagraphPanel';

  /**
   * @param {import('vscode').Uri} extensionUri
   */
  constructor(extensionUri) {
    this._extensionUri = extensionUri;
    /** @type {import('vscode').WebviewView | undefined} */
    this._view = undefined;
    /** @type {import('child_process').ChildProcess | undefined} */
    this._watchProc = undefined;
  }

  /**
   * @param {import('vscode').WebviewView} webviewView
   */
  resolveWebviewView(webviewView) {
    this._view = webviewView;
    _panel = webviewView;

    // Lazy-load sidebar HTML to avoid circular imports
    if (!_getWebviewHtml) {
      _getWebviewHtml = require('./sidebar-html').getWebviewHtml;
    }

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this._extensionUri, 'media')],
    };

    webviewView.webview.html = _getWebviewHtml(webviewView.webview, this._extensionUri);

    // Lazy-load command handlers to avoid circular dependency
    const cmds = require('./commands');

    // Handle messages from the webview
    webviewView.webview.onDidReceiveMessage(msg => {
      switch (msg.command) {
        case 'build':         return cmds.runBuild(this);
        case 'buildFast':     return cmds.runBuildFast(this);
        case 'query':         return cmds.runQuery(this, msg.text);
        case 'costReport':    return cmds.runCostReport(this);
        case 'refreshSavings':return sendSavingsReceipt(this);
        case 'installMCP':    return cmds.runInstallMCP(this);
        case 'openViz':       return cmds.openVisualizer();
        case 'clearCache':    return cmds.clearCache(this);
        case 'watchToggle':   return cmds.toggleWatch(this);
        case 'showOutput':    return vscode.commands.executeCommand('workbench.action.output.toggleOutput');
        case 'ready':         return Promise.all([sendStatus(this, getWatchMode()), sendSavingsReceipt(this)]);
        case 'installPkg':    return cmds.runInstallPkg(this);
        case 'dryRun':        return cmds.runDryRun(this);
        case 'showDiff':      return cmds.showDiff(this);
        case 'analyzeImpact': return cmds.analyzeImpact(this);
        case 'buildMonorepo': return cmds.buildMonorepo(this);
        case 'openExternal':  return vscode.env.openExternal(vscode.Uri.parse(msg.url));
      }
    });

    sendStatus(this, getWatchMode());
  }

  /**
   * Post a message to the sidebar webview.
   * @param {string} command
   * @param {object} data
   */
  post(command, data) {
    if (this._view) {
      this._view.webview.postMessage({ command, ...data });
    }
  }
}

module.exports = { PruvaGraphViewProvider, getPanel };

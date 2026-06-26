// @ts-check
'use strict';
/**
 * @module utils
 * Shared utility functions for the PruvaGraph VS Code extension.
 */

const vscode = require('vscode');

/** @type {import('vscode').OutputChannel | undefined} */
let _outputChannel;

/**
 * Set the shared output channel (called once from activate()).
 * @param {import('vscode').OutputChannel} channel
 */
function setOutputChannel(channel) {
  _outputChannel = channel;
}

/**
 * Append a line to the PruvaGraph output channel.
 * Falls back to console.log in test environments.
 * @param {string} msg
 */
function log(msg) {
  if (_outputChannel && typeof _outputChannel.appendLine === 'function') {
    _outputChannel.appendLine(`[PruvaGraph] ${msg}`);
    return;
  }
  // Test-environment shim: collect into a global array
  if (typeof globalThis !== 'undefined' && Array.isArray(globalThis.__PRUVAGRAPH_TEST_LOG_MESSAGES__)) {
    globalThis.__PRUVAGRAPH_TEST_LOG_MESSAGES__.push(`[PruvaGraph] ${msg}`);
  }
  if (console && typeof console.log === 'function') {
    console.log(`[PruvaGraph] ${msg}`);
  }
}

/**
 * Generate a cryptographically-adequate nonce for Content-Security-Policy.
 * @returns {string}
 */
function getNonce() {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

/**
 * Escape HTML special characters for safe insertion into webview templates.
 * @param {string} s
 * @returns {string}
 */
function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Return the fsPath of the first workspace folder, or null.
 * @returns {string | null}
 */
function getWorkspaceRoot() {
  return vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath || null;
}

/**
 * Show a warning when no workspace is open.
 */
function noWorkspace() {
  vscode.window.showWarningMessage('PruvaGraph: Please open a folder first.');
}

module.exports = { setOutputChannel, log, getNonce, escapeHtml, getWorkspaceRoot, noWorkspace };

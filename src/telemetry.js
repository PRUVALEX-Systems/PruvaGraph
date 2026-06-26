// @ts-check
'use strict';
/**
 * @module telemetry
 * Opt-in telemetry that respects vscode.env.isTelemetryEnabled.
 * Tracks only: activation count, command usage (name only — zero user data).
 * All data is local-only (stored in globalState); no network calls.
 */

const vscode = require('vscode');

/** @type {import('vscode').ExtensionContext | undefined} */
let _ctx;

/**
 * Initialize telemetry — call once from activate().
 * @param {import('vscode').ExtensionContext} context
 */
function initTelemetry(context) {
  _ctx = context;
  if (!_isEnabled()) return;
  _increment('pruvagraph.telemetry.activations');
}

/**
 * Record that a command was dispatched (name only, no arguments or user data).
 * @param {string} commandId  e.g. 'pruvagraph.build'
 */
function trackCommand(commandId) {
  if (!_isEnabled()) return;
  _increment(`pruvagraph.telemetry.cmd.${commandId}`);
}

/**
 * Return a snapshot of all telemetry counters (for debug / opt-in export).
 * @returns {Record<string, number>}
 */
function getTelemetrySummary() {
  if (!_ctx) return {};
  /** @type {Record<string, number>} */
  const result = {};
  const keys = _ctx.globalState.keys().filter(k => k.startsWith('pruvagraph.telemetry.'));
  for (const k of keys) {
    result[k] = _ctx.globalState.get(k, 0);
  }
  return result;
}

// ── Internal ─────────────────────────────────────────────────────────────────

/**
 * Check VS Code's global telemetry setting.
 * @returns {boolean}
 */
function _isEnabled() {
  // vscode.env.isTelemetryEnabled was added in VS Code 1.75
  if (typeof vscode.env.isTelemetryEnabled === 'boolean') {
    return vscode.env.isTelemetryEnabled;
  }
  // Fallback: respect the deprecated telemetry.enableTelemetry setting
  const cfg = vscode.workspace.getConfiguration('telemetry');
  return cfg.get('enableTelemetry', true);
}

/**
 * Atomically increment a globalState counter.
 * @param {string} key
 */
function _increment(key) {
  if (!_ctx) return;
  const prev = _ctx.globalState.get(key, 0);
  _ctx.globalState.update(key, /** @type {number} */(prev) + 1);
}

module.exports = { initTelemetry, trackCommand, getTelemetrySummary };

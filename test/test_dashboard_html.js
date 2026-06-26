'use strict';
/**
 * test/test_dashboard_html.js
 *
 * Smoke test for PruvaGraphDashboard._buildHtml() and _loadBenchmarkData().
 *
 * Strategy (Phase 3): directly require src/dashboard.js with mocked vscode
 * and child_process. This is more robust than extracting raw source text.
 */

const assert = require('assert');
const fs     = require('fs');
const path   = require('path');
const os     = require('os');
const Module = require('module');

// ─── Mock vscode + child_process before requiring dashboard ───────────────────
const vscodeMock = {
  workspace: {
    workspaceFolders: [{ uri: { fsPath: os.tmpdir() } }],
    getConfiguration: () => ({ get: (_k, d) => d }),
  },
  window: {
    createWebviewPanel: () => ({
      webview: { html: '', onDidReceiveMessage: () => ({ dispose() {} }), cspSource: 'vscode-resource:' },
      onDidDispose: () => ({ dispose() {} }),
      reveal: () => {},
      dispose: () => {},
    }),
    activeTextEditor: null,
  },
  ViewColumn: { One: 1, Two: 2 },
  Uri: { joinPath: (base, ...rest) => ({ fsPath: path.join(base.fsPath || os.tmpdir(), ...rest) }) },
  env: { isTelemetryEnabled: true },
};

const _origLoad = Module._load;
const _origResolve = Module._resolveFilename;

Module._resolveFilename = function(req, parent, isMain, opts) {
  if (req === 'vscode') return 'vscode';
  return _origResolve(req, parent, isMain, opts);
};
Module._load = function(req, parent, isMain) {
  if (req === 'vscode') return vscodeMock;
  return _origLoad(req, parent, isMain);
};
require.cache['vscode'] = { id: 'vscode', filename: 'vscode', loaded: true, exports: vscodeMock };

// ─── Load module ──────────────────────────────────────────────────────────────
const dashboardPath = path.join(__dirname, '..', 'src', 'dashboard.js');
delete require.cache[dashboardPath];
const dashMod = require(dashboardPath);

// _loadBenchmarkData is a module-level function; PruvaGraphDashboard is the class
const _loadBenchmarkData = dashMod._loadBenchmarkData;
const PruvaGraphDashboard = dashMod.PruvaGraphDashboard;

if (typeof _loadBenchmarkData !== 'function') {
  throw new Error('src/dashboard.js does not export _loadBenchmarkData — add module.exports');
}
if (typeof PruvaGraphDashboard !== 'function') {
  throw new Error('src/dashboard.js does not export PruvaGraphDashboard — add module.exports');
}

// Build a minimal instance to call _buildHtml on
const _Dashboard = PruvaGraphDashboard.prototype;

// ─── Test helpers ─────────────────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (e) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${e.message}`);
    failed++;
  }
}

function countOpenClose(html, tag) {
  const open  = (html.match(new RegExp(`<${tag}[\\s>/]`, 'gi')) || []).length;
  const close = (html.match(new RegExp(`</${tag}>`, 'gi')) || []).length;
  return { open, close };
}

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const NULL_BUDGET    = { session_set: false, cap: 0, spent: 0, remaining: 0, pct_used: 0, status: 'NO_BUDGET' };
const REAL_BUDGET    = { session_set: true, cap: 50000, spent: 12500, remaining: 37500, pct_used: 25.0, status: 'OK' };
const WARN_BUDGET    = { session_set: true, cap: 10000, spent: 8900, remaining: 1100, pct_used: 89.0, status: 'WARNING' };
const EXCEED_BUDGET  = { session_set: true, cap: 10000, spent: 11000, remaining: -1000, pct_used: 110.0, status: 'EXCEEDED' };

const BENCH_DATA = {
  summary: { avg_savings_pct: 70.5, avg_tokens_graph: 450, avg_tokens_raw: 3884, question_count: 84 },
  questions: [
    { question: 'What modules import networkx?', savings_pct: 88.2, tokens_graph: 120, tokens_raw: 1012, method_used: 'tier1_deterministic' },
    { question: 'List all callers of build_graph', savings_pct: 75.1, tokens_graph: 210, tokens_raw: 843, method_used: 'tier0_cache' },
    { question: 'What does mcp_server export?', savings_pct: 62.3, tokens_graph: 380, tokens_raw: 1010, method_used: 'tier1_graph' },
  ]
};

const CHECKPOINTS = [
  { task_id: 'task-001', description: 'Initial scaffold', status: 'active', git_sha: 'abc1234567', created_at: '2026-06-21T10:00:00Z' },
  { task_id: 'task-001', description: 'Add tests', status: 'active', git_sha: 'def8901234', created_at: '2026-06-21T11:00:00Z' },
  { task_id: 'task-002', description: 'Fix installer', status: 'rolled_back', git_sha: null, created_at: '2026-06-21T12:00:00Z' },
];

// ─── Tests ────────────────────────────────────────────────────────────────────

console.log('\n=== Dashboard HTML Smoke Tests ===\n');

// Group 1: null / empty data
console.log('Group 1: Empty state (null benchData, no budget, no checkpoints)');
{
  const html = _Dashboard._buildHtml(null, NULL_BUDGET, []);

  test('Returns a non-empty string', () => {
    assert.strictEqual(typeof html, 'string');
    assert(html.length > 500, `HTML too short: ${html.length} chars`);
  });

  test('Starts with <!DOCTYPE html>', () => {
    assert(html.trimStart().startsWith('<!DOCTYPE html>'), `First 50 chars: ${html.slice(0, 50)}`);
  });

  test('Contains all 4 panel divs', () => {
    assert(html.includes('id="dashboard"'), 'Missing id=dashboard');
    assert(html.includes('id="tiermap"'),   'Missing id=tiermap');
    assert(html.includes('id="timeline"'),  'Missing id=timeline');
    assert(html.includes('id="budget"'),    'Missing id=budget');
  });

  test('Has ≥4 tab elements', () => {
    const tabs = html.match(/class="tab[" ]/g) || [];
    assert(tabs.length >= 4, `Expected ≥4 tabs, got ${tabs.length}`);
  });

  test('No raw template syntax ${...} leaked', () => {
    const leaked = html.match(/\$\{[^}]+\}/g);
    assert(!leaked, `Leaked template syntax: ${(leaked||[]).join(', ')}`);
  });

  test('<div> tags are balanced', () => {
    const { open, close } = countOpenClose(html, 'div');
    assert.strictEqual(open, close, `<div> imbalance: ${open} open vs ${close} close`);
  });

  test('<svg> tags are balanced', () => {
    const { open, close } = countOpenClose(html, 'svg');
    assert.strictEqual(open, close, `<svg> imbalance: ${open} vs ${close}`);
  });

  test('<script> tag present and closed', () => {
    const { open, close } = countOpenClose(html, 'script');
    assert(open >= 1, 'No <script> tag');
    assert.strictEqual(open, close, `<script> imbalance: ${open} vs ${close}`);
  });

  test('Empty state: benchmark empty message shown', () => {
    assert(html.includes('benchmark-suite') || html.includes('No benchmark data'),
      'Benchmark empty state missing');
  });

  test('Empty state: checkpoint empty message shown', () => {
    assert(html.includes('No checkpoints') || html.includes('create_checkpoint'),
      'Checkpoint empty state missing');
  });

  test('Empty state: no-budget message shown', () => {
    assert(html.includes('No budget set') || html.includes('NO_BUDGET'),
      'No-budget state message missing');
  });
}

// Group 2: Full realistic data
console.log('\nGroup 2: Full realistic data');
{
  const html = _Dashboard._buildHtml(BENCH_DATA, REAL_BUDGET, CHECKPOINTS);

  test('KPI: 70.5% savings rendered', () => {
    assert(html.includes('70.5%'), 'Savings KPI missing');
  });

  test('KPI: question count 84 rendered', () => {
    assert(html.includes('>84<'), `Question count not found in: ${html.slice(html.indexOf('kpi-value'), html.indexOf('kpi-value') + 100)}`);
  });

  test('Bar chart: question text rendered', () => {
    assert(html.includes('networkx') || html.includes('build_graph'), 'Bar chart questions absent');
  });

  test('Tier map: Tier 1 label rendered', () => {
    assert(html.includes('Tier 1') || html.includes('Deterministic'), 'Tier 1 missing from donut');
  });

  test('Timeline: task-001 rendered', () => {
    assert(html.includes('task-001'), 'Timeline task-001 missing');
  });

  test('Timeline: rolled_back status rendered', () => {
    assert(html.includes('rolled_back'), 'rolled_back status missing');
  });

  test('Timeline: git sha first 8 chars rendered', () => {
    assert(html.includes('abc12345'), 'git_sha[0:8] missing');
  });

  test('Budget: 25% rendered', () => {
    assert(html.includes('25'), 'Budget 25% missing');
  });

  test('<div> balanced with full data', () => {
    const { open, close } = countOpenClose(html, 'div');
    assert.strictEqual(open, close, `<div> imbalance: ${open} vs ${close}`);
  });

  test('No raw ${...} leaked with full data', () => {
    const leaked = html.match(/\$\{[^}]+\}/g);
    assert(!leaked, `Leaked: ${(leaked||[]).join(', ')}`);
  });
}

// Group 3: Budget color states
console.log('\nGroup 3: Budget color states');
{
  test('EXCEEDED: red color (#ff4d4d) in SVG', () => {
    const html = _Dashboard._buildHtml(null, EXCEED_BUDGET, []);
    assert(html.includes('#ff4d4d'), 'Red color missing for EXCEEDED');
  });

  test('WARNING: amber color (#f5a623) in SVG', () => {
    const html = _Dashboard._buildHtml(null, WARN_BUDGET, []);
    assert(html.includes('#f5a623'), 'Amber color missing for WARNING');
  });

  test('OK budget: teal color (#4ecdc4) in SVG', () => {
    const html = _Dashboard._buildHtml(null, REAL_BUDGET, []);
    assert(html.includes('#4ecdc4'), 'Teal color missing for OK');
  });
}

// Group 4: Edge cases
console.log('\nGroup 4: Edge cases');
{
  test('git_sha null: no literal "null" string in output', () => {
    const html = _Dashboard._buildHtml(BENCH_DATA, NULL_BUDGET, CHECKPOINTS);
    assert(!html.includes('>null<'), 'Literal >null< found in output');
  });

  test('XSS: <script> in question does not appear as unescaped HTML', () => {
    const xssData = {
      summary: { avg_savings_pct: 50, avg_tokens_graph: 100, avg_tokens_raw: 200, question_count: 1 },
      questions: [{ question: '<script>alert(1)</script>', savings_pct: 50, tokens_graph: 100, tokens_raw: 200, method_used: 'tier1_deterministic' }]
    };
    const html = _Dashboard._buildHtml(xssData, NULL_BUDGET, []);
    // The question may appear in title="" or bar label — check raw <script> tag is not injected
    // into element content (title attribute is less dangerous)
    const unquotedScript = (html.match(/>.*<script>alert\(1\)<\/script>.*</g) || []);
    assert(unquotedScript.length === 0,
      'Unescaped <script> from question content found as element content — XSS risk');
  });

  test('Empty checkpoints array: no crash, timeline empty state shown', () => {
    const html = _Dashboard._buildHtml(BENCH_DATA, NULL_BUDGET, []);
    assert(html.includes('No checkpoints') || html.includes('create_checkpoint'));
  });
}

// Group 5: _loadBenchmarkData
console.log('\nGroup 5: _loadBenchmarkData()');
{
  test('Returns null for nonexistent path', () => {
    const r = _loadBenchmarkData('/this/path/does/not/exist/at/all');
    assert.strictEqual(r, null);
  });

  test('Returns {summary, questions} for valid JSONL', () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pruva-'));
    fs.mkdirSync(path.join(tmp, 'pruvagraph-out'));
    const sum = { avg_savings_pct: 65, avg_tokens_graph: 300, avg_tokens_raw: 857, question_count: 1 };
    const q = { question: 'q1', savings_pct: 65, tokens_graph: 300, tokens_raw: 857, method_used: 'tier1_deterministic' };
    fs.writeFileSync(
      path.join(tmp, 'pruvagraph-out', 'benchmark_results.jsonl'),
      JSON.stringify(sum) + '\n' + JSON.stringify(q) + '\n',
      'utf-8'
    );
    const r = _loadBenchmarkData(tmp);
    // NOTE: deepStrictEqual fails across vm context boundaries (different Object
    // prototype from vm vs main context in Node.js 24). Use individual checks instead.
    assert(r !== null, 'Expected non-null result');
    assert.strictEqual(r.summary.avg_savings_pct, 65,  'avg_savings_pct mismatch');
    assert.strictEqual(r.summary.avg_tokens_graph, 300, 'avg_tokens_graph mismatch');
    assert.strictEqual(r.summary.avg_tokens_raw, 857,   'avg_tokens_raw mismatch');
    assert.strictEqual(r.summary.question_count, 1,     'question_count mismatch');
    assert.strictEqual(r.questions.length, 1,           'Expected 1 question');
    assert.strictEqual(r.questions[0].question, 'q1',   'question text mismatch');
    // cleanup
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  test('Returns null for corrupt JSONL without crashing', () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pruva-'));
    fs.mkdirSync(path.join(tmp, 'pruvagraph-out'));
    fs.writeFileSync(path.join(tmp, 'pruvagraph-out', 'benchmark_results.jsonl'),
      'NOT JSON\n{{bad', 'utf-8');
    const r = _loadBenchmarkData(tmp);
    assert.strictEqual(r, null);
    fs.rmSync(tmp, { recursive: true, force: true });
  });
}

// ─── Summary ──────────────────────────────────────────────────────────────────
console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);
if (failed > 0) process.exit(1);

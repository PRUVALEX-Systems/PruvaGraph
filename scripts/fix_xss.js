/**
 * fix_xss.js — applies two surgical fixes to extension.js:
 *   1. Restores all CSS accidentally deleted from the <style> block
 *   2. Adds _esc() helper and escapes question text in bar chart labels
 *
 * Run: node fix_xss.js
 */
'use strict';
const fs = require('fs');
const path = require('path');

const EXT = path.join(__dirname, 'extension.js');
let src = fs.readFileSync(EXT, 'utf-8');

// ── Verify current state ──────────────────────────────────────────────────────
const STYLE_OPEN = '<style>\n:root{--bg:#0d1117;';
if (!src.includes(STYLE_OPEN)) {
  // Style block may have been deleted — restore it
  console.log('⚠ Style block missing — restoring');

  const CSS_RESTORE = `<style>
:root{--bg:#0d1117;--sur:#161b22;--bdr:#30363d;--txt:#e6edf3;--mut:#8b949e;
  --grn:#3fb950;--amb:#f5a623;--red:#ff4d4d;--blu:#58a6ff;--tel:#4ecdc4;--pur:#a78bfa;
  --fnt:'Inter',-apple-system,sans-serif;--mono:'JetBrains Mono','Fira Code',monospace;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--txt);font-family:var(--fnt);font-size:13px;line-height:1.5;}
.tab-bar{display:flex;background:var(--sur);border-bottom:1px solid var(--bdr);
  position:sticky;top:0;z-index:10;}
.tab{padding:10px 18px;cursor:pointer;color:var(--mut);font-size:12px;font-weight:500;
  border-bottom:2px solid transparent;transition:all .15s;user-select:none;}
.tab:hover{color:var(--txt);}
.tab.active{color:var(--tel);border-bottom-color:var(--tel);}
.panel{display:none;padding:20px;max-width:900px;}
.panel.active{display:block;}
.card{background:var(--sur);border:1px solid var(--bdr);border-radius:8px;padding:16px;margin-bottom:16px;}
.card-title{font-size:11px;font-weight:600;color:var(--mut);text-transform:uppercase;
  letter-spacing:.6px;margin-bottom:12px;}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px;}
.kpi{background:var(--sur);border:1px solid var(--bdr);border-radius:8px;padding:14px 16px;}
.kpi-label{font-size:11px;color:var(--mut);margin-bottom:4px;}
.kpi-value{font-family:var(--mono);font-size:24px;font-weight:700;}
.kpi-value.g{color:var(--grn);}.kpi-value.t{color:var(--tel);}.kpi-value.b{color:var(--blu);}
.bar-chart{display:flex;flex-direction:column;gap:8px;}
.bar-row{display:flex;align-items:center;gap:8px;}
.bar-label{font-size:11px;color:var(--mut);width:160px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;flex-shrink:0;}
.bar-track{flex:1;}
.bar-seg{display:flex;align-items:center;gap:4px;margin-bottom:2px;}
.bar-fill{border-radius:3px;height:10px;transition:width .4s;}
.bar-fill.g{background:var(--tel);}
.bar-fill.r{background:#3d4654;}
.bar-tok{font-family:var(--mono);font-size:10px;color:var(--mut);}
.bar-pct{font-family:var(--mono);font-size:11px;color:var(--grn);width:38px;text-align:right;}
.donut-wrap{display:flex;align-items:flex-start;gap:24px;}
.legend{display:flex;flex-direction:column;gap:8px;}
.legend-row{display:flex;align-items:flex-start;gap:8px;font-size:12px;}
.dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:3px;}
.budget-wrap{display:flex;align-items:center;gap:32px;}
.bstatus{font-family:var(--mono);font-size:11px;font-weight:700;text-align:center;margin-top:6px;}
.bstatus.OK{color:var(--tel);}.bstatus.WARNING{color:var(--amb);}.bstatus.EXCEEDED{color:var(--red);}.bstatus.NO_BUDGET{color:var(--mut);}
.budget-details{flex:1;}
.b-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bdr);font-size:12px;}
.b-row:last-child{border:none;}.b-row .val{font-family:var(--mono);}
.timeline{display:flex;flex-direction:column;gap:0;}
.timeline-task{margin-bottom:24px;}
.t-task-id{font-family:var(--mono);font-size:11px;color:var(--blu);margin-bottom:8px;font-weight:600;}
.t-track{border-left:2px solid var(--bdr);padding-left:16px;margin-left:6px;}
.t-item{position:relative;padding:5px 0 10px;}
.t-item::before{content:'';position:absolute;left:-21px;top:10px;width:8px;height:8px;
  border-radius:50%;background:var(--tel);border:2px solid var(--bg);}
.t-item.rolled_back::before{background:var(--mut);}
.t-desc{font-size:12px;color:var(--txt);}
.t-meta{font-size:11px;color:var(--mut);font-family:var(--mono);margin-top:2px;}
.sha{background:#21262d;border-radius:3px;padding:1px 5px;font-size:10px;font-family:var(--mono);color:var(--blu);}
.sbadge{border-radius:3px;padding:1px 6px;font-size:10px;font-weight:600;}
.sbadge.active{background:#1b3a2b;color:var(--grn);}
.sbadge.rolled_back{background:#2a2a2a;color:var(--mut);}
.btn{display:inline-flex;align-items:center;gap:6px;background:var(--tel);color:#000;
  border:none;border-radius:5px;padding:6px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .15s;}
.btn:hover{opacity:.85;}.btn.ghost{background:transparent;color:var(--mut);border:1px solid var(--bdr);}
.btn.ghost:hover{color:var(--txt);border-color:var(--txt);}
.btn-row{display:flex;gap:8px;margin-bottom:16px;}
.empty{color:var(--mut);font-size:12px;padding:20px;text-align:center;
  border:1px dashed var(--bdr);border-radius:8px;}
code{font-family:var(--mono);background:#21262d;padding:1px 5px;border-radius:3px;font-size:11px;}
table{width:100%;border-collapse:collapse;font-size:12px;}
th{text-align:left;padding:6px 8px;color:var(--mut);border-bottom:1px solid var(--bdr);}
td{padding:6px 8px;border-bottom:1px solid var(--bdr);}
tr:last-child td{border:none;}
</style></head><body>`;

  // Find the insertion point — just before the first <div class="tab-bar">
  const TAB_BAR = '\n<div class="tab-bar">';
  const tabIdx = src.indexOf(TAB_BAR);
  if (tabIdx === -1) throw new Error('Cannot find tab-bar div');

  // Remove whatever is between <title>PruvaGraph Analytics</title> and <div class="tab-bar">
  const TITLE_END = '</title>\n';
  const titleIdx = src.indexOf(TITLE_END);
  if (titleIdx === -1) throw new Error('Cannot find </title>');

  src = src.slice(0, titleIdx + TITLE_END.length) + CSS_RESTORE + src.slice(tabIdx);
  console.log('  ✓ Style block restored');
} else {
  console.log('  ✓ Style block present');
}

// ── XSS fix: add _esc() and escape bar chart label ───────────────────────────
const OLD_BAR = `    \${topQ.length > 0 ? \`<div class="bar-chart">\${topQ.map(q => {
      const mx = Math.max(q.tokens_raw, q.tokens_graph, 1);
      const gw = (q.tokens_graph / mx * 100).toFixed(1);
      const rw = (q.tokens_raw   / mx * 100).toFixed(1);
      const lbl = q.question.length > 42 ? q.question.slice(0,40)+'\u2026' : q.question;
      return \`<div class="bar-row" title="\${q.question.replace(/"/g,'&quot;')}">\`;`.slice(0, 50);

// Simpler approach: find the exact unescaped lbl line and replace
const LBL_OLD = "      const lbl = q.question.length > 42 ? q.question.slice(0,40)+'\u2026' : q.question;\n      return `<div class=\"bar-row\" title=\"${q.question.replace(/\"/g,'&quot;')}\">";
const LBL_NEW = `      // _esc: HTML-encode to prevent XSS from question content in element content + attrs
      const _esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
      const lbl = _esc(q.question.length > 42 ? q.question.slice(0,40)+'\u2026' : q.question);
      return \`<div class="bar-row" title="\${_esc(q.question)}">`;

if (!src.includes(LBL_OLD)) {
  // Try alternate (already partially fixed)
  const LBL_ALT = "      const lbl = _esc(q.question.length > 42 ? q.question.slice(0,40)+'\u2026' : q.question);";
  if (src.includes(LBL_ALT)) {
    console.log('  ✓ XSS fix already applied');
  } else {
    console.error('  ✗ Could not find lbl line to patch XSS. Manual fix needed.');
    console.error('    Searched for:', LBL_OLD.slice(0, 80));
    process.exit(1);
  }
} else {
  src = src.replace(LBL_OLD, LBL_NEW);
  console.log('  ✓ XSS fix applied to bar chart label');
}

// ── Write back ────────────────────────────────────────────────────────────────
fs.writeFileSync(EXT, src, 'utf-8');
console.log('  ✓ extension.js written');

// ── Quick validation ──────────────────────────────────────────────────────────
const out = fs.readFileSync(EXT, 'utf-8');
const checks = [
  ['<style>', 'style block open'],
  ['.bar-track{flex:1;}', 'bar-track CSS'],
  ['.donut-wrap{', 'donut-wrap CSS'],
  ['.timeline{', 'timeline CSS'],
  ['id="dashboard"', 'dashboard panel'],
  ['id="tiermap"', 'tiermap panel'],
  ['id="timeline"', 'timeline panel'],
  ['id="budget"', 'budget panel'],
  ['_esc(q.question', 'XSS fix present'],
];
let ok = true;
for (const [needle, label] of checks) {
  if (out.includes(needle)) {
    console.log(`  ✓ ${label}`);
  } else {
    console.error(`  ✗ MISSING: ${label}`);
    ok = false;
  }
}
if (!ok) process.exit(1);
console.log('\nextension.js patched successfully.');

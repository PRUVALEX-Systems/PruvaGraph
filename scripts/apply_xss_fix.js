/**
 * apply_xss_fix.js — patches the bar chart label lines in extension.js
 * to add HTML escaping (_esc helper).
 * Safe: replaces only one exact known string, verifies after.
 */
'use strict';
const fs = require('fs');
const path = require('path');

const EXT = path.join(__dirname, 'extension.js');
let src = fs.readFileSync(EXT, 'utf-8');

// The exact 2 lines we need to replace (from view_file output)
const OLD = `      const lbl = q.question.length > 42 ? q.question.slice(0,40)+'\u2026' : q.question;\r\n      return \`<div class="bar-row" title="\${q.question.replace(/"/g,'&quot;')}">`;

const NEW = `      // _esc: HTML-encode question to prevent XSS in element content and attributes\r\n      const _esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');\r\n      const lbl = _esc(q.question.length > 42 ? q.question.slice(0,40)+'\u2026' : q.question);\r\n      return \`<div class="bar-row" title="\${_esc(q.question)}">`;

// Also try without \r\n (LF-only)
const OLD_LF = OLD.replace(/\r\n/g, '\n');
const NEW_LF = NEW.replace(/\r\n/g, '\n');

let applied = false;
if (src.includes(OLD)) {
  src = src.replace(OLD, NEW);
  applied = true;
  console.log('Applied fix (CRLF)');
} else if (src.includes(OLD_LF)) {
  src = src.replace(OLD_LF, NEW_LF);
  applied = true;
  console.log('Applied fix (LF)');
} else {
  // Check if already fixed
  if (src.includes('_esc(q.question')) {
    console.log('XSS fix already present — skipping');
    applied = true;
  } else {
    // Show context around lbl line for debugging
    const idx = src.indexOf("const lbl = q.question.length > 42");
    console.error('Cannot find target. lbl context:', src.slice(Math.max(0, idx-20), idx+100));
    process.exit(1);
  }
}

if (applied) {
  fs.writeFileSync(EXT, src, 'utf-8');
  // Verify
  const result = fs.readFileSync(EXT, 'utf-8');
  if (result.includes('_esc(q.question')) {
    console.log('  \u2713 _esc present in extension.js');
  } else {
    console.error('  \u2717 _esc NOT found after write');
    process.exit(1);
  }
}
console.log('Done.');

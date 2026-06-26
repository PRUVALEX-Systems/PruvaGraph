/**
 * build.js — esbuild bundler for PruvaGraph VS Code extension
 *
 * Usage:
 *   node build.js           — production bundle (minified)
 *   node build.js --watch   — watch mode (dev)
 *
 * Output: dist/extension.js
 * The extension entry is extension.js at repo root.
 * External modules: vscode (provided by VS Code), node built-ins.
 */
'use strict';

const esbuild = require('esbuild');
const path    = require('path');
const fs      = require('fs');

const isWatch = process.argv.includes('--watch');
const isProd  = !isWatch;

const OUT_DIR  = path.join(__dirname, 'dist');
const OUT_FILE = path.join(OUT_DIR, 'extension.js');

// Ensure dist/ directory exists
fs.mkdirSync(OUT_DIR, { recursive: true });

/** @type {import('esbuild').BuildOptions} */
const config = {
  entryPoints: [path.join(__dirname, 'extension.js')],
  bundle:      true,
  outfile:     OUT_FILE,
  format:      'cjs',          // VS Code extensions use CommonJS
  platform:    'node',
  target:      'node16',       // VS Code 1.85+ runs Node 18, but 16 is safe
  sourcemap:   !isProd,        // source maps for dev only
  minify:      isProd,
  // External: vscode API + all Node built-ins (never bundled)
  external: [
    'vscode',
    'fs', 'path', 'os', 'child_process', 'stream', 'util', 'events',
    'net', 'http', 'https', 'url', 'crypto', 'zlib', 'assert',
  ],
  // Suppress "use client"/"use server" React warnings (not applicable here)
  logLevel: 'info',
  // Keep function names for better error messages
  keepNames: true,
  // Define NODE_ENV for dead-code elimination
  define: { 'process.env.NODE_ENV': isProd ? '"production"' : '"development"' },
};

async function main() {
  if (isWatch) {
    const ctx = await esbuild.context(config);
    await ctx.watch();
    console.log('[esbuild] Watching for changes → dist/extension.js');
  } else {
    const result = await esbuild.build(config);
    if (result.errors.length > 0) {
      process.exit(1);
    }
    const stat = fs.statSync(OUT_FILE);
    const kb   = (stat.size / 1024).toFixed(1);
    console.log(`[esbuild] Built dist/extension.js (${kb} KB, minified)`);
  }
}

main().catch(err => { console.error(err); process.exit(1); });

/**
 * benchmarks/driftguard.bench.ts
 *
 * Measures DriftGuard hallucination detection scan performance.
 * Contract: Full workspace scan of 50-file TS project must complete in < 2s.
 *
 * Run: npm run bench -- --reporter=verbose benchmarks/driftguard.bench.ts
 */

import { bench, describe, expect, beforeAll, afterAll } from "vitest";
import * as path from "path";
import * as fs from "fs/promises";

// ─── Contract Thresholds ────────────────────────────────────────────────────
const CONTRACTS = {
  FULL_SCAN_50_FILES_MS: 2000,      // Full workspace scan, 50 TS files
  SINGLE_FILE_SCAN_MS: 100,         // Scan one file for symbol validation
  INDEX_BUILD_MS: 3000,             // Build driftguard_index from package.json dependencies
  INCREMENTAL_UPDATE_MS: 200,       // Re-index after single file change (hot path)
  SYMBOL_LOOKUP_MS: 5,              // Single validate_symbol() call (DB lookup)
  IMPORT_CHECK_MS: 10,              // Single check_import() call
} as const;

// ─── Fixture Content ─────────────────────────────────────────────────────────

/** A realistic TypeScript file with several API calls to validate */
const REALISTIC_TS_FILE = `
import { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Route, Switch } from 'react-router-dom';
import axios from 'axios';

// This should be caught: useStateInvalid is hallucinated
const [count, setCount] = useStateInvalid(0);

// This should pass: useState is valid
const [name, setName] = useState<string>('');

// This should be caught: axios.getAsync does not exist
const response = await axios.getAsync('/api/users');

// This should pass: axios.get is valid
const data = await axios.get('/api/users');

export function MyComponent() {
  useEffect(() => {
    console.log('mounted');
  }, []);

  // Hallucinated hook
  const handler = useCallbackImproved(() => {}, []);

  return null;
}
`;

/** Generate N unique TypeScript fixture files */
async function generateFixtureWorkspace(dir: string, fileCount: number): Promise<void> {
  await fs.mkdir(dir, { recursive: true });

  // package.json for dependency indexing
  await fs.writeFile(
    path.join(dir, "package.json"),
    JSON.stringify({
      name: "bench-workspace",
      dependencies: {
        react: "^18.2.0",
        "react-router-dom": "^6.11.0",
        axios: "^1.4.0",
        typescript: "^5.1.0",
      },
    }, null, 2)
  );

  // Generate TypeScript files
  for (let i = 0; i < fileCount; i++) {
    const content = i % 5 === 0
      ? REALISTIC_TS_FILE  // Every 5th file has hallucinations
      : `// Clean file ${i}\nimport { useState } from 'react';\nexport const Component${i} = () => null;\n`;

    await fs.writeFile(
      path.join(dir, `component-${i.toString().padStart(3, "0")}.tsx`),
      content
    );
  }
}

// ─── Benchmarks ─────────────────────────────────────────────────────────────

describe("DriftGuard Performance", () => {
  const fixtureDir50 = path.join(process.cwd(), ".bench-tmp", "workspace-50");
  const fixtureDir200 = path.join(process.cwd(), ".bench-tmp", "workspace-200");
  let driftGuard: any;

  beforeAll(async () => {
    // Generate fixture workspaces
    await Promise.all([
      generateFixtureWorkspace(fixtureDir50, 50),
      generateFixtureWorkspace(fixtureDir200, 200),
    ]);

    // Initialize DriftGuard
    const { DriftGuardModule } = await import("../packages/module-driftguard/src/index");
    const { GraphStore } = await import("../packages/core-engine/src/db/connection");
    const dbPath = path.join(process.cwd(), ".bench-tmp", "driftguard.bench.db");
    const store = new GraphStore(dbPath);
    store.migrate();
    driftGuard = new DriftGuardModule(store.scope("driftguard"));
  });

  afterAll(async () => {
    await fs.rm(path.join(process.cwd(), ".bench-tmp"), { recursive: true, force: true });
  });

  // ─── Index Building ──────────────────────────────────────────────────────

  bench(
    "index_build — build driftguard_index from node_modules types",
    async () => {
      const start = performance.now();
      await driftGuard.buildIndex(fixtureDir50);
      const elapsed = performance.now() - start;
      expect(elapsed, `Index build exceeded ${CONTRACTS.INDEX_BUILD_MS}ms: ${elapsed.toFixed(1)}ms`).toBeLessThan(CONTRACTS.INDEX_BUILD_MS);
    },
    { iterations: 3, warmupIterations: 1 }
  );

  // ─── Symbol Validation ───────────────────────────────────────────────────

  bench(
    "validate_symbol — single known-good symbol lookup",
    async () => {
      const start = performance.now();
      await driftGuard.validateSymbol("useState", "react");
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.SYMBOL_LOOKUP_MS);
    },
    { iterations: 1000, warmupIterations: 100 }
  );

  bench(
    "validate_symbol — hallucinated symbol (not in index)",
    async () => {
      const start = performance.now();
      const result = await driftGuard.validateSymbol("useStateInvalid", "react");
      const elapsed = performance.now() - start;
      expect(result.isHallucination).toBe(true);
      expect(elapsed).toBeLessThan(CONTRACTS.SYMBOL_LOOKUP_MS);
    },
    { iterations: 1000, warmupIterations: 100 }
  );

  bench(
    "check_import — single import validation",
    async () => {
      const start = performance.now();
      await driftGuard.checkImport("react");
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.IMPORT_CHECK_MS);
    },
    { iterations: 500, warmupIterations: 50 }
  );

  // ─── File Scanning ───────────────────────────────────────────────────────

  bench(
    "scan_file — single file with mixed valid/hallucinated symbols",
    async () => {
      const tmpFile = path.join(fixtureDir50, "_bench-single.tsx");
      await fs.writeFile(tmpFile, REALISTIC_TS_FILE);

      const start = performance.now();
      const diagnostics = await driftGuard.scanFile(tmpFile);
      const elapsed = performance.now() - start;

      expect(elapsed).toBeLessThan(CONTRACTS.SINGLE_FILE_SCAN_MS);
      // Should catch at least 2 hallucinations in REALISTIC_TS_FILE
      expect(diagnostics.length).toBeGreaterThanOrEqual(2);
    },
    { iterations: 20, warmupIterations: 3 }
  );

  // ─── PRIMARY CONTRACT ────────────────────────────────────────────────────

  bench(
    "FULL_SCAN — 50-file workspace [PRIMARY CONTRACT ≤ 2s]",
    async () => {
      const start = performance.now();
      const allDiagnostics = await driftGuard.scanWorkspace(fixtureDir50);
      const elapsed = performance.now() - start;

      // Primary contract assertion
      expect(
        elapsed,
        `Full scan of 50-file workspace exceeded ${CONTRACTS.FULL_SCAN_50_FILES_MS}ms contract: ${elapsed.toFixed(1)}ms`
      ).toBeLessThan(CONTRACTS.FULL_SCAN_50_FILES_MS);

      // Quality assertion: should have found hallucinations in every 5th file
      const hallucinations = allDiagnostics.filter((d: any) => d.isHallucination);
      expect(hallucinations.length).toBeGreaterThan(0);

      console.log(
        `  ✅ Scanned 50 files in ${elapsed.toFixed(1)}ms — found ${hallucinations.length} hallucinations`
      );
    },
    { iterations: 5, warmupIterations: 1 }
  );

  bench(
    "FULL_SCAN — 200-file workspace (stress test, no hard contract)",
    async () => {
      const start = performance.now();
      await driftGuard.scanWorkspace(fixtureDir200);
      const elapsed = performance.now() - start;
      // Informational — linear scaling check
      const perFileMs = elapsed / 200;
      console.log(`  200-file scan: ${elapsed.toFixed(1)}ms (${perFileMs.toFixed(1)}ms/file)`);
      // Soft contract: should scale roughly linearly (not more than 5x slower for 4x files)
      expect(elapsed).toBeLessThan(CONTRACTS.FULL_SCAN_50_FILES_MS * 5);
    },
    { iterations: 3, warmupIterations: 1 }
  );

  // ─── Incremental Update ──────────────────────────────────────────────────

  bench(
    "incremental_update — re-scan single changed file (hot path)",
    async () => {
      // Simulate a file save
      const changedFile = path.join(fixtureDir50, "component-000.tsx");
      await fs.writeFile(changedFile, REALISTIC_TS_FILE + "\n// edit\n");

      const start = performance.now();
      await driftGuard.scanFile(changedFile);   // incremental — only re-scans the changed file
      const elapsed = performance.now() - start;

      expect(elapsed).toBeLessThan(CONTRACTS.INCREMENTAL_UPDATE_MS);
    },
    { iterations: 30, warmupIterations: 5 }
  );
});

// ─── Exported contract map for CI assertion ──────────────────────────────────
export const DRIFTGUARD_CONTRACTS = CONTRACTS;

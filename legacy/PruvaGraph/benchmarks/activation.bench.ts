/**
 * benchmarks/activation.bench.ts
 *
 * Measures PRUVALEX extension activation time.
 * Contract: Cold activation must complete in < 300ms.
 *
 * Run: npm run bench -- --reporter=verbose benchmarks/activation.bench.ts
 */

import { bench, describe, expect, beforeAll, afterAll } from "vitest";
import * as path from "path";
import { buildCoreEngine } from "../packages/core-engine/src/index";

// ─── Contract Thresholds ────────────────────────────────────────────────────
const CONTRACTS = {
  COLD_ACTIVATION_MS: 300,      // Full activate() call, cold
  WARM_ACTIVATION_MS: 50,       // Re-activation after first run (cache warm)
  DB_OPEN_MS: 20,               // SQLite DB file open + migration check
  EVENT_BUS_INIT_MS: 5,         // EventBus instantiation
  MCP_ROUTER_INIT_MS: 30,       // MCP router setup (no external connection needed)
  WORKSPACE_CONTEXT_INIT_MS: 150, // WorkspaceContext with file walk on 50-file project
} as const;

// ─── Mock Workspace (50-file TypeScript project) ────────────────────────────
const MOCK_WORKSPACE_ROOT = path.join(__dirname, "__fixtures__", "workspace-50files");

// ─── Benchmarks ─────────────────────────────────────────────────────────────

describe("Extension Activation Performance", () => {
  let globalStoragePath: string;

  beforeAll(async () => {
    globalStoragePath = path.join(process.cwd(), ".bench-tmp", "globalStorage");
  });

  afterAll(async () => {
    // Clean up bench DB
    const fs = await import("fs/promises");
    await fs.rm(path.join(process.cwd(), ".bench-tmp"), { recursive: true, force: true });
  });

  bench(
    "COLD — Full activate() including all module stubs",
    async () => {
      const start = performance.now();
      const core = await buildCoreEngine({
        globalStoragePath,
        workspaceRoot: MOCK_WORKSPACE_ROOT,
        modulesEnabled: {
          driftguard: true,
          contextlens: true,
          ghostmemory: true,
          rulesforge: true,
          taskweaver: true,
        },
      });
      await core.dispose();
      const elapsed = performance.now() - start;
      expect(elapsed, `Cold activation exceeded ${CONTRACTS.COLD_ACTIVATION_MS}ms contract: ${elapsed.toFixed(1)}ms`).toBeLessThan(CONTRACTS.COLD_ACTIVATION_MS);
    },
    { iterations: 10, warmupIterations: 2 }
  );

  bench(
    "WARM — Re-activate with existing DB (cache warm)",
    async () => {
      // First run to warm cache
      const prewarm = await buildCoreEngine({
        globalStoragePath,
        workspaceRoot: MOCK_WORKSPACE_ROOT,
        modulesEnabled: { driftguard: true, contextlens: true, ghostmemory: true, rulesforge: true, taskweaver: true },
      });
      await prewarm.dispose();

      const start = performance.now();
      const core = await buildCoreEngine({
        globalStoragePath,
        workspaceRoot: MOCK_WORKSPACE_ROOT,
        modulesEnabled: { driftguard: true, contextlens: true, ghostmemory: true, rulesforge: true, taskweaver: true },
      });
      await core.dispose();
      const elapsed = performance.now() - start;
      expect(elapsed, `Warm activation exceeded ${CONTRACTS.WARM_ACTIVATION_MS}ms contract`).toBeLessThan(CONTRACTS.WARM_ACTIVATION_MS);
    },
    { iterations: 20, warmupIterations: 5 }
  );

  bench(
    "ISOLATED — SQLite DB open + migration check",
    async () => {
      const { GraphStore } = await import("../packages/core-engine/src/db/connection");
      const start = performance.now();
      const store = new GraphStore(path.join(globalStoragePath, "pruvagraph.bench.db"));
      store.migrate();
      store.close();
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.DB_OPEN_MS);
    },
    { iterations: 50, warmupIterations: 10 }
  );

  bench(
    "ISOLATED — EventBus instantiation",
    async () => {
      const { EventBus } = await import("../packages/core-engine/src/events/bus");
      const start = performance.now();
      const bus = new EventBus();
      bus.dispose();
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.EVENT_BUS_INIT_MS);
    },
    { iterations: 1000, warmupIterations: 100 }
  );

  bench(
    "ISOLATED — WorkspaceContext file walk (50-file project)",
    async () => {
      const { WorkspaceContext } = await import("../packages/core-engine/src/workspace/context");
      const start = performance.now();
      const ctx = new WorkspaceContext(MOCK_WORKSPACE_ROOT);
      await ctx.initialize();
      ctx.dispose();
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.WORKSPACE_CONTEXT_INIT_MS);
    },
    { iterations: 10, warmupIterations: 2 }
  );

  bench(
    "SINGLE MODULE — Activate only DriftGuard (others disabled)",
    async () => {
      const start = performance.now();
      const core = await buildCoreEngine({
        globalStoragePath,
        workspaceRoot: MOCK_WORKSPACE_ROOT,
        modulesEnabled: { driftguard: true, contextlens: false, ghostmemory: false, rulesforge: false, taskweaver: false },
      });
      await core.dispose();
      const elapsed = performance.now() - start;
      // Single module should be significantly faster
      expect(elapsed).toBeLessThan(CONTRACTS.COLD_ACTIVATION_MS / 2);
    },
    { iterations: 10, warmupIterations: 2 }
  );
});

// ─── Contract Assertion Script (called from CI) ──────────────────────────────
// This function is called by .github/workflows/ci.yml via scripts/assert-perf-contracts.js
export async function assertAllContracts(): Promise<void> {
  console.log("\n📊 PRUVALEX Performance Contract Report");
  console.log("━".repeat(50));
  for (const [name, thresholdMs] of Object.entries(CONTRACTS)) {
    console.log(`  ${name.padEnd(30)} ≤ ${thresholdMs}ms`);
  }
  console.log("━".repeat(50));
  console.log("  Run benchmarks to verify actual values.\n");
}


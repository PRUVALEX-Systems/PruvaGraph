/**
 * benchmarks/ghostmemory.bench.ts
 *
 * Measures GhostMemory recall performance at scale.
 * Contract: Semantic recall over 10,000 entries must complete in < 150ms.
 *
 * Run: npm run bench -- --reporter=verbose benchmarks/ghostmemory.bench.ts
 */

import { bench, describe, expect, beforeAll, afterAll } from "vitest";
import * as path from "path";
import * as crypto from "crypto";

// ─── Contract Thresholds ────────────────────────────────────────────────────
const CONTRACTS = {
  RECALL_100_ENTRIES_MS: 20,    // recall() over 100 stored memories
  RECALL_1K_ENTRIES_MS: 50,     // recall() over 1,000 stored memories
  RECALL_10K_ENTRIES_MS: 150,   // recall() over 10,000 stored memories (primary contract)
  STORE_SINGLE_MS: 30,          // store_memory() for one entry (includes embed + write)
  STORE_BATCH_100_MS: 500,      // batch insert 100 memories
  EMBED_SINGLE_MS: 20,          // embedding generation time for one string
} as const;

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Generate a realistic fake memory entry */
function makeFakeMemory(index: number) {
  const topics = [
    "authentication flow using JWT tokens with refresh rotation",
    "PostgreSQL index strategy for time-series data",
    "React context vs Zustand for global state management",
    "EU AI Act Article 9 risk management documentation requirements",
    "TypeScript discriminated unions for type-safe event handling",
    "Hexagonal architecture ports and adapters pattern",
    "German banking compliance KYC AML requirements",
    "Tree-sitter incremental parsing for large TypeScript files",
  ];
  return {
    id: crypto.randomUUID(),
    content: `Memory ${index}: ${topics[index % topics.length]}. Additional context about implementation details and trade-offs in the current project.`,
    tags: ["typescript", "architecture", "project-alpha"].slice(0, (index % 3) + 1),
    project: index % 3 === 0 ? "pruvagraph" : index % 3 === 1 ? "pruvalex" : "client-alpha",
  };
}

// ─── Benchmarks ─────────────────────────────────────────────────────────────

describe("GhostMemory Performance", () => {
  let ghostMemory: any;
  let dbPath: string;

  beforeAll(async () => {
    dbPath = path.join(process.cwd(), ".bench-tmp", "ghostmemory.bench.db");

    const { GhostMemoryModule } = await import("../packages/module-ghostmemory/src/index");
    const { GraphStore } = await import("../packages/core-engine/src/db/connection");
    const store = new GraphStore(dbPath);
    store.migrate();
    ghostMemory = new GhostMemoryModule(store.scope("ghostmemory"));
  });

  afterAll(async () => {
    const fs = await import("fs/promises");
    await fs.rm(path.join(process.cwd(), ".bench-tmp"), { recursive: true, force: true });
  });

  // ─── Embedding ───────────────────────────────────────────────────────────

  bench(
    "embed — single string embedding generation",
    async () => {
      const start = performance.now();
      await ghostMemory.embed("TypeScript discriminated unions for event handling");
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.EMBED_SINGLE_MS);
    },
    { iterations: 50, warmupIterations: 5 }
  );

  // ─── Store ───────────────────────────────────────────────────────────────

  bench(
    "store_memory — single entry (embed + write)",
    async () => {
      const entry = makeFakeMemory(Math.floor(Math.random() * 1000));
      const start = performance.now();
      await ghostMemory.storeMemory(entry.content, entry.tags, entry.project);
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.STORE_SINGLE_MS);
    },
    { iterations: 30, warmupIterations: 5 }
  );

  // ─── Recall at scale ─────────────────────────────────────────────────────

  bench(
    "recall_relevant — 100 entries, top_k=5",
    async () => {
      // Pre-seed 100 entries
      await Promise.all(
        Array.from({ length: 100 }, (_, i) => {
          const m = makeFakeMemory(i);
          return ghostMemory.storeMemory(m.content, m.tags, m.project);
        })
      );

      const start = performance.now();
      await ghostMemory.recallRelevant("TypeScript architecture patterns", 5);
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.RECALL_100_ENTRIES_MS);
    },
    { iterations: 20, warmupIterations: 3 }
  );

  bench(
    "recall_relevant — 1,000 entries, top_k=10",
    async () => {
      // Pre-seed 1,000 entries
      await Promise.all(
        Array.from({ length: 1000 }, (_, i) => {
          const m = makeFakeMemory(i);
          return ghostMemory.storeMemory(m.content, m.tags, m.project);
        })
      );

      const start = performance.now();
      await ghostMemory.recallRelevant("EU AI Act compliance documentation requirements", 10);
      const elapsed = performance.now() - start;
      expect(elapsed).toBeLessThan(CONTRACTS.RECALL_1K_ENTRIES_MS);
    },
    { iterations: 10, warmupIterations: 2 }
  );

  bench(
    "recall_relevant — 10,000 entries, top_k=10 [PRIMARY CONTRACT]",
    async () => {
      // Pre-seed to 10,000 entries total
      const batchSize = 500;
      for (let batch = 0; batch < 10000 / batchSize; batch++) {
        await Promise.all(
          Array.from({ length: batchSize }, (_, i) => {
            const m = makeFakeMemory(batch * batchSize + i);
            return ghostMemory.storeMemory(m.content, m.tags, m.project);
          })
        );
      }

      const query = "hexagonal architecture ports adapters dependency injection";
      const start = performance.now();
      const results = await ghostMemory.recallRelevant(query, 10);
      const elapsed = performance.now() - start;

      // Assert contract
      expect(elapsed, `GhostMemory recall over 10k entries exceeded ${CONTRACTS.RECALL_10K_ENTRIES_MS}ms: ${elapsed.toFixed(1)}ms`).toBeLessThan(CONTRACTS.RECALL_10K_ENTRIES_MS);

      // Assert result quality (should return exactly top_k results)
      expect(results).toHaveLength(10);
      // All results should have similarity scores
      expect(results[0]).toHaveProperty("similarity");
      // Results should be ordered by similarity (descending)
      expect(results[0].similarity).toBeGreaterThanOrEqual(results[9].similarity);
    },
    { iterations: 5, warmupIterations: 1 }
  );

  // ─── DB Size Governance ──────────────────────────────────────────────────

  bench(
    "DB size after 10,000 entries (< 50MB contract)",
    async () => {
      const fs = await import("fs/promises");
      const stat = await fs.stat(dbPath);
      const sizeKb = stat.size / 1024;
      const sizeMb = sizeKb / 1024;

      console.log(`  ghostmemory.bench.db size: ${sizeMb.toFixed(2)}MB`);
      expect(sizeMb, `DB size exceeded 50MB after 10k entries: ${sizeMb.toFixed(2)}MB`).toBeLessThan(50);
    },
    { iterations: 1 }
  );
});

// ─── Exported contract map for CI assertion ──────────────────────────────────
export const GHOSTMEMORY_CONTRACTS = CONTRACTS;


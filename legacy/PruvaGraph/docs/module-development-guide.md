# PRUVALEX Module Development Guide

> Build a module that plugs into the PRUVALEX engine and gets a full SQLite store, MCP router, workspace context, and event bus — for free.

---

## What Is an PRUVALEX Module?

An PRUVALEX module is a TypeScript package that implements the `PRUVALEXModule` interface and receives the `CoreEngineAPI` at activation time. In exchange for implementing this interface, your module automatically gets:

- A scoped slice of the shared `pruvagraph.db` SQLite database.
- Access to the shared MCP router (your tool calls are auto-logged to `token_ledger`).
- Real-time workspace context: file tree, AST cache, package manifest.
- An in-process event bus for reacting to (and emitting) cross-module events.
- A shared webview host for rendering UI panels.

You write zero infrastructure code. You only write business logic.

---

## Prerequisites

- Node.js ≥ 20
- TypeScript ≥ 5.1
- Basic knowledge of VS Code extension APIs

---

## Step 1: Create the Module Package

```bash
# From the pruvagraph repo root:
mkdir -p packages/module-yourmodule/src
cd packages/module-yourmodule

# Initialize as a workspace package
cat > package.json << 'EOF'
{
  "name": "@pruvalex/module-yourmodule",
  "version": "0.1.0",
  "private": true,
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc --build",
    "test": "vitest run",
    "lint": "eslint src --ext .ts"
  },
  "dependencies": {
    "@pruvalex/shared-types": "workspace:*",
    "@pruvalex/core-engine": "workspace:*"
  },
  "devDependencies": {
    "vitest": "^1.0.0",
    "@types/vscode": "^1.85.0"
  }
}
EOF
```

---

## Step 2: Implement the Module Contract

```typescript
// packages/module-yourmodule/src/index.ts

import type * as vscode from "vscode";
import type { PRUVALEXModule, CoreEngineAPI } from "@pruvalex/shared-types";
import { YourModuleRepository } from "./repository";

export class YourModuleModule implements PRUVALEXModule {
  readonly id: string = "yourmodule";   // must be unique across all modules

  activate(deps: CoreEngineAPI): vscode.Disposable {
    const repo = new YourModuleRepository(deps.db.scope("yourmodule"));

    // Register your MCP tools
    deps.mcp.registerTool("do_something", async (args: unknown) => {
      // your logic here
      return { result: "done" };
    });

    // Subscribe to events (optional)
    const sub = deps.events.on("suggestion:accepted", ({ diff }) => {
      repo.recordAcceptance(diff);
    });

    // Emit events (optional)
    deps.events.emit("yourmodule:ready", { moduleId: this.id });

    // Return a Disposable — called when VS Code deactivates the extension
    // or when the user toggles off this module in settings.
    return {
      dispose: () => {
        sub.dispose();
        // clean up any timers, watchers, etc.
      },
    };
  }
}
```

**What you must NOT do:**
```typescript
// ❌ FORBIDDEN — will fail the architecture lint check
import Database from "better-sqlite3";
import { Client } from "@modelcontextprotocol/sdk";
import { GhostMemoryModule } from "../module-ghostmemory/src/index";
```

---

## Step 3: Add the Repository

```typescript
// packages/module-yourmodule/src/repository.ts

import type { ModuleRepository } from "@pruvalex/core-engine";

export interface YourModuleEntry {
  id: string;
  content: string;
  created_at: number;
}

export class YourModuleRepository {
  constructor(private repo: ModuleRepository) {}

  insert(entry: Omit<YourModuleEntry, "created_at">): void {
    this.repo.run(
      // Table name MUST start with your module ID
      "INSERT INTO yourmodule_entries (id, content, created_at) VALUES (?, ?, ?)",
      [entry.id, entry.content, Date.now()]
    );
  }

  getById(id: string): YourModuleEntry | undefined {
    return this.repo.get(
      "SELECT * FROM yourmodule_entries WHERE id = ?",
      [id]
    ) as YourModuleEntry | undefined;
  }

  recordAcceptance(diff: string): void {
    // example of reacting to an event
    this.insert({ id: crypto.randomUUID(), content: diff });
  }
}
```

---

## Step 4: Add the SQL Migration

```sql
-- db/migrations/005_yourmodule.sql
-- (use the next available number — check existing files)

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS yourmodule_entries (
  id          TEXT    PRIMARY KEY,
  content     TEXT    NOT NULL,
  created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_yourmodule_entries_created_at
  ON yourmodule_entries (created_at DESC);

COMMIT;
```

Also add your table to `db/schema/pruvagraph.sql` (the canonical review copy).

---

## Step 5: Register the Module

Edit `extension/src/di/container.ts`:

```typescript
import { YourModuleModule } from "@pruvalex/module-yourmodule";

// Inside buildCoreEngine():
registry.register(
  driftguard,
  contextlens,
  ghostmemory,
  rulesforge,
  taskweaver,
  new YourModuleModule()   // ← add your module here
);
```

Add the settings toggle to `extension/package.json`:
```json
"pruvagraph.modules.yourmodule.enabled": {
  "type": "boolean",
  "default": true,
  "description": "Enable YourModule — [description of what it does]."
}
```

---

## Step 6: Add MCP Tool Documentation

Add your tool to the MCP Tool Manifest table in `README.md`:

| Tool | Owning Module | Backed By |
|---|---|---|
| `do_something(args)` | YourModule | `yourmodule_entries` |

---

## Step 7: Write Tests

```typescript
// packages/module-yourmodule/src/__tests__/yourmodule.test.ts

import { describe, it, expect, vi } from "vitest";
import { YourModuleModule } from "../index";
import type { CoreEngineAPI } from "@pruvalex/shared-types";

// Stub the ports — no real DB, no real MCP client
function makeMockCoreAPI(): CoreEngineAPI {
  return {
    db: {
      scope: vi.fn().mockReturnValue({
        run: vi.fn(),
        get: vi.fn(),
        all: vi.fn(),
      }),
    },
    mcp: {
      call: vi.fn(),
      registerTool: vi.fn(),
    },
    workspace: {
      getPackageManifest: vi.fn().mockReturnValue({}),
      getAST: vi.fn(),
      onFileChanged: { event: vi.fn() },
    },
    events: {
      on: vi.fn().mockReturnValue({ dispose: vi.fn() }),
      emit: vi.fn(),
    },
    webview: {
      createPanel: vi.fn(),
    },
  };
}

describe("YourModuleModule", () => {
  it("activates without throwing", () => {
    const module = new YourModuleModule();
    const api = makeMockCoreAPI();
    expect(() => module.activate(api)).not.toThrow();
  });

  it("registers its MCP tools on activation", () => {
    const module = new YourModuleModule();
    const api = makeMockCoreAPI();
    module.activate(api);
    expect(api.mcp.registerTool).toHaveBeenCalledWith("do_something", expect.any(Function));
  });

  it("disposes cleanly without errors", () => {
    const module = new YourModuleModule();
    const api = makeMockCoreAPI();
    const disposable = module.activate(api);
    expect(() => disposable.dispose()).not.toThrow();
  });
});
```

---

## Creating Branded Webview Panels

If your module needs a user-facing webview panel (like ContextLens), use the shared `getWebviewShell()` and `DESIGN_TOKENS` from `@pruvalex/shared-ui` to ensure a consistent **PRUVALEX PruvaGraph** look and feel.

### Example: Branded Panel Class

```typescript
// packages/module-yourmodule/src/panel.ts

import * as vscode from 'vscode';
import { getWebviewShell } from '@pruvalex/shared-ui';
import { WebviewHost } from '@pruvalex/shared-types';

export class YourModulePanel {
    private panel: vscode.WebviewPanel | undefined;

    constructor(private host: WebviewHost) {}

    public show(data: any) {
        const panel = this.ensurePanel();
        const htmlContent = this.generateHtml(data);
        panel.webview.html = getWebviewShell('Your Feature', htmlContent);
        panel.title = 'PruvaGraph Your Feature';
    }

    private ensurePanel(): vscode.WebviewPanel {
        if (this.panel) {
            this.panel.reveal();
            return this.panel;
        }

        const panel = this.host.registerPanel('yourmodule', 'Your Feature');
        if (!panel) {
            throw new Error('Unable to create panel.');
        }

        panel.onDidDispose(() => {
            this.panel = undefined;
        });
        this.panel = panel;
        return panel;
    }

    private generateHtml(data: any): string {
        return `
            <section class="card section">
                <h2>Your Feature</h2>
                <p class="muted">Description of what this feature does.</p>
            </section>

            <div class="surface section" style="padding: 22px;">
                <table>
                    <thead>
                        <tr>
                            <th>Column A</th>
                            <th>Column B</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(row => `
                            <tr>
                                <td>${row.a}</td>
                                <td>${row.b}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }
}
```

### UI Tokens Reference

The `DESIGN_TOKENS` CSS from `@pruvalex/shared-ui` includes these CSS classes and variables:

**CSS Variables:**
- `--omni-bg` — Background color
- `--omni-surface` — Card/panel background
- `--omni-border` — Border color
- `--omni-text-primary` — Primary text
- `--omni-text-secondary` — Secondary/muted text
- `--omni-accent` — Brand accent (blue)
- `--omni-warn` — Warning/error state
- `--omni-ok` — Success state

**CSS Classes:**
- `.shell` — Main page wrapper with padding
- `.brandbar` — Header with PRUVALEX PruvaGraph logo
- `.page-title` — Large heading
- `.page-subtitle` — Descriptive subtitle
- `.card` — Elevated card with shadow
- `.surface` — Flat panel surface with border
- `.section` — Vertical spacing container
- `.muted` — Muted text color
- `.inline-copy` — Monospace code/identifier styling
- `.column-grid` — Responsive multi-column layout
- `.badge` — Pill-shaped status indicator

---

## Event Bus Reference

### Events you can consume

| Event | Payload | Emitted By |
|---|---|---|
| `suggestion:accepted` | `{ uri: string; diff: string }` | GhostMemory + RulesForge |
| `checkpoint:created` | `{ taskId: string; files: string[] }` | TaskWeaver |
| `mcp:call` | `{ server, tool, tokensIn, tokensOut, latencyMs }` | Core Engine |
| `drift:detected` | `{ uri: string; symbol: string; reason: string }` | DriftGuard |

### Events you can emit

Prefix your events with your module ID to avoid collisions:
```typescript
// Good
deps.events.emit("yourmodule:analysis_complete", { fileCount: 50 });

// Bad — could collide with existing events
deps.events.emit("analysis_complete", { fileCount: 50 });
```

To add your event to the typed `PRUVALEXEventMap`, open a PR that adds it to `packages/shared-types/src/events.ts`.

---

## Checklist Before Opening a PR

- [ ] Module implements `PRUVALEXModule` interface from `@pruvalex/shared-types`
- [ ] No `import` of `better-sqlite3`, `@modelcontextprotocol/sdk`, or any `module-*` package
- [ ] All SQLite tables follow naming convention: `yourmodule_<tablename>`
- [ ] Migration file added to `db/migrations/` with the next sequential number
- [ ] Canonical schema in `db/schema/pruvagraph.sql` updated
- [ ] Module registered in `di/container.ts` and `package.json` settings
- [ ] Module can be disabled via settings with no impact on other modules
- [ ] Unit tests cover activate/dispose lifecycle and all MCP tools
- [ ] MCP tools listed in `README.md` manifest table
- [ ] PR template checklist completed

---

## Questions?

Open a discussion in the `#contributors` channel on Discord or file a GitHub Discussion tagged `module-development`.

Maintainers review module PRs on Tuesdays and Fridays. Response time: ≤ 48 hours.


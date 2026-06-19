---
name: Module / Feature Request
about: Propose a new PRUVALEX module or a significant feature addition
title: "[MODULE REQUEST] "
labels: ["enhancement", "module-proposal"]
assignees: ""
---

## Request Type
- [ ] New PRUVALEX module (implements `PRUVALEXModule` interface)
- [ ] Feature addition to an existing module
- [ ] New MCP tool / resource
- [ ] Core Engine capability

## Problem Statement
<!-- What developer pain does this solve? Be specific. -->
<!-- Example: "Every time I switch branches, GhostMemory loses track of which task I was working on." -->

## Proposed Solution
<!-- Describe the module or feature you want. -->

### If proposing a new module:

**Module ID:** `module-` (e.g., `module-dockerlens`)  
**Tagline:** (e.g., "Real-time Docker container cost visibility inside VS Code")

**MCP Tools this module would expose:**
| Tool Name | Description | Backed By |
|---|---|---|
| `tool_name(args)` | What it does | DB table / IWorkspaceContext / EventBus |

**SQLite table(s) needed:**
```sql
-- Table naming convention: <modulename>_<tablename>
CREATE TABLE mymodule_entries (
  id TEXT PRIMARY KEY,
  -- ...
);
```

**EventBus events this module would emit or consume:**
| Event | Direction (emit / consume) | Purpose |
|---|---|---|
| `suggestion:accepted` | consume | Example |

**Would this module require Python?**
- [ ] Yes (describe why)
- [ ] No — TypeScript only

### If proposing a feature for an existing module:

**Target module:** (DriftGuard / ContextLens / GhostMemory / RulesForge / TaskWeaver)  
**Feature description:**

## Alternatives Considered
<!-- What other approaches did you consider and why are they worse? -->

## Who Would Use This?
- [ ] Individual developers (free tier)
- [ ] Pro users
- [ ] Teams
- [ ] Enterprise (banking / healthcare / compliance-heavy)

## Are You Willing to Build This?
- [ ] Yes — I want to contribute this module (see [Module Development Guide](../../docs/module-development-guide.md))
- [ ] Yes — with guidance from maintainers
- [ ] No — submitting for the roadmap

---
> **Before submitting:**
> - [ ] I have searched existing issues for similar proposals.
> - [ ] I have read the [Architecture Mandate](../../packages/shared-types/src/module-contract.ts) and confirmed this can be built within the `PRUVALEXModule` contract.


# Pull Request

## Summary
<!-- One paragraph: what does this PR do and why? -->

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] New module (implements `PRUVALEXModule` interface)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Refactor (no behavior change, internal improvement)
- [ ] Performance improvement
- [ ] Documentation only

## Related Issues
Closes # <!-- issue number -->

---

## Architecture Checklist (MANDATORY — PRs failing any of these will not be merged)

### Core Engine Integrity
- [ ] No new `better-sqlite3.Database(...)` call exists outside `core-engine/src/db/connection.ts`
- [ ] No new MCP `Client` instantiation exists outside `core-engine/src/mcp/router.ts`
- [ ] No `module-*` package imports another `module-*` package directly (cross-module communication uses EventBus only)
- [ ] No module performs its own `fs.readdir` / workspace walk (uses `IWorkspaceContext` instead)
- [ ] No module performs its own Tree-sitter parse (uses the shared AST cache via `IWorkspaceContext.getAST`)

### New Module PRs (skip if not adding a module)
- [ ] Module implements `PRUVALEXModule` interface from `shared-types`
- [ ] Module receives all dependencies via constructor injection (no `require` / `import` of concrete DB/MCP classes)
- [ ] All new SQLite tables follow naming convention: `<moduleid>_<tablename>`
- [ ] Module SQL schema is added to `db/migrations/` as a new numbered migration file
- [ ] Module schema is also reflected in `db/schema/pruvagraph.sql` (canonical review copy)
- [ ] Module is registered in `di/container.ts` and wired to `extension.ts`
- [ ] Module can be independently disabled via `pruvagraph.modules.<id>.enabled` with no side effects on other modules
- [ ] Module is toggleable at runtime without VS Code reload

### New MCP Tool PRs (skip if not adding tools)
- [ ] Tool is registered via `core.mcp.registerTool(...)` — not by creating a new MCP server process
- [ ] Tool is listed in the MCP Tool/Resource Manifest in `README.md`
- [ ] Token usage is auto-captured by the existing `IMCPTransport` proxy (no manual logging needed)

### PruvaGraphRunner / Python Engine Changes (skip if not applicable)
- [ ] All failure paths (Python not found, pip fails, venv corrupt) degrade gracefully with a user-visible notification
- [ ] No Python execution occurs on extension activation without workspace context
- [ ] `.venv_pruvagraph` is excluded from `.vscodeignore` and `.gitignore`

---

## Testing

### Tests Added
- [ ] Unit tests for new business logic
- [ ] Integration test for module activation / deactivation
- [ ] Benchmark assertion added if this touches a performance-critical path

### Manual Testing
Describe the manual test you performed:
```
1. Opened workspace: [type of project]
2. Action performed: ...
3. Expected result: ...
4. Actual result: ...
```

### Performance Impact
<!-- Did activation time, memory, or DB size change? Run benchmarks and paste results. -->
```
Before: activation=XXXms, memory=XXmb, db=XXkb
After:  activation=XXXms, memory=XXmb, db=XXkb
```

---

## Screenshots / GIFs
<!-- If this is a UI change, attach a before/after screenshot or a GIF. PRs without visuals for UI changes will be deprioritized. -->

---

## Reviewer Notes
<!-- Anything specific you want reviewers to focus on or be aware of? -->


---
name: Bug Report
about: Something is broken or behaving unexpectedly
title: "[BUG] "
labels: ["bug", "needs-triage"]
assignees: ""
---

## Bug Description
<!-- A clear and concise description of what is broken. -->

## Which Module?
<!-- Check all that apply -->
- [ ] Core Engine (DB / EventBus / MCP Router)
- [ ] DriftGuard (hallucination detection)
- [ ] ContextLens (token cost visibility)
- [ ] GhostMemory (cross-session memory)
- [ ] RulesForge (custom prompt rules)
- [ ] TaskWeaver (checkpoints / rollback)
- [ ] PruvaGraphRunner (Python engine / venv bootstrap)
- [ ] Other (specify below)

## Steps to Reproduce
1. Go to `...`
2. Open file `...`
3. Trigger action `...`
4. See error

## Expected Behavior
<!-- What should have happened? -->

## Actual Behavior
<!-- What actually happened? -->

## Error Output
<!-- Paste the full error from: Help > Toggle Developer Tools > Console -->
```
[paste error here]
```

## PRUVALEX Output Channel Log
<!-- Open View > Output, select "PRUVALEX" from the dropdown, paste relevant lines -->
```
[paste output channel log here]
```

## Environment
| Field | Value |
|---|---|
| PRUVALEX Version | v |
| VS Code Version | |
| OS | Windows / macOS / Linux |
| Node.js Version | |
| Python Version | |
| Active Modules | (list which modules are enabled in settings) |

## `pruvagraph.db` Tables Present?
<!-- Run: sqlite3 ~/.vscode/extensions/pruvalex.pruvagraph-*/pruvagraph.db ".tables" -->
```
[paste output here, or "not applicable"]
```

## Additional Context
<!-- Any other context, screenshots, or workspace setup details. -->

---
> **Quick checks before submitting:**
> - [ ] I have the latest version of PRUVALEX installed.
> - [ ] I have checked the [existing issues](../../issues) for duplicates.
> - [ ] I have read the [troubleshooting guide](../../docs/troubleshooting.md).


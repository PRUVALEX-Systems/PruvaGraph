# Contributing to PRUVALEX PruvaGraph

Thank you for contributing to PRUVALEX PruvaGraph. This guide explains the modular architecture, PR workflow, coding standards, and version sync process.

## Project structure

- `python/`: core PruvaGraph engine and query pipeline.
- `pruvagraph/`: VS Code extension monorepo, shared UI, and feature modules.
- `pruvagraph/extension/`: production TypeScript-based VS Code extension.
- `pruvagraph/extension-standalone/`: legacy standalone extension implementation.
- `pruvagraph/packages/`: reusable libraries and modules such as `shared-ui`, `module-ghostmemory`, and `core-engine`.

## Contribution workflow

1. Fork the repository and create a feature branch.
2. Keep each PR focused on one issue, bug, or feature.
3. Write a clear PR title and description.
4. Reference the issue number if applicable.
5. Add or update tests for all functional changes.
6. Ensure the change follows the modular split between Python engine and extension UI.

## Modular architecture guidance

- Python engine work belongs in `python/pruvagraph/`.
- UI and extension work belongs in `pruvagraph/`.
- Shared UI tokens and shell components live in `pruvagraph/packages/shared-ui/`.
- GhostMemory, DriftGuard, and TaskWeaver are module packages under `pruvagraph/packages/`.
- Keep Python-only logic inside `python/` and avoid mixing VS Code runtime concerns there.

## Coding standards

- Prefer clear, readable, and maintainable code.
- Keep functions small and focused.
- Use descriptive names for variables, functions, and classes.
- Favor explicit behavior over clever shortcuts.
- Maintain the brand style: calm, Nordic, and polished.
- For Python:
  - Follow PEP 8 and use `ruff` for linting.
  - Use type hints where practical.
  - Keep prompt and schema logic deterministic and testable.
- For TypeScript/JS:
  - Follow the monorepo’s existing style.
  - Keep webview UI minimal and consistent with the shareable design tokens.

## PR requirements

- Pass unit and integration tests.
- Pass linting on changed files.
- Keep changes scoped to the intended layer.
- Document new features or behavior changes in `CHANGELOG.md`.
- Add a short note if the PR affects publishing, packaging, or versioning.

## Local setup

### Python

```bash
git clone https://github.com/pruvalex/pruvagraph.git
cd pruvagraph/python
python -m pip install -U pip
pip install -e .
pip install -e .[dev]
```

### Extension

```bash
cd pruvagraph/pruvagraph
npm install
npm run build --workspaces
```

## Running tests

### Python

```bash
cd python
python -m pytest -q
python -m ruff check pruvagraph/ --select F,I
```

### Extension

```bash
cd pruvagraph
npm run lint
npm run test
```

## Version bump script

Use `scripts/bump-version.sh <new-version>` to synchronize:

- `package.json`
- `python/pyproject.toml`
- `python/pruvagraph/__init__.py`
- `pruvagraph/extension/package.json`
- `pruvagraph/extension-standalone/package.json`

Example:

```bash
./scripts/bump-version.sh 1.4.0
```

## Pull request checklist

- [ ] Tests pass locally.
- [ ] Lint passes on changed files.
- [ ] PR is focused and self-contained.
- [ ] Relevant docs and changelog entries are updated.
- [ ] Version sync script used if package or extension versions changed.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.


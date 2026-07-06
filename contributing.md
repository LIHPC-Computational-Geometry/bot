# Contributing to Bot Project

This section is here to explain how to contribute to this project.

## Code of Conduct

By participating in this project, you agree to remain respectful, professional, and collaborative.

## Development Workflow

### 1. Environment setup

We use `uv` for dependency management.

```bash
git checkout -b feature/your-feature-name
uv sync --all-extras --dev
```

If submodules are not initialized yet:

```bash
git submodule update --init --recursive
```

### 2. Coding standards

- **Formatting:** follow standard Python conventions.
- **Docstrings:** add English docstrings for new public classes/functions (Google style preferred).
- **Type hints:** use type hints for new public interfaces.

### 3. Testing requirements

- No contribution is merged without passing tests.
- Add tests for new behavior in `tests/`.
- Ensure existing tests still pass before pushing.

```bash
uv run pytest
```

Useful subsets:

```bash
uv run pytest tests/unit/
uv run pytest tests/system/
```

### 4. Git branching and commits

- Branch names: `feature/...`, `fix/...`, `docs/...`, `refactor/...`, `test/...`
- Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `perf:`)

### Pull request process

1. Update documentation when API or behavior changes.
2. Ensure GitHub Actions CI is green.
3. Open a PR with clear change motivation and impact.
4. A maintainer reviews and provides feedback.

## Documentation references

- Developer index: [doc/index.md](doc/index.md)
- Canonical technical reference: [doc/technical_reference_v1.md](doc/technical_reference_v1.md)
- Focused guides:
  - [doc/architecture.md](doc/architecture.md)
  - [doc/callbacks.md](doc/callbacks.md)
  - [doc/custom_model.md](doc/custom_model.md)

## Troubleshooting

### Graphics issues (Panda3D/Gmsh)

If you are on a headless Linux server and encounter OpenGL issues:

```bash
sudo apt-get install libglu1-mesa libosmesa6
```

### Continuous integration

PRs are automatically checked for:

- Tests and logic (`tests.yml`)
- Lint/format checks (`lint.yml`)
- Coverage reporting
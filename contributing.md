# Contributing to Bot Project 

This section is here to explain how to contribute to this project.

## 📜 Code of Conduct
By participating in this project, you agree to abide by our code of conduct: be respectful, professional, and collaborative.

## 🛠 Development Workflow

### 1. Environment Setup
We use `uv` for all dependency management. To set up your environment:
```bash
git checkout -b feature/your-feature-name
uv sync
```
  
###  2. Coding Standards
- **Formatting:** We follow standard Python conventions. Please ensure your code is clean and readable.
- **Docstrings:** All new functions and classes must include docstrings in Google Style.
- **Type Hints:** Use Python type hints wherever possible to improve maintainability.

### 3. Testing Requirements
- No contribution will be merged without passing tests.
- Add tests for any new feature in the `tests/` directory.
- Ensure your changes do not break existing tests.
- Always run the test suite locally before pushing. In the project root dir, run:
```bash
uv run pytest
```

### 4. Git Branching & Commits

- Branches: Use descriptive names like feature/abc, fix/xyz, or docs/update-readme.

- Commits: Try to use Conventional Commits (e.g., feat: add new mesh generator, fix: resolve libGLU path issue).

### 🚀 Pull Request Process
1. Update the `README.md` or documentation if you changed the API.

2. Ensure the CI pipeline (GitHub Actions) passes on your PR.

3. A maintainer will review your changes and provide feedback.

#u# 🛠 Troubleshooting for Contributors

### Graphics Issues (Panda3D/Gmsh)

If you are working on a headless Linux server and encounter libGLU errors, ensure you have the system dependencies installed:

```Bash
sudo apt-get install libglu1-mesa libosmesa6
```

### Continuous Integration

Your PR will be automatically tested for:
- **Linting & Logic:** via `pytest`.
- **Coverage:** Coverage must not decrease significantly.

- **Documentation:** `pdoc` must be able to build the docs without errors.
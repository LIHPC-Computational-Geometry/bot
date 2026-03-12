# BOT — BlOcking Toolkit

![Tests](https://github.com/franck-ledoux/bot/actions/workflows/tests.yml/badge.svg)
[![codecov](https://codecov.io/gh/franck-ledoux/bot/graph/badge.svg?token=HGY9PK4OA4)](https://codecov.io/gh/franck-ledoux/bot)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**BOT** is a Python research sandbox for developing and testing interactive quad and hex mesh blocking algorithms, with a focus on programmatic and potentially AI-driven workflows.

The project combines a [gmsh](https://gmsh.info/)-based CAD model with a real-time [Panda3D](https://www.panda3d.org/) 3D viewer, both accessible from an interactive IPython session.

---

## Table of Contents

- [Project overview](#project-overview)
- [Architecture](#architecture)
- [Usage](#usage)
- [Development guide](#development-guide)
- [Project structure](#project-structure)
- [Contributing](#contributing)

---

## Project overview

BOT provides a programmable environment where you can:

- Load CAD geometry (`.geo`, `.step`, …) via gmsh/OpenCASCADE.
- Query and mutate the geometry programmatically (add points, query adjacencies, …).
- Visualise the model live in a 3D viewer.
- Pick locations in the viewport and feed them back to the model.

The goal is to build robust, well-specified geometric operations that can later be driven by an AI agent.

---

## Architecture

```
IPython (main thread)                 Panda3D subprocess (main thread)
─────────────────────                 ────────────────────────────────
Model (gmsh / OCC)                    ViewerApp (ShowBase)
  └─ _notify_observers()  ──pipe──►   pipe_reader thread → cmd_queue
                                        └─ _process_commands task
                                             └─ scene.rebuild()
Viewer._send('update', data)
  └─ conn.send(...)        ──pipe──►   same path

Picking (future):
                             ◄──pipe── conn.send(('pick', coords))
Viewer._event_thread
  └─ on_pick(coords)
```

> **Why a subprocess?** On macOS, OpenGL must run on the main thread of the process that owns the window. Spawning Panda3D in a dedicated subprocess leaves IPython's main thread fully interactive. All data exchanged over the pipe is plain picklable dicts — no gmsh dependency on the viewer side.

---

## Usage

### Interactive session (IPython)

```python
import bot

# 1. Load geometry
model = bot.Model()
model.open("data/profil_1.geo")

# 2. Start the viewer (non-blocking — Panda3D runs in a subprocess)
viewer = bot.Viewer()
viewer.connect(model).run()

# 3. Query the model
print(model.get_point_tags())   # [1, 2, 3, 4, 5, 6]
print(model.get_curve_tags())   # [1, 2, 3, 4, 5]

# 4. Mutate — the viewer updates automatically
model.add_point([10.0, 5.0, 0.0])

# 5. React to picking events
viewer.on_pick = lambda coords: model.add_point(coords)

# 6. Standard view shortcuts (in the viewer window)
#    c       — re-centre on model
#    x/y/z   — align to right / front / top view
#    Scroll  — zoom
#    Drag    — rotate   |   Shift+Drag — pan

# 7. Clean shutdown
viewer.stop()
model.finalize()
```

### Render data format

The data dict exchanged between the model and the viewer is a plain Python dict:

```python
{
    'points': [(x, y, z), ...],               # discretised mesh nodes
    'edges':  [(idx_a, idx_b, curve_tag), ...],
    'bounds': {
        'min': [x, y, z], 'max': [x, y, z],
        'center': [x, y, z], 'size': [dx, dy, dz],
    },
}
```

---

## Development guide

We use [uv](https://docs.astral.sh/uv/) for all dependency and environment management.

### Prerequisites

- Python ≥ 3.14
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- On headless Linux: `sudo apt-get install libglu1-mesa libosmesa6`

### 1. Clone and set up

```bash
git clone https://github.com/franck-ledoux/bot.git
cd bot
uv sync          # creates .venv and installs all production + dev dependencies
```

> **Never edit `uv.lock` by hand.** Always commit it — it guarantees every contributor uses the exact same dependency versions.

### 2. Add or remove dependencies

```bash
uv add <package>            # production dependency
uv add --dev <package>      # development-only dependency
uv remove <package>
```

### 3. Run the test suite

```bash
uv run pytest               # runs all tests + coverage (configured in pyproject.toml)
```

Coverage reports are written to:
- **Terminal** — summary after each run.
- **`htmlcov/index.html`** — full line-by-line HTML report.

To run a specific subset:

```bash
uv run pytest tests/unit/           # unit tests only (no display required)
uv run pytest tests/system/         # system tests (subprocess tests open a window)
uv run pytest -k "TestAddPoint"     # filter by name
```

### 4. Generate the documentation

Live preview (auto-refreshes on save):
```bash
uv run pdoc ./bot
```

Build static HTML into `docs/`:
```bash
uv run pdoc ./bot -o ./docs
```

### 5. Continuous integration

Each push and pull request automatically triggers a GitHub Actions workflow that:

- Runs the full test suite on Ubuntu.
- Uploads coverage to [Codecov](https://codecov.io/gh/franck-ledoux/bot).

---

## Project structure

```
bot/
├── bot/
│   ├── core/
│   │   └── cad.py          # Model — gmsh/OCC geometry + observer pattern
│   ├── view/
│   │   ├── scene.py         # Scene + Gizmo — Panda3D geometry rendering
│   │   └── utils.py         # View-layer utilities (ColorGenerator, …)
│   ├── control/
│   │   ├── camera.py        # CameraController — orthographic camera
│   │   ├── keyboard.py      # KeyboardHandler
│   │   └── mouse.py         # MouseHandler
│   └── viewer/
│       ├── viewer.py        # Viewer — public API, manages the subprocess
│       └── app.py           # ViewerApp — Panda3D ShowBase (runs in subprocess)
├── tests/
│   ├── unit/                # Isolated class tests (no display required)
│   └── system/              # End-to-end workflow tests
├── data/                    # Sample .geo files
├── docs/                    # Generated HTML documentation
├── bot_config.toml          # Runtime configuration (scene, camera)
├── pyproject.toml           # Project metadata, dependencies, pytest config
└── uv.lock                  # Deterministic lockfile — always commit this
```

---

## Contributing

We follow a **branch-and-pull-request** workflow. Direct pushes to `main` are not allowed.

### Branch naming

| Type | Pattern | Example |
|---|---|---|
| New feature | `feature/<short-description>` | `feature/picking-support` |
| Bug fix | `fix/<short-description>` | `fix/camera-clip-plane` |
| Documentation | `docs/<short-description>` | `docs/update-readme` |
| Refactoring | `refactor/<short-description>` | `refactor/scene-rename` |
| Tests | `test/<short-description>` | `test/add-system-viewer` |

### Workflow

```bash
# 1. Branch off main (always keep main up to date first)
git checkout main && git pull
git checkout -b feature/my-feature

# 2. Develop, commit often
git add <files>
git commit -m "feat: add picking event callback"

# 3. Keep your branch up to date
git fetch origin && git rebase origin/main

# 4. Push and open a pull request
git push -u origin feature/my-feature
# → open a PR on GitHub targeting main
```

### Commit message conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short summary>

Types: feat | fix | docs | refactor | test | chore | perf
```

Examples:
```
feat: add on_pick callback to Viewer
fix: prevent camera clipping on small models
test: add system tests for viewer subprocess lifecycle
docs: document Scene and Gizmo classes
```

### Pull request checklist

Before requesting a review, make sure:

- [ ] All existing tests pass: `uv run pytest`
- [ ] New code is covered by unit or system tests.
- [ ] Docstrings are present on all new public classes and methods (English, Google style).
- [ ] `uv.lock` is committed if dependencies changed.
- [ ] The PR description explains **what** changed and **why**.
- [ ] The branch is rebased on the latest `main`.

### Code standards

- **Formatting:** standard Python conventions (PEP 8).
- **Docstrings:** English, Google style, on all public symbols.
- **Type hints:** use them on all new function signatures.
- **No direct push to `main`** — all changes go through a PR.

### Troubleshooting

**Panda3D / OpenGL errors on headless Linux:**
```bash
sudo apt-get install libglu1-mesa libosmesa6
```

**Subprocess tests open a window — is that expected?**
Yes. `tests/system/test_viewer_subprocess.py` starts the real Panda3D process. Those tests are automatically skipped in headless environments (`DISPLAY` / `WAYLAND_DISPLAY` not set).

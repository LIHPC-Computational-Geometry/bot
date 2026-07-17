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

- Load CAD geometry (`.geo`, `.step`, ...) via gmsh/OpenCASCADE.
- Query and mutate CAD entities (points, curves, adjacency).
- Create and edit spline curves (Bezier/NURBS) through FerriSpline.
- Visualise both CAD and spline geometry in a live 3D viewer.
- Use raycasting-based picking and control-point dragging.

The goal is to develop robust geometric operations with a clean interface that can be driven interactively or by higher-level automation/AI agents.

---

## Architecture

```
IPython / Python script (parent process)      Panda3D subprocess (child process)
────────────────────────────────────────       ──────────────────────────────────
CADModel + SplineModel                        View (ShowBase)
  └─ Observable._notify_observers() ─pipe─►    pipe_reader thread -> cmd_queue
Viewer + ACL adapters                           -> process commands -> scene patch
  └─ send(ScenePayload / ViewerCommand)      ◄─ send(ViewEventType, data)
```

> **Why a subprocess?** OpenGL must run on the main thread of the process owning the window. Running Panda3D in a dedicated subprocess keeps the parent Python session responsive.

See [doc/architecture.md](doc/architecture.md) for the focused IPC guide and [doc/technical_reference_v1.md](doc/technical_reference_v1.md) for the full architecture and data contracts.

---

## Usage

### Interactive session (IPython)

```python
import bot
from bot.core.spline import SplineModel, BEZIER_TYP
from bot.viewer.contracts import ViewEventType

# 1. Load CAD geometry
cad_model = bot.CADModel()
cad_model.open("data/profil_1.geo")

# 2. Optional spline model (FerriSpline-backed)
spline_model = SplineModel()
spline_model.add_curve(
    BEZIER_TYP,
    degree=3,
    control_points=[[0.0, 0.0, 0.0], [1.0, 3.0, 0.0], [4.0, 3.0, 0.0], [5.0, 0.0, 0.0]],
)

# 3. Start viewer (non-blocking; child process)
viewer = bot.Viewer()
viewer.connect_models(cad_model, spline_model).run()

# 4. Query and mutate CAD
print(cad_model.get_point_tags())
print(cad_model.get_curve_tags())
cad_model.add_point([10.0, 5.0, 0.0])  # observer update -> scene update

# 5. React to visual events
def on_curve_selected(curve_tag):
    print("Selected:", curve_tag)

viewer.add_callback(ViewEventType.CURVE_SELECTED, on_curve_selected)

# 6. Clean shutdown
viewer.stop()
cad_model.finalize()
```

The repository includes a fuller dual-model example in [main.ipy](main.ipy).

### Render data format

Parent/child geometry synchronization uses typed IPC payloads defined in `bot.viewer.contracts`:

- `ScenePayload` with operation `ADD` / `UPDATE` / `DELETE`
- per-curve `CurveDelta`
- float32 packed vertex channels (`bytes`) for compact transport

At runtime:

- parent serializes geometry with `floats_to_bytes` (`bot.viewer.serialize`),
- `multiprocessing.Pipe` transports pickled `(cmd, data)` tuples,
- child applies updates via `np.frombuffer(...)` on binary channels for patch updates.

See [doc/technical_reference_v1.md](doc/technical_reference_v1.md#3-core-mechanisms) for the full schema and flow.

---

## Development guide

We use [uv](https://docs.astral.sh/uv/) for dependency and environment management.

### Prerequisites

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- On headless Linux: `sudo apt-get install libglu1-mesa libosmesa6`

### 1. Clone and set up

```bash
git clone --recurse-submodules https://github.com/franck-ledoux/bot.git
cd bot
uv sync --all-extras --dev
```

`ferrispline/` is a required submodule and is installed as a local path dependency (`ferrispline/python`) during `uv sync`.

> **Never edit `uv.lock` by hand.** Commit it when dependency resolution changes.

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

Developer guides are indexed in [doc/index.md](doc/index.md).

### 5. Continuous integration

Each push and pull request triggers GitHub Actions workflows:

- `tests.yml`: test run + coverage upload
- `lint.yml`: Ruff lint and format checks

---

## Project structure

```
bot/
├── bot/
│   ├── core/
│   │   ├── cad.py             # CADModel (gmsh/OCC)
│   │   ├── spline.py          # SplineModel (ferrispline.PyModel wrapper)
│   │   └── observable.py      # Observer base
│   ├── viewer/
│   │   ├── viewer.py          # Viewer public API, subprocess lifecycle
│   │   ├── contracts.py       # IPC message types (ScenePayload, ViewEventType, ...)
│   │   ├── serialize.py       # Float32 packing/unpacking helpers
│   │   └── adapter.py         # ACL adapters (CADAdapter, SplineAdapter)
|   |   └── tag.py             # Namespaced curve tag utilities for the viewer adapter boundary
│   ├── view/
│   │   ├── scene.py           # Scene patch/apply logic
│   │   └── curve_app.py       # Curve rendering + collision solids
|   |   └── view.py            # View — Panda3D ShowBase (runs in subprocess)
│   └── control/
│       ├── picker.py          # RayPicker raycasting
│       ├── mouse.py           # Mouse interactions and drag sessions
│       └── keyboard.py        # Shortcuts and axis constraints
├── ferrispline/               # Rust/Python NURBS library submodule
├── doc/                       # Developer docs (index + focused guides + technical reference)
├── tests/
│   ├── unit/
│   └── system/
├── data/
├── main.ipy                   # End-to-end interactive example
├── bot_config.toml
├── pyproject.toml
└── uv.lock
```

---

## Contributing

We follow a branch-and-pull-request workflow. Direct pushes to `main` are not allowed.

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

- [ ] `uv run pytest` passes
- [ ] New behavior has test coverage
- [ ] Public API/documentation changes are documented
- [ ] `uv.lock` is committed if dependencies changed
- [ ] PR explains what changed and why

### Code standards

- Formatting: standard Python conventions (PEP 8)
- Docstrings: English, Google style, for public symbols
- Type hints: required for new public signatures

### Troubleshooting

**Panda3D / OpenGL errors on headless Linux:**

```bash
sudo apt-get install libglu1-mesa libosmesa6
```

**Subprocess tests open a window — is that expected?**
Yes. `tests/system/test_viewer_subprocess.py` starts the real Panda3D process and is skipped automatically when no display is available.

# BOT
![Tests](https://github.com/franck-ledoux/bot/actions/workflows/tests.yml/badge.svg)
[![codecov](https://codecov.io/gh/franck-ledoux/bot/graph/badge.svg?token=HGY9PK4OA4)](https://codecov.io/gh/franck-ledoux/bot)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

<!-- ![Documentation](https://github.com/franck-ledoux/bot/actions/workflows/documentation.yml/badge.svg)' -->

The BOT project, for *BlOcking Toolkit*, is a Python project that is designed to provide a sandbox to test new ideas for generating quad and hex meshes interactively. It is a research project under construction. 

# Spirit of the project
This software is a sandbox for developing and testing meshing algorithm, focusing on quad and hex blocking, and potentially AI-driven. To eventually enable an AI agent to create or modify block structure, we need robust and specified operations.

What do we want? A programmatic approach, we do not interactively modify the structure. The role of the viewer will be to provide informations to help us to programmatically modify a structure, for instance:
- picking in the scene to get a location 
- regular grid in any plan to see how and where to move a point 

```python
boa = bot.Agent()
boa.load('file.step')
p1 = boa.create_point(0,0,0)
p1 = boa.project_on_geom(p1)
p1 = boa.move(p1, (2.2,2.5))

# bob is a visualizer that is connected to bot using the Observer Design Pattern
bob = bot.Viewer(boa,display=True)

#If we want to let boa works without 
# any update on bob, we disconnect it
boa.unconnect(bob)

#and we connect it again
boa.connect(bob)
```
## A word about the architecture
We use sockets for the communication between the Agent and the Viewer.  

# Commandes pour travailler

- `uv init` to initialize the working directory 
- Lancer un script : `uv run main.py` (uv gère l'activation de l'environnement pour vous).

- Ajouter une nouvelle bibliothèque : `uv add <nom>`

- Ajouter une nouvelle bibliothèque pour le dev : `uv add --dev <nom>`

- Synchroniser l'environnement (si vous récupérez le projet d'un collègue) : `uv sync`
- Pour tester le projet, se mettre à la racine 
et faire : `uv run pytest`. La configuration des tests fournie dans le fichier `pyproject.toml` fait que les tests lancés sont ceux écrits dans le répertoire `tests/`, avec les options de couverture `--cov=bot --cov-report=html --cov-report=term` qui permettent de fournir le taux de couverture de tout le répertoire `bot` avec une sortie dans le terminal et une autre plus complète dans `htmlcv\index.html`.

- Pour générer la documentation dans le répertoire `docs`: `uv run pdoc ./bot -o ./docs`
[!Attention] Le fichier `uv.lock` : Ne le modifiez pas à la main, mais commitez-le impérativement sur Git. C'est lui qui garantit que l'on a tous exactement les mêmes versions de bibliothèques.


## 🛠 Development Guide

We use [uv](https://docs.astral.sh/uv/) to manage dependencies and virtual environments. Please ensure you have it installed before starting.

Please read our [Contributing Guide](CONTRIBUTING.md) before starting to work on the project.


### 1. Setup
Clone the repository and install the environment:
```bash
git clone [https://github.com/franck-ledoux/bot.git](https://github.com/franck-ledoux/bot.git)
cd bot
uv sync
```
This command automatically creates a `.venv` and installs all production and development dependencies.

### 2. Running the Project
To run the main script or the bot:
```bash
uv run python bot/main.py
```

### 3. Testing & Coverage

We use pytest with pytest-cov. To run the test suite and generate an HTML coverage report:
```bash
uv run pytest
```
The report will be available in the `htmlcov/` folder.

### 4. Documentation

Documentation is generated from docstrings using `pdoc`.

Live Preview (updates as you save):
```bash
uv run pdoc ./bot
```
Build Static HTML:
```bash
uv run pdoc ./bot -o ./docs
```

### 5. Continuous Integration
Each push to the repository triggers:
- A full test suite on Ubuntu (including graphics library dependencies).
- Coverage upload to Codecov.

## 🏗 Project Structure

```plain
.
├── .github/workflows/   # CI/CD pipelines (Tests & Docs)
├── bot/                 # Main package source code
├── tests/               # Pytest suite
├── pyproject.toml       # Project metadata & dependencies
├── uv.lock              # Deterministic lockfile
└── README.md            # This file
```
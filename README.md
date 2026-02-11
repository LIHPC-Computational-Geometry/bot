# BOT, BlOcking Toolkit

![Tests](https://github.com/franck-ledoux/bot/actions/workflows/tests.yml/badge.svg)
![Coverage](https://codecov.io/gh/franck-ledoux/bot/branch/main/graph/badge.svg?token=CODECOV_TOKEN)
![Documentation](https://github.com/franck-ledoux/bot/actions/workflows/documentation.yml/badge.svg)

# Commandes pour travailler

- Lancer un script : `uv run main.py` (uv gère l'activation de l'environnement pour vous).

- Ajouter une nouvelle bibliothèque : `uv add <nom>`

- Ajouter une nouvelle bibliothèque pour le dev : `uv add --dev <nom>`

- Synchroniser l'environnement (si vous récupérez le projet d'un collègue) : `uv sync`
- Pour tester le projet, se mettre à la racine et faire : `uv run pytest`. La configuration des tests fournie dans le fichier `pyproject.toml` fait que les tests lancés sont ceux écrits dans le répertoire `tests/`, avec les options de couverture `--cov=bot --cov-report=html --cov-report=term` qui permettent de fournir le taux de couverture de tout le répertoire `bot` avec une sortie dans le terminal et une autre plus complète dans `htmlcv\index.html`.

- Pour générer la documentation dans le répertoire `docs`: `uv run pdoc ./bot -o ./docs`
[!Attention] Le fichier `uv.lock` : Ne le modifiez pas à la main, mais commitez-le impérativement sur Git. C'est lui qui garantit que l'on a tous exactement les mêmes versions de bibliothèques.

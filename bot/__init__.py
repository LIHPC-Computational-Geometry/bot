"""
bot module: the complete bot application

Submodules:
- core:   geometric kernel (CAD model via gmsh)
- viewer: Panda3D viewer, connectable to a Model
- view:   rendering components (internal)
- control: camera, keyboard, mouse controllers (internal)

Quick start:
    import bot
    k = bot.CADModel()
    k.open("part.geo")
    v = bot.Viewer()
    v.connect_models(k).run()
"""

from . import core, view
from .viewer import Viewer

try:
    from .core.cad import CADModel
except ModuleNotFoundError:
    CADModel = None

__all__ = ["core", "control", "view", "viewer", "CADModel", "Viewer"]

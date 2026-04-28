"""
bot module: the complete bot application

Submodules:
- core:   geometric kernel (CAD model via gmsh)
- viewer: Panda3D viewer, connectable to a Model
- view:   rendering components (internal)
- control: camera, keyboard, mouse controllers (internal)

Quick start:
    import bot
    k = bot.Model()
    k.open("part.geo")
    v = bot.Viewer()
    v.connect(k).run()
"""

from . import core, view
from .viewer import Viewer

try:
    from .core.cad import Model as CADModel
except ModuleNotFoundError:
    CADModel = None
Model = CADModel

__all__ = ["core", "control", "view", "viewer", "Model", "Viewer"]

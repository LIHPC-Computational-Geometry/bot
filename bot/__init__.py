"""
bot module: the complete bot application

Submodules:

- model: this module provides business classes and functions (for geometry and mesh)

- view: View module with GUI and 2D/3D visualization capabilities
"""

from . import model, view

# list of sub-modules the user will see when he writes 'from bot import *'
__all__ = ['model', 'view']

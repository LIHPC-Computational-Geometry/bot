"""
Kernel module: The model module gathers the business object of our application

Submodules:

- geom: Classes and functions for handling and querying geometric entities

- mesh: Classes and functions for handling blossom mesh entities
"""


from . import geom, mesh

# list of sub-modules the user will see when he writes 'from bot.model import *'
__all__ = ['geom', 'mesh']

"""Immutable binding types for the shortcut system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Key:
    """Single key press (Panda3D event name, e.g. ``\"c\"``, ``\"shift-x\"``)."""

    name: str


@dataclass(frozen=True)
class Seq:
    """Ordered key sequence; fires only when the full sequence matches."""

    keys: tuple[str, ...]
    timeout: float = 0.4

    def __init__(self, *keys: str, timeout: float = 0.4):
        object.__setattr__(self, "keys", tuple(keys))
        object.__setattr__(self, "timeout", timeout)


@dataclass(frozen=True)
class Wheel:
    """Mouse wheel tick."""

    direction: Literal["up", "down"]


@dataclass(frozen=True)
class Click:
    """Mouse click without significant movement."""

    button: Literal["left", "right", "middle"]
    modifiers: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Drag:
    """Continuous mouse drag; handler receives ``(ctx, delta)`` each frame."""

    button: Literal["left", "right", "middle"]
    modifiers: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Hold:
    """Keys held down; handler is called every frame with pressed-state dict."""

    keys: tuple[str, ...]

    def __init__(self, *keys: str):
        object.__setattr__(self, "keys", tuple(keys))


Binding = Key | Seq | Wheel | Click | Drag | Hold

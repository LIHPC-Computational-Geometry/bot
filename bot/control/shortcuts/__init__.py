"""Public API for the KISS shortcut system."""

from bot.control.shortcuts.binding import Click, Drag, Hold, Key, Seq, Wheel
from bot.control.shortcuts.engine import (
    Delta,
    InputContext,
    ShortcutRegistry,
    bind,
    registry,
)

__all__ = [
    "Click",
    "Delta",
    "Drag",
    "Hold",
    "InputContext",
    "Key",
    "Seq",
    "ShortcutRegistry",
    "Wheel",
    "bind",
    "registry",
]

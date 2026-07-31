"""
Adapters bridging core models to the viewer IPC layer.
Adapters translate domain models (CAD, splines) into ``ScenePayload`` deltas for the render subprocess
and turn ``ViewEvent`` interactions into ``ViewerCommand`` responses.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from bot.viewer.contracts import (
    ScenePayload,
    ViewerCommand,
    ViewerCommandType,
    ViewEvent,
)

__all__ = [
    "CADAdapter",
    "CompositeAdapter",
    "SplineAdapter",
]


class Adapter(Protocol):
    """Interface for objects that can be rendered and observed by the Viewer."""

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        """Register a callback invoked when the underlying model changes."""

    def unbind_update(self) -> None:
        """Clear the update callback."""

    def get_delta_load(self) -> ScenePayload:
        """Return the full scene payload used for initial load."""

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Translate a user interaction into viewer commands."""


class BaseAdapter:
    """
    Base class providing common event handling, state management,
    and update binding for viewer adapters.
    """

    curve_type_name: str = "curve"

    def __init__(self) -> None:
        self._update_callback: Callable[[ScenePayload], None] | None = None
        self._last_hovered: str | None = None
        self.color: list[float] = [1.0, 1.0, 1.0, 1.0]
        self.hover_color: list[float] = [1.0, 0.5, 0.0, 1.0]

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        """Register a callback invoked when the underlying model changes."""
        self._update_callback = callback

    def unbind_update(self) -> None:
        """Clear the update callback."""
        self._update_callback = None

    def _handle_hover(self, tag: str | None) -> list[ViewerCommand]:
        """Update HUD text and curve highlight on hover enter or leave."""
        commands: list[ViewerCommand] = []
        if tag:
            tag_str = str(tag)
            if self._last_hovered and self._last_hovered != tag_str:
                commands.append(
                    {
                        "cmd": ViewerCommandType.HIGHLIGHT_CURVE,
                        "tag": self._last_hovered,
                        "color": self.color,
                    }
                )
            info_text = f"--- Curve {tag_str} ---\n" + self._get_hover_info(tag_str)
            commands.extend(
                [
                    {"cmd": ViewerCommandType.UPDATE_HUD, "text": info_text},
                    {
                        "cmd": ViewerCommandType.HIGHLIGHT_CURVE,
                        "tag": tag_str,
                        "color": self.hover_color,
                    },
                ]
            )
            self._last_hovered = tag_str
        else:
            if self._last_hovered:
                commands.append(
                    {
                        "cmd": ViewerCommandType.HIGHLIGHT_CURVE,
                        "tag": self._last_hovered,
                        "color": self.color,
                    }
                )
                commands.append(
                    {
                        "cmd": ViewerCommandType.UPDATE_HUD,
                        "text": "Ready. Hover or click on curves.",
                    }
                )
                self._last_hovered = None
        return commands

    def _get_hover_info(self, tag_str: str) -> str:
        """
        Return model-specific curve information for HUD display.
        Should be overridden by subclasses.
        """
        return "Type: unknown"

    def _handle_curve_selected(self, tag: str) -> list[ViewerCommand]:
        """Enter edit mode for the selected curve."""
        return [
            {
                "cmd": ViewerCommandType.SET_EDIT_MODE,
                "enabled": True,
                "curve_tag": tag,
            },
            {"cmd": ViewerCommandType.SET_ACTIVE_CURVE, "curve_tag": tag},
            {
                "cmd": ViewerCommandType.UPDATE_HUD,
                "text": f"Editing {self.curve_type_name} {tag}: drag a control point.",
            },
        ]

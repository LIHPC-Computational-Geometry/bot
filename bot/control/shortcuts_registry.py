"""
Declarative shortcut registry — single place to add new commands.

Usage::

    @bind(Key("c"), scope="local")
    def center_camera(ctx):
        ctx.messenger.send("cmd_center")

    @bind(Key("n"), scope="domain")
    def new_point(ctx):
        return {"action": "new_point"}  # emits ViewEventType.SHORTCUT
"""

from __future__ import annotations

import sys

from bot.control.shortcuts import Drag, Hold, Key, Wheel, bind, registry
from bot.viewer.contracts import ViewEventType  # noqa: F401 — re-export for domain handlers

# Importing this module registers all handlers on the default ``registry``.
__all__ = ["registry"]


@bind(Key("escape"), scope="local")
def quit_app(ctx):
    sys.exit(0)


@bind(Key("f5"), scope="local")
def hot_reload(ctx):
    ctx.messenger.send("cmd_hot_reload")


@bind(Key("c"), scope="local")
def center_camera(ctx):
    ctx.messenger.send("cmd_center")


@bind(Key("alt-x"), scope="local")
def align_plane_x(ctx):
    ctx.messenger.send("cmd_align_plane", ["x"])


@bind(Key("alt-y"), scope="local")
def align_plane_y(ctx):
    ctx.messenger.send("cmd_align_plane", ["y"])


@bind(Key("alt-z"), scope="local")
def align_plane_z(ctx):
    ctx.messenger.send("cmd_align_plane", ["z"])


@bind(Key("x"), scope="local")
def axis_constraint_x(ctx):
    ctx.messenger.send("cmd_axis_constraint", [1])


@bind(Key("y"), scope="local")
def axis_constraint_y(ctx):
    ctx.messenger.send("cmd_axis_constraint", [2])


@bind(Key("z"), scope="local")
def axis_constraint_z(ctx):
    ctx.messenger.send("cmd_axis_constraint", [4])


@bind(Key("shift-x"), scope="local")
def axis_constraint_yz(ctx):
    ctx.messenger.send("cmd_axis_constraint", [6])


@bind(Key("shift-y"), scope="local")
def axis_constraint_xz(ctx):
    ctx.messenger.send("cmd_axis_constraint", [5])


@bind(Key("shift-z"), scope="local")
def axis_constraint_xy(ctx):
    ctx.messenger.send("cmd_axis_constraint", [3])


def _register_axis_mask_keys() -> None:
    """Axis-constraint masks 0..7 via digit keys."""

    def _make(mask: int):
        def handler(ctx, m=mask):
            ctx.messenger.send("cmd_axis_constraint", [m])

        handler.__name__ = f"axis_constraint_mask_{mask}"
        return handler

    for mask in range(8):
        registry.bind(Key(str(mask)), scope="local")(_make(mask))


_register_axis_mask_keys()


@bind(Key("p"), scope="local")
def toggle_marker(ctx):
    ctx.messenger.send("cmd_toggle_marker")


@bind(Hold("arrow_left", "arrow_right", "arrow_up", "arrow_down"), scope="local")
def arrow_pan(ctx, keys: dict):
    dx = keys.get("arrow_right", 0) - keys.get("arrow_left", 0)
    dy = keys.get("arrow_up", 0) - keys.get("arrow_down", 0)
    if dx == 0 and dy == 0:
        return
    dt = ctx.base.clock.getDt()
    speed = 0.5
    ctx.messenger.send("cmd_pan", [dx * speed * dt, dy * speed * dt])


@bind(Wheel("up"), scope="local")
def zoom_in(ctx):
    ctx.messenger.send("cmd_zoom", [0.9])


@bind(Wheel("down"), scope="local")
def zoom_out(ctx):
    ctx.messenger.send("cmd_zoom", [1.1])


@bind(Drag("left"), scope="local")
def pan_drag(ctx, delta):
    if ctx.mouse_handler is not None and getattr(
        ctx.mouse_handler, "dragging_cp", False
    ):
        return
    ctx.messenger.send("cmd_pan", [delta.x, delta.y])

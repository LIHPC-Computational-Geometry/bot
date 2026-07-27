from __future__ import annotations
import multiprocessing as mp
import threading
from typing import Callable, Optional, Any
from bot.viewer.adapter import Adapter, CADAdapter, CompositeAdapter
from bot.core.cad import CADModel
from bot.core.spline import SplineModel
from bot.viewer.contracts import (
    ParentCommand,
    ScenePayload,
    SceneUpdateOp,
    ViewerCommand,
    ViewerCommandType,
    ViewEvent,
    ViewEventType,
)

"""
Viewer: launches Panda3D in a separate subprocess.

On macOS (and in general), OpenGL must run on the main thread of the
process that owns the window. By launching Panda3D in a subprocess,
its main thread is free for Panda3D, and the IPython main thread
remains fully interactive. Data flows through a multiprocessing Pipe
in the form of serializable dicts.
"""

# ---------------------------------------------------------------------------
# Subprocess entry function (must be at module level for pickle)
# ---------------------------------------------------------------------------


def _viewer_subprocess(conn, config_filename: str):
    """
    Panda3D subprocess entry point.
    Runs on the subprocess main thread → macOS safe.
    """
    import queue as _queue

    cmd_queue = _queue.Queue()

    # Thread that reads the parent pipe → puts into the internal queue
    def _pipe_reader():
        while True:
            try:
                msg = conn.recv()
                cmd_queue.put(msg)
                if msg[0] == ViewerCommandType.EXIT:
                    break
            except EOFError:
                break

    threading.Thread(target=_pipe_reader, daemon=True).start()

    def on_event(event_type, data):
        try:
            conn.send((event_type, data))
        except BrokenPipeError:
            pass

    from bot.view.view import View

    view = View(config_filename, cmd_queue, on_event)
    view.run()  # blocking — intentional, it's the main thread of the subprocess


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

VisualCallback = Callable[[Any], None] | None


class Viewer:
    """
    3D Viewer connected to an Adapter data source.

    IPython usage:
        k = bot.CADModel()
        k.open("part.geo")

        v = bot.Viewer()
        v.connect_models(k).run()

        k.add_point([1, 2, 3])
        v.on_pick = lambda coords: k.add_point(coords)
    """

    def __init__(self, config_filename: str = "bot_config.toml"):
        self._config_filename = config_filename
        self._adapter: Optional["Adapter"] = None
        self._conn = None  # parent end of the Pipe
        self._process = None  # Panda3D subprocess
        self._event_thread = None  # event listening thread
        self._running = False
        self._last_hovered: str | None = None

        self._callbacks: dict[ViewEventType, VisualCallback] = {}

    # =========================================================================
    # COMMANDES (Public API)
    # =========================================================================

    def connect_models(
        self,
        cad_model: "CADModel",
        spline_model: Optional["SplineModel"] = None,
    ) -> "Viewer":
        """Convenience wrapper that builds a CompositeAdapter from core models."""

        if spline_model is None:
            return self._connect(CompositeAdapter({"cad": CADAdapter(cad_model)}))
        return self._connect(CompositeAdapter.from_models(cad_model, spline_model))

    def disconnect(self) -> "Viewer":
        """Detach the viewer from the current adapter."""
        if self._adapter is not None:
            self._adapter.unbind_update()
            self._adapter = None

        if hasattr(self, "_default_event_handler"):
            delattr(self, "_default_event_handler")

        return self

    def run(self) -> "Viewer":
        """
        Launches the viewer in a separate subprocess (non-blocking).
        Returns self for chaining.
        """
        self._running = True

        ctx = mp.get_context("spawn")
        parent_conn, child_conn = ctx.Pipe()
        self._conn = parent_conn

        self._process = ctx.Process(
            target=_viewer_subprocess,
            args=(child_conn, self._config_filename),
            daemon=True,
        )
        self._process.start()
        child_conn.close()  # useless in the parent process

        if self._adapter is not None:
            self._send(SceneUpdateOp.ADD, self._adapter.get_delta_load())

        self._start_event_listener()
        return self

    def stop(self):
        """Stops the viewer cleanly and frees resources."""
        self._running = False
        # 1. Notify the model that we are no longer watching
        self.disconnect()

        # 2. Send the stop signal to the subprocess
        if self._conn is not None:
            try:
                self._send(ViewerCommandType.EXIT, None)
            except Exception:
                pass

        if self._process is not None:
            self._process.join(timeout=2.0)  # We allow 2 seconds to close
            if self._process.is_alive():
                self._process.terminate()  # Brute force if still alive
            self._process = None

        # 4. Close communication
        if self._conn is not None:
            self._conn.close()
            self._conn = None

        self._event_thread = None

    def add_callback(
        self, event_type: ViewEventType, callback: VisualCallback
    ) -> "Viewer":
        """Associate a personalized function for a specific event."""
        self._callbacks[event_type] = callback
        return self

    def remove_callback(self, event_type: ViewEventType) -> "Viewer":
        """Delete the personalized callback for an event."""
        self._callbacks.pop(event_type, None)
        return self

    def highlight_curve(self, tag: str, color: list) -> "Viewer":
        """Colors the geometry associated with a tag."""
        self._send(ViewerCommandType.HIGHLIGHT_CURVE, {"tag": tag, "color": color})
        return self

    def set_hud_text(self, text: str) -> "Viewer":
        """Updates the text displayed in an overlay on the screen."""
        self._send(ViewerCommandType.UPDATE_HUD, {"text": text})
        return self

    def set_edit_mode(
        self, enabled: bool, curve_tag: Optional[str | int] = None
    ) -> "Viewer":
        self._send(
            ViewerCommandType.SET_EDIT_MODE,
            {"enabled": enabled, "curve_tag": curve_tag},
        )
        return self

    def set_active_curve(self, curve_tag: Optional[str | int]) -> "Viewer":
        self._send(ViewerCommandType.SET_ACTIVE_CURVE, {"curve_tag": curve_tag})
        return self

    def set_axis_constraint(self, mask: int) -> "Viewer":
        try:
            normalized = int(mask)
        except TypeError, ValueError:
            normalized = 7
        normalized = max(0, min(7, normalized))
        self._send(ViewerCommandType.SET_AXIS_CONSTRAINT, {"mask": normalized})
        return self

    def delete_curve(self, tag: str) -> "Viewer":
        """
        Supprime explicitement une courbe de la scène.
        Génère un payload 'delete' complet pour le processus enfant.
        """
        payload: ScenePayload = {
            "op": SceneUpdateOp.DELETE,
            "changed_curves": {},
            "deleted_curves": [tag],
        }
        self._send(SceneUpdateOp.DELETE, payload)
        return self

    def move_control_point(
        self, curve_tag: str, cp_index: int, new_pos: list[float]
    ) -> "Viewer":
        """Move a control point via the adapter event path from IPython."""
        if self._adapter is None:
            self.set_hud_text("No adapter connected.")
            return

        event: ViewEvent = {
            "event_type": ViewEventType.CP_PICK_END,
            "curve_tag": curve_tag,
            "cp_index": cp_index,
            "world_pos": new_pos,
        }
        self._dispatch_commands(self._adapter.handle_event(event))
        self.set_hud_text(f"Control point {cp_index} of curve {curve_tag} moved.")
        return self

    # =========================================================================
    # INTERNAL FUNCTIONS
    # =========================================================================

    def _connect(self, adapter: "Adapter") -> "Viewer":
        """
        Connects this viewer to an Adapter source.
        Can be called before or after run().
        Returns self for chaining.
        """
        if self._adapter is not None:
            self.disconnect()

        self._adapter = adapter
        adapter.bind_update(self._on_delta)

        self._default_event_handler = self._create_default_handler(adapter)

        if self._conn is not None:
            self._send(SceneUpdateOp.ADD, adapter.get_delta_load())
        return self

    def _create_default_handler(
        self, adapter: "Adapter"
    ) -> Callable[[ViewEventType, Any], None]:
        """Create a closure for translate event into visual commands."""

        def handler(event_type: ViewEventType, data: Any):
            # 1. Format event
            view_event = self._build_view_event(event_type, data)
            # 2. The adapter choose commands to apply
            commands = adapter.handle_event(view_event)
            # 3. The Viewer send these commands to the child process
            self._dispatch_commands(commands)

        return handler

    def _on_delta(self, payload: "ScenePayload") -> None:
        """Forward adapter deltas to the child process."""
        op = payload.get("op", SceneUpdateOp.UPDATE)
        self._send(op, payload)

    def _send(self, cmd: ParentCommand, data):
        """Send a ``(cmd, data)`` message to the child process over the pipe."""
        if self._conn is not None:
            try:
                self._conn.send((cmd, data))
            except BrokenPipeError:
                pass

    def _dispatch_commands(self, commands: list["ViewerCommand"]) -> None:
        for command in commands:
            cmd = command.get("cmd")
            match cmd:
                case ViewerCommandType.HIGHLIGHT_CURVE:
                    self.highlight_curve(
                        command["tag"], command.get("color", [1, 0, 1, 1])
                    )
                case ViewerCommandType.UPDATE_HUD:
                    self.set_hud_text(command.get("text", ""))
                case ViewerCommandType.SET_EDIT_MODE:
                    self.set_edit_mode(
                        bool(command.get("enabled", False)), command.get("curve_tag")
                    )
                case ViewerCommandType.SET_ACTIVE_CURVE:
                    self.set_active_curve(command.get("curve_tag"))
                case ViewerCommandType.SET_AXIS_CONSTRAINT:
                    self.set_axis_constraint(command.get("mask", 7))
                case _:
                    pass

    def _start_event_listener(self):
        """Daemon thread that receives events from the subprocess."""

        def _listen():
            while self._running:
                try:
                    if not self._conn.poll(0.1):
                        continue

                    event_type, data = self._conn.recv()

                    if event_type == ViewEventType.HOVER:
                        self._last_hovered = str(data) if data is not None else None

                    # NOTE: personalized callback
                    if (
                        event_type in self._callbacks
                        and self._callbacks[event_type] is not None
                    ):
                        self._callbacks[event_type](data)

                    # NOTE: execute default behavior event though a personalized callback is used
                    if hasattr(self, "_default_event_handler"):
                        self._default_event_handler(event_type, data)

                except EOFError, BrokenPipeError, AttributeError:
                    break
                except Exception:
                    pass

        self._event_thread = threading.Thread(target=_listen, daemon=True)
        self._event_thread.start()

    @staticmethod
    def _build_view_event(event_type: ViewEventType, data) -> "ViewEvent":
        """Build a strict typing event from pipe"""
        if isinstance(data, dict):
            return {"event_type": event_type, **data}

        if event_type == ViewEventType.HOVER:
            return {"event_type": ViewEventType.HOVER, "tag": data}
        if event_type == ViewEventType.CURVE_SELECTED:
            return {"event_type": ViewEventType.CURVE_SELECTED, "curve_tag": data}

        return {"event_type": event_type, "data": data}

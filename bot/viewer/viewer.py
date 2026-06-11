from __future__ import annotations
import multiprocessing as mp
import threading
from typing import Callable, Optional
from bot.viewer.viewable import IViewable, CADAdapter, CompositeViewable
from bot.core.cad import CADModel
from bot.core.spline import SplineModel
from bot.viewer.contracts import ScenePayload, ViewerCommand, ViewEvent

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
                if msg[0] == "exit":  # Exit command
                    break
            except EOFError:
                break

    threading.Thread(target=_pipe_reader, daemon=True).start()

    def on_event(event_type, data):
        try:
            conn.send((event_type, data))
        except BrokenPipeError:
            pass

    from bot.viewer.app import ViewerApp

    app = ViewerApp(config_filename, cmd_queue, on_event)
    app.run()  # blocking — intentional, it's the main thread of the subprocess


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class Viewer:
    """
    3D Viewer connected to an IViewable data source.

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
        self._viewable: Optional["IViewable"] = None
        self._conn = None  # parent end of the Pipe
        self._process = None  # Panda3D subprocess
        self._event_thread = None  # event listening thread
        self._running = False
        self._last_hovered: str | None = None

        self.on_pick: Optional[Callable] = None
        self.on_hover: Optional[Callable] = None
        self.on_curve_selected: Optional[Callable] = None
        self.on_cp_pick_start: Optional[Callable] = None
        self.on_cp_drag: Optional[Callable] = None
        self.on_cp_pick_end: Optional[Callable] = None

    def highlight_curve(self, tag: str, color: list) -> "Viewer":
        """Colors the geometry associated with a tag."""
        self._send("highlight_curve", {"tag": tag, "color": color})
        return self

    def set_hud_text(self, text: str) -> "Viewer":
        """Updates the text displayed in an overlay on the screen."""
        self._send("update_hud", {"text": text})
        return self

    def set_edit_mode(
        self, enabled: bool, curve_tag: Optional[str | int] = None
    ) -> "Viewer":
        self._send("set_edit_mode", {"enabled": enabled, "curve_tag": curve_tag})
        return self

    def set_active_curve(self, curve_tag: Optional[str | int]) -> "Viewer":
        self._send("set_active_curve", {"curve_tag": curve_tag})
        return self

    def set_axis_constraint(self, mask: int) -> "Viewer":
        try:
            normalized = int(mask)
        except TypeError, ValueError:
            normalized = 7
        normalized = max(0, min(7, normalized))
        self._send("set_axis_constraint", {"mask": normalized})
        return self

    def _connect(self, viewable: "IViewable") -> "Viewer":
        """
        Connects this viewer to an IViewable source.
        Can be called before or after run().
        Returns self for chaining.
        """
        if self._viewable is not None:
            self.disconnect()
        self._viewable = viewable
        viewable.bind_update(self._on_delta)
        if self._conn is not None:
            self._send("add", viewable.get_delta_load())
        return self

    def connect_models(
        self,
        cad_model: "CADModel",
        spline_model: Optional["SplineModel"] = None,
    ) -> "Viewer":
        """Convenience wrapper that builds a CompositeViewable from core models."""

        if spline_model is None:
            return self._connect(CompositeViewable({"cad": CADAdapter(cad_model)}))
        return self._connect(CompositeViewable.from_models(cad_model, spline_model))

    def disconnect(self) -> "Viewer":
        """Detach the viewer from the current viewable."""
        if self._viewable is not None:
            self._viewable.unbind_update()
            self._viewable = None
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

        if self._viewable is not None:
            self._send("add", self._viewable.get_delta_load())

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
                self._send("exit", None)
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
        print("Stopped Viewer")

    def _on_delta(self, payload: "ScenePayload") -> None:
        """Forward adapter deltas to the child process."""
        op = payload.get("op", "update")
        self._send(op, payload)

    def _send(self, cmd: str, data):
        """Send a ``(cmd, data)`` message to the child process over the pipe."""
        if self._conn is not None:
            try:
                self._conn.send((cmd, data))
            except BrokenPipeError:
                pass

    def _dispatch_commands(self, commands: list["ViewerCommand"]) -> None:
        for command in commands:
            cmd = command.get("cmd")
            if cmd == "highlight_curve":
                self.highlight_curve(command["tag"], command.get("color", [1, 1, 1, 1]))
            elif cmd == "update_hud":
                self.set_hud_text(command.get("text", ""))
            elif cmd == "set_edit_mode":
                self.set_edit_mode(
                    bool(command.get("enabled", False)),
                    command.get("curve_tag"),
                )
            elif cmd == "set_active_curve":
                self.set_active_curve(command.get("curve_tag"))

    def _start_event_listener(self):
        """Daemon thread that receives events from the subprocess."""

        def _listen():
            while self._running:
                try:
                    if self._conn.poll(0.1):
                        event_type, data = self._conn.recv()
                        if event_type == "pick" and self.on_pick is not None:
                            self.on_pick(data)
                            continue

                        view_event: ViewEvent = self._build_view_event(event_type, data)

                        if event_type == "hover":
                            tag = data
                            self._last_hovered = str(tag) if tag is not None else None
                            if self.on_hover is not None:
                                self.on_hover(data)
                            elif self._viewable is not None:
                                self._dispatch_commands(
                                    self._viewable.handle_event(view_event)
                                )
                            continue

                        if (
                            event_type == "curve_selected"
                            and self.on_curve_selected is not None
                        ):
                            self.on_curve_selected(data)
                            continue

                        if (
                            event_type == "cp_pick_start"
                            and self.on_cp_pick_start is not None
                        ):
                            self.on_cp_pick_start(data)
                            continue

                        if event_type == "cp_drag" and self.on_cp_drag is not None:
                            self.on_cp_drag(data)
                            continue

                        if (
                            event_type == "cp_pick_end"
                            and self.on_cp_pick_end is not None
                        ):
                            self.on_cp_pick_end(data)
                            continue

                        if self._viewable is not None:
                            self._dispatch_commands(
                                self._viewable.handle_event(view_event)
                            )
                except EOFError, BrokenPipeError, AttributeError:
                    break
                except Exception:
                    pass

        self._event_thread = threading.Thread(target=_listen, daemon=True)
        self._event_thread.start()

    @staticmethod
    def _build_view_event(event_type: str, data) -> "ViewEvent":
        if isinstance(data, dict):
            return {"event_type": event_type, **data}
        return {"event_type": event_type, "tag": data, "curve_tag": data}

    def bezier_conversion(self, degree: int):
        """Convert the last hovered CAD curve into a Bezier spline."""
        if self._last_hovered is None:
            self.set_hud_text("Impossible to convert: no curve selected")
            return
        if not isinstance(self._viewable, CompositeViewable):
            self.set_hud_text("Bezier conversion requires a CompositeViewable.")
            return
        self.set_hud_text("Bezier conversion is not yet implemented for IViewable.")

    def move_control_point(self, tag: str, cp_index: int, new_pos: list[float]):
        """Move a control point via the viewable event path."""
        if self._viewable is None:
            self.set_hud_text("No viewable connected.")
            return
        event: ViewEvent = {
            "event_type": "cp_pick_end",
            "tag": tag,
            "curve_tag": tag,
            "cp_index": cp_index,
            "world_pos": new_pos,
        }
        self._dispatch_commands(self._viewable.handle_event(event))
        self.set_hud_text(f"Control point {cp_index} of curve {tag} moved.")

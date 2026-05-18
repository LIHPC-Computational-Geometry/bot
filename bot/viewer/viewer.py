"""
Viewer: launches Panda3D in a separate subprocess.

On macOS (and in general), OpenGL must run on the main thread of the
process that owns the window. By launching Panda3D in a subprocess,
its main thread is free for Panda3D, and the IPython main thread
remains fully interactive. Data flows through a multiprocessing Pipe
in the form of serializable dicts.
"""

import multiprocessing as mp
import threading
from typing import Any, Callable, Optional, TYPE_CHECKING

from bot.core.curve import BezierCurve

if TYPE_CHECKING:
    from bot.core.cad import Model
else:
    Model = Any


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
    3D Viewer connected to a Model core.

    IPython usage:
        k = bot.CADModel()
        k.open("part.geo")

        v = bot.Viewer()
        v.connect(k).run()   # non-blocking: Panda3D runs in a subprocess

        k.add_point([1, 2, 3])                      # → viewer updated
        v.on_pick = lambda coords: k.add_point(coords)  # viewer → core

    Multiple viewers can be connected to the same model (one subprocess
    per viewer).
    """

    def __init__(self, config_filename: str = "bot_config.toml"):
        self._config_filename = config_filename
        self.model: Optional[Model] = None
        self._conn = None  # parent end of the Pipe
        self._process = None  # Panda3D subprocess
        self._event_thread = None  # event listening thread
        self._running = False

        self._default_last_hovered = None

        self.on_pick: Optional[Callable] = None
        self.on_hover: Optional[Callable] = self._default_on_hover
        self.on_curve_selected: Optional[Callable] = self._default_on_curve_selected
        self.on_cp_pick_start: Optional[Callable] = None
        self.on_cp_drag: Optional[Callable] = None
        self.on_cp_pick_end: Optional[Callable] = self._default_on_cp_pick_end

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def highlight_curve(self, tag: str, color: list) -> "Viewer":
        """Colors the geometry associated with a tag."""
        self._send("highlight_curve", {"tag": tag, "color": color})
        return self

    def set_hud_text(self, text: str) -> "Viewer":
        """Updates the text displayed in an overlay on the screen."""
        self._send("update_hud", {"text": text})
        return self

    def set_edit_mode(self, enabled: bool, curve_tag: Optional[int] = None) -> "Viewer":
        self._send("set_edit_mode", {"enabled": enabled, "curve_tag": curve_tag})
        return self

    def set_active_curve(self, curve_tag: Optional[int]) -> "Viewer":
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

    def connect(self, model: Model) -> "Viewer":
        """
        Connects this viewer to a Model core.
        Can be called before or after run().
        Returns self for chaining.
        """
        if self.model is not None:
            self.model.remove_observer(self)
        self.model = model
        model.add_observer(self)
        if self._conn is not None:
            self._send("load", model.get_render_data())
        return self

    def disconnect(self) -> "Viewer":
        """Detaches the viewer from the current model."""
        if self.model is not None:
            self.model.remove_observer(self)
            self.model = None
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

        if self.model is not None:
            self._send("load", self.model.get_render_data())

        self._start_event_listener()
        return self

    def stop(self):
        """
        Stops the viewer cleanly and frees resources.
        """
        self._running = False

        # 1. Notify the model that we are no longer watching
        self.disconnect()

        # 2. Send the stop signal to the subprocess
        if self._conn is not None:
            try:
                self._send("exit", None)
            except:  # noqa: E722
                pass

        # 3. Wait for the process to finish
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

    # ------------------------------------------------------------------
    # Observer callback (called by Model when state changes)
    # ------------------------------------------------------------------

    def update(self, model: Model):
        """Called by the Model through the observer pattern when geometry changes."""
        self._send("update", model.get_render_data())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send(self, cmd: str, data):
        """Send a ``(cmd, data)`` message to the child process over the pipe."""
        if self._conn is not None:
            try:
                self._conn.send((cmd, data))
            except BrokenPipeError:
                pass

    def _start_event_listener(self):
        """Lightweight thread that receives events from the subprocess (e.g., picking)."""

        def _listen():
            while self._running:
                try:
                    if self._conn.poll(0.1):
                        event_type, data = self._conn.recv()
                        if event_type == "pick" and self.on_pick is not None:
                            self.on_pick(data)
                        elif event_type == "hover" and self.on_hover is not None:
                            self.on_hover(data)
                        elif (
                            event_type == "curve_selected"
                            and self.on_curve_selected is not None
                        ):
                            self.on_curve_selected(data)
                        elif (
                            event_type == "cp_pick_start"
                            and self.on_cp_pick_start is not None
                        ):
                            self.on_cp_pick_start(data)
                        elif event_type == "cp_drag" and self.on_cp_drag is not None:
                            self.on_cp_drag(data)
                        elif (
                            event_type == "cp_pick_end"
                            and self.on_cp_pick_end is not None
                        ):
                            self.on_cp_pick_end(data)
                except EOFError, BrokenPipeError, AttributeError:
                    break
                except Exception:
                    pass

        self._event_thread = threading.Thread(target=_listen, daemon=True)
        self._event_thread.start()

    # ------------------------------------------------------------------
    # Default Interactive Behaviors
    # ------------------------------------------------------------------

    def _default_on_hover(self, tag):
        """Default behavior: highlights and displays spatial details."""
        if tag:
            # 1. Cleanup of the previous curve
            if self._default_last_hovered and self._default_last_hovered != tag:
                self.highlight_curve(self._default_last_hovered, [1, 1, 1, 1])

            # 2. Building the information text
            info_text = f"--- Courbe {tag} ---\n"

            if self.model is not None:
                try:
                    coords_a, coords_b = self.model.get_end_points_coords(int(tag))

                    pt_a = f"({coords_a[0]:.2f}, {coords_a[1]:.2f}, {coords_a[2]:.2f})"
                    pt_b = f"({coords_b[0]:.2f}, {coords_b[1]:.2f}, {coords_b[2]:.2f})"

                    info_text += "Type: Segment linéaire\n"
                    info_text += f"Extrémité A: {pt_a}\n"
                    info_text += f"Extrémité B: {pt_b}"

                except Exception as e:
                    info_text += f"Erreur: {str(e)}"

            # 3. Visual application
            self.set_hud_text(info_text)
            self.highlight_curve(tag, [1, 0.5, 0, 1])
            self._default_last_hovered = tag

        else:
            # Handle empty selection
            if self._default_last_hovered:
                self.highlight_curve(self._default_last_hovered, [1, 1, 1, 1])
                self.set_hud_text("Prêt. Survolez ou cliquez sur les courbes.")
                self._default_last_hovered = None

    def _default_on_curve_selected(self, tag):
        if tag is None:
            return
        try:
            normalized = int(tag)
        except TypeError, ValueError:
            return
        self.set_edit_mode(True, normalized)
        self.set_active_curve(normalized)
        self.set_hud_text(f"Editing curve {normalized}: drag a control point.")

    def _default_on_cp_pick_end(self, data):
        if self.model is None or data is None:
            return
        try:
            tag = int(data["tag"])
            cp_index = int(data["cp_index"])
            world_pos = data.get("world_pos")
            if world_pos is None:
                return
            self.model.update_control_point(tag, cp_index, world_pos)
        except Exception as e:
            self.set_hud_text(f"Control point update failed: {e}")

    def bezier_conversion(self, degree: int):
        if self._default_last_hovered is not None:
            tag = int(self._default_last_hovered)
            if self.model is not None:
                coords_a, coords_b = self.model.get_end_points_coords(int(tag))
                control_points = BezierCurve._default_control_points(
                    coords_a, coords_b, degree
                )
                curve = BezierCurve(tag, control_points, degree)
                self.model.set_curve(tag, curve)
            else:
                self.set_hud_text("Impossible to convert: no model loaded")
        else:
            self.set_hud_text("Impossible to convert: no curve selected")

    def move_control_point(self, tag: int, cp_index: int, new_pos: list[float]):
        if self.model is not None:
            self.model.update_control_point(tag, cp_index, new_pos)
            self.set_hud_text(
                f"Point de contrôle {cp_index} de la courbe {tag} déplacé."
            )
        else:
            self.set_hud_text("Aucun modèle chargé.")

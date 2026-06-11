import queue
import tomllib
import os

from direct.showbase.ShowBase import ShowBase
from panda3d.core import WindowProperties
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from bot.view.scene import Scene
from bot.viewer.serialize import payload_to_geom_data
from bot.control.camera import CameraController
from bot.control.mouse import MouseHandler
from bot.control.keyboard import KeyboardHandler
from bot.viewer.contracts import ScenePayload

_DEFAULT_SCENE = {
    "background_color": [0.1, 0.1, 0.12],
    "line_thickness": 2,
}
_DEFAULT_CAMERA = {
    "pan_speed": 10.0,
    "rotate_speed": 100.0,
    "animation_duration": 0.5,
    "show_marker_at_start": False,
}


class ViewerApp(ShowBase):
    """
    Internal  application.
    Receives display data via a thread-safe queue and renders it.
    Sends user interaction events back via on_event_cb.
    """

    def __init__(self, config_filename: str, cmd_queue: queue.Queue, on_event_cb):
        """
        Args:
            config_filename: Path (relative to the project root) of the TOML
                             config file.
            cmd_queue:       Thread-safe queue fed by the pipe-reader thread.
                             Commands are ``('add'|'update'|'delete'|..., data)``.
            on_event_cb:     Callable ``(event_type, data)`` used to send events
                             (e.g. picking) back to the parent process.
        """
        super().__init__()

        wp = WindowProperties()
        wp.setTitle("bot")
        self.win.requestProperties(wp)

        self._cmd_queue = cmd_queue
        self._on_event_cb = on_event_cb
        self._scene = None
        self._camera_controller = None

        self._config = self.__load_config(config_filename)

        self.kb_handler = KeyboardHandler(self)
        self.mouse_handler = MouseHandler(self)
        self.axis_constraint_mask = 7
        self.accept("cmd_axis_constraint", self.__on_axis_constraint_cmd)

        self.hud = OnscreenText(
            text="", pos=(-1.3, -0.5), scale=0.06, fg=(1, 1, 1, 1), align=TextNode.ALeft
        )

        self.taskMgr.add(self.__process_commands, "ViewerProcessCommands")

    def __load_config(self, config_filename: str) -> dict:
        """Load and parse the TOML config file. Returns an empty dict if not found."""
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        path = os.path.join(base_dir, config_filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return tomllib.load(f)
        return {}

    def __scene_cfg(self) -> dict:
        """Return the ``[view.scene]`` section of the config, or built-in defaults."""
        return self._config.get("view", {}).get("scene", _DEFAULT_SCENE)

    def __camera_cfg(self) -> dict:
        """Return the ``[view.camera]`` section merged with built-in defaults."""
        cfg = _DEFAULT_CAMERA.copy()
        cfg.update(self._config.get("view", {}).get("camera", {}))
        return cfg

    def __process_commands(self, task):
        """
        Per-frame task: drain the command queue and dispatch each command.

        Supported commands: ``add``, ``update``, ``delete``, ``reload_config``.

        Returns:
            task.cont to keep the task alive.
        """
        while not self._cmd_queue.empty():
            try:
                cmd, data = self._cmd_queue.get_nowait()
                if cmd == "add":
                    self.__load_scene(data)
                elif cmd == "update":
                    self.__update_scene(data)
                elif cmd == "delete":
                    self.__delete_in_scene(data)
                elif cmd == "reload_config":
                    self._config = data
                    if self._scene:
                        self._scene.apply_settings(self.__scene_cfg())
                    if self._camera_controller:
                        self._camera_controller.apply_settings(self.__camera_cfg())
                elif cmd == "highlight_curve":
                    if self._scene:
                        self._scene.set_curve_color(data["tag"], data["color"])
                elif cmd == "update_hud":
                    self.hud.setText(data["text"])
                elif cmd == "set_edit_mode":
                    enabled = bool(data.get("enabled", False))
                    curve_tag = data.get("curve_tag")
                    self.mouse_handler.set_edit_mode(enabled, curve_tag)
                    if self._scene:
                        self._scene.set_edit_mode(enabled)
                        if curve_tag is not None:
                            self._scene.set_active_curve(curve_tag)
                elif cmd == "set_active_curve":
                    curve_tag = data.get("curve_tag")
                    self.mouse_handler.set_edit_mode(
                        self.mouse_handler.edit_mode_enabled, curve_tag
                    )
                    if self._scene:
                        self._scene.set_active_curve(curve_tag)
                elif cmd == "set_axis_constraint":
                    self.__set_axis_constraint(data.get("mask", 7))
            except queue.Empty:
                break
        return task.cont

    def __set_axis_constraint(self, mask: int):
        try:
            raw_mask = int(mask)
        except TypeError, ValueError:
            raw_mask = 3
            self.hud.setText("Axis constraint invalid, fallback to xy (3).")
        self.axis_constraint_mask = max(0, min(7, raw_mask))
        if self.axis_constraint_mask != raw_mask:
            self.hud.setText(f"Axis constraint clamped to {self.axis_constraint_mask}.")
        self.mouse_handler.set_axis_constraint(self.axis_constraint_mask)
        if self._scene:
            self._scene.set_axis_constraint(self.axis_constraint_mask)
        self.hud.setText(f"Axis constraint mask: {self.axis_constraint_mask}")

    def __on_axis_constraint_cmd(self, mask: int):
        self.__set_axis_constraint(mask)

    def __load_scene(self, payload: dict):
        """Load (or reload) the scene from an add payload or legacy geom_data."""
        if self._scene is not None:
            self._scene.clear()

        if isinstance(payload, dict) and payload.get("op") == "add":
            geom_data = payload_to_geom_data(payload)
        else:
            geom_data = payload

        self._scene = Scene(self, geom_data, self.__scene_cfg())
        self._scene.set_axis_constraint(self.axis_constraint_mask)

        if self._camera_controller is None:
            self._camera_controller = CameraController(
                self, self._scene, self.__camera_cfg()
            )
        else:
            self._camera_controller.scene = self._scene

        self._camera_controller.recenter()

    def __update_scene(self, payload: dict):
        """Apply an update payload or rebuild from legacy geom_data."""
        if self._scene is None:
            self.__load_scene(payload)
            return

        if isinstance(payload, dict) and payload.get("op") == "update":
            self._scene.apply_patch(payload)
            return

        if isinstance(payload, dict) and "changed_curves" in payload:
            self._scene.apply_patch(payload)
            return

        self._scene.rebuild(payload)

    def __delete_in_scene(self, payload: ScenePayload):
        """Remove curves listed in a delete payload."""
        if self._scene is None:
            return
        tags = payload.get("deleted_curves", [])
        if tags:
            self._scene.remove_curves([str(t) for t in tags])

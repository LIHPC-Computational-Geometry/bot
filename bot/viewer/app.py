import queue
import tomllib
import os

from direct.showbase.ShowBase import ShowBase

from bot.view.components import Scene
from bot.control.camera import CameraController
from bot.control.mouse import MouseHandler
from bot.control.keyboard import KeyboardHandler

_DEFAULT_SCENE = {
    'background_color': [0.1, 0.1, 0.12],
    'line_thickness': 2,
}
_DEFAULT_CAMERA = {
    'pan_speed': 10.0,
    'rotate_speed': 100.0,
    'animation_duration': 0.5,
    'show_marker_at_start': False,
}


class ViewerApp(ShowBase):
    """
    Internal  application.
    Receives display data via a thread-safe queue and renders it.
    Sends user interaction events back via on_event_cb.
    """

    def __init__(self, config_filename: str, cmd_queue: queue.Queue, on_event_cb):
        super().__init__()

        self._cmd_queue = cmd_queue
        self._on_event_cb = on_event_cb
        self._scene = None
        self._camera_controller = None

        self._config = self._load_config(config_filename)

        self.kb_handler = KeyboardHandler()
        self.mouse_handler = MouseHandler()

        taskMgr.add(self._process_commands, "ViewerProcessCommands")

    def _load_config(self, config_filename: str) -> dict:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base_dir, config_filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return tomllib.load(f)
        return {}

    def _scene_cfg(self) -> dict:
        return self._config.get('view', {}).get('scene', _DEFAULT_SCENE)

    def _camera_cfg(self) -> dict:
        cfg = _DEFAULT_CAMERA.copy()
        cfg.update(self._config.get('view', {}).get('camera', {}))
        return cfg

    def _process_commands(self, task):
        while not self._cmd_queue.empty():
            try:
                cmd, data = self._cmd_queue.get_nowait()
                if cmd == 'load':
                    self.load_scene(data)
                elif cmd == 'update':
                    self.update_scene(data)
                elif cmd == 'reload_config':
                    self._config = data
                    if self._scene:
                        self._scene.apply_settings(self._scene_cfg())
                    if self._camera_controller:
                        self._camera_controller.apply_settings(self._camera_cfg())
            except queue.Empty:
                break
        return task.cont

    def load_scene(self, geom_data: dict):
        """Load (or reload) the scene from geom_data."""
        if self._scene is not None:
            self._scene.clear()

        self._scene = Scene(self, geom_data, self._scene_cfg())

        if self._camera_controller is None:
            self._camera_controller = CameraController(self, self._scene, self._camera_cfg())
        else:
            self._camera_controller.scene = self._scene

        self._camera_controller.instant_recenter()

    def update_scene(self, geom_data: dict):
        """Update geometry without recreating the scene."""
        if self._scene is None:
            self.load_scene(geom_data)
        else:
            self._scene.rebuild(geom_data)

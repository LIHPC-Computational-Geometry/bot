"""
Viewer: lance Panda3D dans un sous-processus séparé.

Sur macOS (et en général), OpenGL doit tourner sur le thread principal du
processus qui possède la fenêtre. En lançant Panda3D dans un sous-processus,
son thread principal est libre pour Panda3D, et le thread principal d'IPython
reste entièrement interactif. Les données transitent par un Pipe
multiprocessing sous forme de dicts sérialisables.
"""

import multiprocessing as mp
import threading
from typing import Callable, Optional

from bot.core.cad import Model


# ---------------------------------------------------------------------------
# Fonction d'entrée du sous-processus (doit être au niveau module pour pickle)
# ---------------------------------------------------------------------------

def _viewer_subprocess(conn, config_filename: str):
    """
    Point d'entrée du sous-processus Panda3D.
    Tourne sur le thread principal du sous-processus → macOS safe.
    """
    import queue as _queue

    cmd_queue = _queue.Queue()

    # Thread qui lit le pipe parent → met dans la queue interne
    def _pipe_reader():
        while True:
            try:
                msg = conn.recv()
                cmd_queue.put(msg)
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
    app.run()   # bloquant — c'est voulu, c'est le thread principal du sous-processus


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

class Viewer:
    """
    Viewer 3D connecté à un noyau Model.

    Usage en IPython :
        k = bot.CADModel()
        k.open("part.geo")

        v = bot.Viewer()
        v.connect(k).run()   # non-bloquant : Panda3D tourne dans un sous-processus

        k.add_point([1, 2, 3])                      # → viewer mis à jour
        v.on_pick = lambda coords: k.add_point(coords)  # viewer → noyau

    Plusieurs viewers peuvent être connectés au même modèle (un sous-processus
    par viewer).
    """

    def __init__(self, config_filename: str = "bot_config.toml"):
        self._config_filename = config_filename
        self.model: Optional[Model] = None
        self._conn = None           # extrémité parent du Pipe
        self._process = None        # sous-processus Panda3D
        self._event_thread = None   # thread d'écoute des events retour
        self.on_pick: Optional[Callable] = None

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def connect(self, model: Model) -> "Viewer":
        """
        Connecte ce viewer à un noyau Model.
        Peut être appelé avant ou après run().
        Retourne self pour le chaînage.
        """
        if self.model is not None:
            self.model.remove_observer(self)
        self.model = model
        model.add_observer(self)
        if self._conn is not None:
            self._send('load', model.get_render_data())
        return self

    def disconnect(self) -> "Viewer":
        """Détache le viewer du modèle courant."""
        if self.model is not None:
            self.model.remove_observer(self)
            self.model = None
        return self

    def run(self) -> "Viewer":
        """
        Lance le viewer dans un sous-processus séparé (non-bloquant).
        Retourne self pour le chaînage.
        """
        ctx = mp.get_context('spawn')
        parent_conn, child_conn = ctx.Pipe()
        self._conn = parent_conn

        self._process = ctx.Process(
            target=_viewer_subprocess,
            args=(child_conn, self._config_filename),
            daemon=True,
        )
        self._process.start()
        child_conn.close()  # inutile dans le processus parent

        if self.model is not None:
            self._send('load', self.model.get_render_data())

        self._start_event_listener()
        return self

    # ------------------------------------------------------------------
    # Callback observer (appelé par Model quand l'état change)
    # ------------------------------------------------------------------

    def update(self, model: Model):
        """called by the model through the oberser pattern."""
        self._send('update', model.get_render_data())

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    def _send(self, cmd: str, data):
        if self._conn is not None:
            try:
                self._conn.send((cmd, data))
            except BrokenPipeError:
                pass

    def _start_event_listener(self):
        """Thread léger qui reçoit les events du sous-processus (ex : picking)."""
        def _listen():
            while True:
                try:
                    if self._conn.poll(0.1):
                        event_type, data = self._conn.recv()
                        if event_type == 'pick' and self.on_pick is not None:
                            self.on_pick(data)
                except EOFError:
                    break
                except Exception:
                    pass

        self._event_thread = threading.Thread(target=_listen, daemon=True)
        self._event_thread.start()

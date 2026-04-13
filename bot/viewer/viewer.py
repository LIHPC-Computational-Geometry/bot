"""
Viewer: lance Panda3D dans un sous-processus séparé.

Sur macOS (et en général), OpenGL doit tourner sur le thread principal du
processus qui possède la fenêtre. En lançant Panda3D dans un sous-processus,
son thread principal est libre pour Panda3D, et le thread principal d'IPython
reste entièrement interactif. Les données transitent par un Pipe
multiprocessing sous forme de dicts sérialisables.
"""

import math
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
                if msg[0] == 'exit': # Commande de sortie
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
        self._running = False

        self._default_last_hovered = None

        self.on_pick: Optional[Callable] = None
        self.on_hover: Optional[Callable] = self._default_on_hover



    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def highlight_curve(self, tag: str, color: list) -> "Viewer":
        """Colore la géométrie associée à un tag."""
        self._send('highlight_curve', {'tag': tag, 'color': color})
        return self

    def set_hud_text(self, text: str) -> "Viewer":
        """Met à jour le texte affiché en surimpression à l'écran."""
        self._send('update_hud', {'text': text})
        return self

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
        self._running = True

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

    def stop(self):
        """
        Arrête proprement le viewer et libère les ressources.
        """
        self._running = False

        # 1. Notifier le modèle qu'on ne regarde plus
        self.disconnect()

        # 2. Envoyer le signal d'arrêt au sous-processus
        if self._conn is not None:
            try:
                self._send('exit', None)
            except:
                pass

        # 3. Attendre la fin du processus
        if self._process is not None:
            self._process.join(timeout=2.0) # On laisse 2 secondes pour fermer
            if self._process.is_alive():
                self._process.terminate() # Force brute si tjs vivant
            self._process = None

        # 4. Fermer la communication
        if self._conn is not None:
            self._conn.close()
            self._conn = None

        self._event_thread = None
        print("Stopped Viewer")
    # ------------------------------------------------------------------
    # Callback observer (appelé par Model quand l'état change)
    # ------------------------------------------------------------------

    def update(self, model: Model):
        """Called by the Model through the observer pattern when geometry changes."""
        self._send('update', model.get_render_data())

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    def _send(self, cmd: str, data):
        """Send a ``(cmd, data)`` message to the child process over the pipe."""
        if self._conn is not None:
            try:
                self._conn.send((cmd, data))
            except BrokenPipeError:
                pass

    def _start_event_listener(self):
        """Thread léger qui reçoit les events du sous-processus (ex : picking)."""
        def _listen():
            while self._running:
                try:
                    if self._conn.poll(0.1):
                        event_type, data = self._conn.recv()
                        if event_type == 'pick' and self.on_pick is not None:
                            self.on_pick(data)
                        elif event_type == 'hover' and self.on_hover is not None:
                            self.on_hover(data)
                except (EOFError, BrokenPipeError, AttributeError):
                    break
                except Exception:
                    pass

        self._event_thread = threading.Thread(target=_listen, daemon=True)
        self._event_thread.start()

    # ------------------------------------------------------------------
    # Comportements Interactifs par Défaut
    # ------------------------------------------------------------------

    # Dans bot/viewer/viewer.py

    def _default_on_hover(self, tag):
        """Comportement par défaut : met en surbrillance et affiche les détails spatiaux."""
        if tag is not None:
            # 1. Nettoyage de la courbe précédente
            if self._default_last_hovered is not None and self._default_last_hovered != tag:
                self.highlight_curve(self._default_last_hovered, [1, 1, 1, 1])

            # 2. Construction du texte d'information
            info_text = f"--- Courbe {tag} ---\n"

            if self.model is not None:
                try:
                    # Récupération des tags des extrémités (ex: [1, 2])
                    tags_ext = self.model.get_end_points(int(tag))

                    # Récupération des coordonnées réelles via la nouvelle fonction
                    coords_a = self.model.get_point_coords(tags_ext[0])
                    coords_b = self.model.get_point_coords(tags_ext[1])

                    # Formatage pour le HUD
                    pt_a = f"({coords_a[0]:.2f}, {coords_a[1]:.2f}, {coords_a[2]:.2f})"
                    pt_b = f"({coords_b[0]:.2f}, {coords_b[1]:.2f}, {coords_b[2]:.2f})"

                    info_text += f"Type : Segment Linéaire\n"
                    info_text += f"Extrémité A : {pt_a}\n"
                    info_text += f"Extrémité B : {pt_b}"

                except Exception as e:
                    info_text += f"Erreur : {str(e)}"

            # 3. Application visuelle
            self.set_hud_text(info_text)
            self.highlight_curve(tag, [1, 0.5, 0, 1]) # Orange
            self._default_last_hovered = tag

        else:
            # Gestion du vide
            if self._default_last_hovered is not None:
                self.highlight_curve(self._default_last_hovered, [1, 1, 1, 1])
                self.set_hud_text("Prêt. Survolez ou cliquez sur les courbes.")
                self._default_last_hovered = None

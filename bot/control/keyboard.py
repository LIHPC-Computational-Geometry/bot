from direct.showbase.InputStateGlobal import inputState
import sys


class KeyboardHandler:
    """
    Handles keyboard input and dispatches camera commands via the Panda3D messenger.

    Arrow keys produce continuous smooth panning through a per-frame task;
    shortcut keys (c, x, y, z, f5…) send one-shot command events.
    """

    def __init__(self, base):
        """
        Register all key bindings and start the continuous move task.

        Args:
            base: Panda3D ShowBase instance.
        """
        self.base = base

        # Dictionnaire pour stocker l'état des touches
        self.keys = {"arrow_left": 0, "arrow_right": 0, "arrow_up": 0, "arrow_down": 0}

        # On écoute l'appui et le relâchement
        for key in self.keys:
            self.base.accept(key, self.set_key, [key, 1])
            self.base.accept(key + "-up", self.set_key, [key, 0])

        # Actions directes (Events)
        self.base.accept("escape", sys.exit)
        self.base.accept("f5", lambda: base.messenger.send("cmd_hot_reload"))
        self.base.accept("c", lambda: base.messenger.send("cmd_center"))
        self.base.accept("alt-x", lambda: base.messenger.send("cmd_align_plane", ["x"]))
        self.base.accept("alt-y", lambda: base.messenger.send("cmd_align_plane", ["y"]))
        self.base.accept("alt-z", lambda: base.messenger.send("cmd_align_plane", ["z"]))

        self.base.accept("x", lambda: base.messenger.send("cmd_axis_constraint", [1]))
        self.base.accept("y", lambda: base.messenger.send("cmd_axis_constraint", [2]))
        self.base.accept("z", lambda: base.messenger.send("cmd_axis_constraint", [4]))
        self.base.accept(
            "shift-x", lambda: base.messenger.send("cmd_axis_constraint", [6])
        )
        self.base.accept(
            "shift-y", lambda: base.messenger.send("cmd_axis_constraint", [5])
        )
        self.base.accept(
            "shift-z", lambda: base.messenger.send("cmd_axis_constraint", [3])
        )

        # Axis-constraint shortcuts (0..7 mask).
        # x=1, y=2, z=4
        for mask in range(8):
            self.base.accept(
                str(mask),
                lambda m=mask: base.messenger.send("cmd_axis_constraint", [m]),
            )
        # Flèches directionnelles
        # self.base.accept('arrow_left',  lambda: base.messenger.send("cmd_pan", [-1, 0]))
        # self.base.accept('arrow_right', lambda: base.messenger.send("cmd_pan", [1, 0]))
        # self.base.accept('arrow_up',    lambda: base.messenger.send("cmd_pan", [0, 1]))
        # self.base.accept('arrow_down',  lambda: base.messenger.send("cmd_pan", [0, -1]))

        self.base.accept("p", lambda: base.messenger.send("cmd_toggle_marker"))
        inputState.watchWithModifiers("up", "arrow_up")
        inputState.watchWithModifiers("down", "arrow_down")
        inputState.watchWithModifiers("left", "arrow_left")
        inputState.watchWithModifiers("right", "arrow_right")
        # On ajoute une tâche pour traiter le mouvement fluide
        self.base.taskMgr.add(self.move_task, "KeyboardMoveTask")

    def set_key(self, key, value):
        """Update the pressed state of *key* (1 = down, 0 = up)."""
        self.keys[key] = value

    def move_task(self, task):
        """
        Per-frame task: emit ``cmd_pan`` while arrow keys are held down.

        Movement is frame-rate independent (scaled by ``clock.getDt()``).

        Returns:
            task.cont to keep the task alive.
        """
        # On calcule le vecteur de direction selon les touches pressées
        dx = self.keys["arrow_right"] - self.keys["arrow_left"]
        dy = self.keys["arrow_up"] - self.keys["arrow_down"]

        if dx != 0 or dy != 0:
            # On envoie une petite valeur de déplacement constante
            # On multiplie par globalClock.getDt() pour que la vitesse soit
            # la même peu importe la puissance du PC (Frame Rate Independent)
            dt = self.base.clock.getDt()
            speed = 0.5  # Ajustez cette valeur pour la sensibilité clavier
            self.base.messenger.send("cmd_pan", [dx * speed * dt, dy * speed * dt])

        return task.cont

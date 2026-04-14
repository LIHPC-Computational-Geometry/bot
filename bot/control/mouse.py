from direct.showbase.InputStateGlobal import inputState
from panda3d.core import Point2, MouseButton
from panda3d.core import Point2, MouseButton, CollisionTraverser, CollisionNode, CollisionRay, CollisionHandlerQueue

class MouseHandler:
    """
    Handles mouse input and dispatches camera commands via the Panda3D messenger.

    - Left-button drag          → ``cmd_rotate``
    - Shift + left-button drag  → ``cmd_pan``
    - Scroll wheel              → ``cmd_zoom``
    """

    def __init__(self, base):
        """
        Register mouse-wheel bindings and start the per-frame update task.

        Args:
            base: Panda3D ShowBase instance.
        """
        self.base = base
        self.prev_mouse_pos = None

        # FIXME: matrice de projection peut-être pas correct
        self.picker = CollisionTraverser()
        self.pq = CollisionHandlerQueue()
        self.pickerNode = CollisionNode('mouseRay')
        self.pickerNode.setIntoCollideMask(0)
        self.pickerNP = self.base.camera.attachNewNode(self.pickerNode)
        self.pickerRay = CollisionRay()
        self.pickerNode.addSolid(self.pickerRay)
        self.picker.addCollider(self.pickerNP, self.pq)

        self.last_hovered_tag = None

        # On écoute la molette
        self.base.accept("wheel_up",   lambda: self.base.messenger.send("cmd_zoom", [0.9]))
        self.base.accept("wheel_down", lambda: self.base.messenger.send("cmd_zoom", [1.1]))

        self.base.taskMgr.add(self.update, "MouseTask")

    def update(self, task):
        """
        Per-frame task: compute mouse delta and emit the appropriate command.

        Sends ``cmd_rotate`` on plain left-drag and ``cmd_pan`` on
        Shift+left-drag. The delta is computed frame-to-frame to keep
        movements small and smooth.

        Returns:
            task.cont to keep the task alive.
        """
        if self.base.mouseWatcherNode.hasMouse():
            m_pos = self.base.mouseWatcherNode.getMouse()
            curr_pos = Point2(m_pos.getX(), m_pos.getY())

            self.pickerRay.setFromLens(self.base.camNode, m_pos.getX(), m_pos.getY())
            self.picker.traverse(self.base.render)

            hovered_tag = None
            if self.pq.getNumEntries() > 0:
                self.pq.sortEntries()
                # On prend le premier objet touché par le rayon
                entry = self.pq.getEntry(0)
                np = entry.getIntoNodePath()
                hovered_tag = np.getTag('curve_tag')

            # Si on survole une nouvelle courbe (ou si on ne survole plus rien)
            if hovered_tag != self.last_hovered_tag:
                self.last_hovered_tag = hovered_tag
                # On envoie l'info au parent via le callback
                self.base._on_event_cb('hover', hovered_tag)

            if self.base.mouseWatcherNode.isButtonDown(MouseButton.one()):
                if self.prev_mouse_pos is not None:
                    # On calcule le delta par rapport à la frame précédente
                    delta = curr_pos - self.prev_mouse_pos

                    # On n'envoie le message QUE si la souris a réellement bougé
                    if delta.lengthSquared() > 0:
                        if self.base.mouseWatcherNode.isButtonDown("shift"):
                            self.base.messenger.send("cmd_pan", [delta.getX(), delta.getY()])
                        else:
                            self.base.messenger.send("cmd_rotate", [delta.getX(), delta.getY()])

                # CRITIQUE : On met à jour prev_mouse_pos À CHAQUE FRAME
                # pour que le delta reste minuscule entre deux frames.
                self.prev_mouse_pos = Point2(curr_pos)
            else:
                self.prev_mouse_pos = None

        return task.cont

    def is_shift_down(self):
        """Return True if the Shift modifier is currently held."""
        return inputState.isSet('shift')

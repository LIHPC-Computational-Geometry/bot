from direct.showbase.InputStateGlobal import inputState
from panda3d.core import BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionTraverser
from panda3d.core import GeomNode, MouseButton, Plane, Point2, Point3, Vec3


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
        self._left_was_down = False

        self.picker = CollisionTraverser()
        self.pq = CollisionHandlerQueue()
        self.pickerNode = CollisionNode('mouseRay')
        self.pickerNP = self.base.camera.attachNewNode(self.pickerNode)
        self.pickerNode.setFromCollideMask(BitMask32.bit(1) | BitMask32.bit(2))
        self.pickerNode.setIntoCollideMask(BitMask32.allOff())
        self.pickerRay = CollisionRay()
        self.pickerNode.addSolid(self.pickerRay)
        self.picker.addCollider(self.pickerNP, self.pq)

        self.last_hovered_tag = None
        self.edit_mode_enabled = False
        self.active_curve_tag = None
        self.dragging_cp = False
        self.drag_curve_tag = None
        self.drag_cp_index = None
        self.drag_plane = None
        self._last_drag_emit = 0.0

        self.base.accept("wheel_up",   lambda: self.base.messenger.send("cmd_zoom", [0.9]))
        self.base.accept("wheel_down", lambda: self.base.messenger.send("cmd_zoom", [1.1]))

        self.base.taskMgr.add(self.update, "MouseTask")

    def set_edit_mode(self, enabled: bool, curve_tag=None):
        self.edit_mode_enabled = bool(enabled)
        self.active_curve_tag = str(curve_tag) if curve_tag is not None else None
        if not self.edit_mode_enabled:
            self.dragging_cp = False
            self.drag_curve_tag = None
            self.drag_cp_index = None
            self.drag_plane = None

    def _pick_entry(self, m_pos, mask: BitMask32):
        self.pickerNode.setFromCollideMask(mask)
        self.pickerRay.setFromLens(self.base.camNode, m_pos.getX(), m_pos.getY())
        self.picker.traverse(self.base.render)
        if self.pq.getNumEntries() == 0:
            return None
        self.pq.sortEntries()
        return self.pq.getEntry(0)

    def _entry_metadata(self, entry):
        np = entry.getIntoNodePath()
        return {
            'curve_tag': np.getNetTag('curve_tag') if np.hasNetTag('curve_tag') else None,
            'cp_index': np.getNetTag('cp_index') if np.hasNetTag('cp_index') else None,
            'pick_kind': np.getNetTag('pick_kind') if np.hasNetTag('pick_kind') else None,
            'point': entry.getSurfacePoint(self.base.render),
        }

    def _handle_hover(self, m_pos):
        """Processes ray picking to detect hovered curves."""
        hovered_tag = None
        hover_entry = self._pick_entry(m_pos, BitMask32.bit(1))
        if hover_entry is not None:
            metadata = self._entry_metadata(hover_entry)
            hovered_tag = metadata['curve_tag']

        # Si on survole une nouvelle courbe (ou si on ne survole plus rien)
        if hovered_tag != self.last_hovered_tag:
            self.last_hovered_tag = hovered_tag
            # On envoie l'info au parent via le callback
            self.base._on_event_cb('hover', hovered_tag)

    def _build_drag_plane(self, start_point: Point3):
        normal = self.base.render.getRelativeVector(self.base.cam, Vec3(0, 1, 0))
        normal.normalize()
        return Plane(normal, start_point)

    def _mouse_to_plane(self, m_pos):
        if self.drag_plane is None:
            return None
        p_from = Point3()
        p_to = Point3()
        if not self.base.camLens.extrude(m_pos, p_from, p_to):
            return None
        p_from = self.base.render.getRelativePoint(self.base.cam, p_from)
        p_to = self.base.render.getRelativePoint(self.base.cam, p_to)
        hit = Point3()
        if self.drag_plane.intersectsLine(hit, p_from, p_to):
            return [hit[0], hit[1], hit[2]]
        return None

    def _handle_cp_interaction(self, m_pos, left_down):
        if not self.edit_mode_enabled:
            return

        if left_down and not self._left_was_down and not self.dragging_cp:
            entry = self._pick_entry(m_pos, BitMask32.bit(2))
            if entry is None:
                return
            metadata = self._entry_metadata(entry)
            if metadata['pick_kind'] != 'cp' or metadata['curve_tag'] is None or metadata['cp_index'] is None:
                return
            if self.active_curve_tag is not None and metadata['curve_tag'] != self.active_curve_tag:
                return

            self.dragging_cp = True
            self.drag_curve_tag = metadata['curve_tag']
            self.drag_cp_index = int(metadata['cp_index'])
            self.drag_plane = self._build_drag_plane(metadata['point'])
            self.base._on_event_cb('cp_pick_start', {
                'tag': self.drag_curve_tag,
                'cp_index': self.drag_cp_index,
                'world_pos': [metadata['point'][0], metadata['point'][1], metadata['point'][2]],
            })
            return

        if self.dragging_cp and left_down:
            world_pos = self._mouse_to_plane(m_pos)
            if world_pos is None:
                return
            if getattr(self.base, "_scene", None) is not None:
                self.base._scene.preview_control_point(int(self.drag_curve_tag), self.drag_cp_index, world_pos)
            self.base._on_event_cb('cp_drag', {
                'tag': self.drag_curve_tag,
                'cp_index': self.drag_cp_index,
                'world_pos': world_pos,
            })
            return

        if self.dragging_cp and not left_down and self._left_was_down:
            world_pos = self._mouse_to_plane(m_pos)
            self.base._on_event_cb('cp_pick_end', {
                'tag': self.drag_curve_tag,
                'cp_index': self.drag_cp_index,
                'world_pos': world_pos,
            })
            self.dragging_cp = False
            self.drag_curve_tag = None
            self.drag_cp_index = None
            self.drag_plane = None

    def _handle_curve_click(self, m_pos, left_down):
        if self.edit_mode_enabled:
            return
        if not left_down or self._left_was_down:
            return
        entry = self._pick_entry(m_pos, BitMask32.bit(1))
        if entry is None:
            return
        metadata = self._entry_metadata(entry)
        if metadata['pick_kind'] == 'curve' and metadata['curve_tag'] is not None:
            self.base._on_event_cb('curve_selected', metadata['curve_tag'])

    def _handle_drag(self, curr_pos):
        """Handles mouse drag for rotating and panning."""
        if self.dragging_cp:
            self.prev_mouse_pos = Point2(curr_pos)
            return

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
            left_down = self.base.mouseWatcherNode.isButtonDown(MouseButton.one())

            self._handle_hover(m_pos)
            self._handle_curve_click(m_pos, left_down)
            self._handle_cp_interaction(m_pos, left_down)
            self._handle_drag(curr_pos)
            self._left_was_down = left_down

        return task.cont

    def is_shift_down(self):
        """Return True if the Shift modifier is currently held."""
        return inputState.isSet('shift')

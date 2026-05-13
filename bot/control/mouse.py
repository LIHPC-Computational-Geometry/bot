from direct.showbase.InputStateGlobal import inputState
from panda3d.core import (
    BitMask32,
    CollisionHandlerQueue,
    CollisionNode,
    CollisionRay,
    CollisionTraverser,
)
from panda3d.core import MouseButton, Plane, Point2, Point3, Vec3


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
        self.pickerNode = CollisionNode("mouseRay")
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
        self.drag_start_world_pos = None
        self.drag_last_valid_world_pos = None
        self.drag_offset = [0.0, 0.0, 0.0]
        self.drag_active_mask = 7
        self.axis_constraint_mask = 7
        self._last_drag_emit = 0.0

        self.base.accept(
            "wheel_up", lambda: self.base.messenger.send("cmd_zoom", [0.9])
        )
        self.base.accept(
            "wheel_down", lambda: self.base.messenger.send("cmd_zoom", [1.1])
        )

        self.base.taskMgr.add(self.update, "MouseTask")

    def set_edit_mode(self, enabled: bool, curve_tag=None):
        self.edit_mode_enabled = bool(enabled)
        self.active_curve_tag = str(curve_tag) if curve_tag is not None else None
        if not self.edit_mode_enabled:
            self._reset_drag_state()

    def set_axis_constraint(self, mask: int):
        self.axis_constraint_mask = max(0, min(7, int(mask)))

    def _apply_axis_constraint(self, start_pos, candidate_pos):
        if start_pos is None or candidate_pos is None:
            return candidate_pos
        if self.axis_constraint_mask == 0:
            return [start_pos[0], start_pos[1], start_pos[2]]
        constrained = [candidate_pos[0], candidate_pos[1], candidate_pos[2]]
        if not (self.axis_constraint_mask & 1):
            constrained[0] = start_pos[0]
        if not (self.axis_constraint_mask & 2):
            constrained[1] = start_pos[1]
        if not (self.axis_constraint_mask & 4):
            constrained[2] = start_pos[2]
        return constrained

    def _reset_drag_state(self):
        self.dragging_cp = False
        self.drag_curve_tag = None
        self.drag_cp_index = None
        self.drag_plane = None
        self.drag_start_world_pos = None
        self.drag_last_valid_world_pos = None
        self.drag_offset = [0.0, 0.0, 0.0]
        self.drag_active_mask = self.axis_constraint_mask

    def _finalize_drag(self, world_pos):
        if self.drag_curve_tag is not None and self.drag_cp_index is not None:
            if getattr(self.base, "_scene", None) is not None:
                self.base._scene.set_cp_color(
                    self.drag_curve_tag, self.drag_cp_index, [0.5, 0.5, 0.5, 1]
                )
                self.base._scene.hide_axis_guide()
                # NOTE: On valide la nouvelle géométrie physique maintenant que la souris est relâchée
                curve = self.base._scene.curves.get(int(self.drag_curve_tag))
                if curve is not None:
                    curve._attachColissionNode()
                    curve._rebuild_cp_collision()
            self.base._on_event_cb(
                "cp_pick_end",
                {
                    "tag": self.drag_curve_tag,
                    "cp_index": self.drag_cp_index,
                    "world_pos": world_pos,
                },
            )
        self._reset_drag_state()

    def _pick_entry(self, m_pos, expected_kind: str):
        self.pickerNode.setFromCollideMask(BitMask32.bit(1) | BitMask32.bit(2))
        self.pickerRay.setFromLens(self.base.camNode, m_pos.getX(), m_pos.getY())
        self.picker.traverse(self.base.render)

        if self.pq.getNumEntries() == 0:
            return None

        entries = []
        for i in range(self.pq.getNumEntries()):
            entries.append(self.pq.getEntry(i))

        def get_priority_distance_depth(entry):
            np = entry.getIntoNodePath()
            pick_kind = np.getNetTag("pick_kind") if np.hasNetTag("pick_kind") else ""
            depth = entry.getSurfacePoint(self.base.cam).getY()

            if pick_kind == "cp":
                solid = entry.getInto()
                if hasattr(solid, "getCenter"):
                    # NOTE: On convertit le centre 3D réel du point de contrôle...
                    cp_world = self.base.render.getRelativePoint(np, solid.getCenter())
                    p2d = Point2()

                    # NOTE: Et on le projette sur l'écran 2D (coordonnées de -1 à 1)
                    if self.base.camLens.project(cp_world, p2d):
                        # NOTE: On compare purement l'écart visuel entre la souris et le centre du point !
                        dist_sq = (p2d.getX() - m_pos.getX())**2 + (p2d.getY() - m_pos.getY())**2
                        return (0, dist_sq, depth)

                return (0, 0.0, depth)

            return (1, 0.0, depth)

        # NOTE: Python triera d'abord par priorité (0 = cp, 1 = curve).
        # En cas d'égalité sur des CPs (rayon touchant plusieurs grosses hitboxes),
        # c'est celui dont le centre visuel est le plus proche de la souris qui gagnera.
        entries.sort(key=get_priority_distance_depth)

        for entry in entries:
            np = entry.getIntoNodePath()
            if np.hasNetTag("pick_kind") and np.getNetTag("pick_kind") == expected_kind:
                return entry

        return None

    def _entry_metadata(self, entry):
        np = entry.getIntoNodePath()
        pick_kind = np.getNetTag("pick_kind") if np.hasNetTag("pick_kind") else None

        point = entry.getSurfacePoint(self.base.render)
        if pick_kind == "cp":
            solid = entry.getInto()
            if hasattr(solid, "getCenter"):
                point = self.base.render.getRelativePoint(np, solid.getCenter())

        return {
            "curve_tag": np.getNetTag("curve_tag")
            if np.hasNetTag("curve_tag")
            else None,
            "cp_index": np.getNetTag("cp_index") if np.hasNetTag("cp_index") else None,
            "pick_kind": pick_kind,
            "point": point,
        }

    def _handle_hover(self, m_pos):
        """Processes ray picking to detect hovered curves."""
        hovered_tag = None
        hover_entry = self._pick_entry(m_pos, "curve")
        if hover_entry is not None:
            metadata = self._entry_metadata(hover_entry)
            hovered_tag = metadata["curve_tag"]

        if hovered_tag != self.last_hovered_tag:
            self.last_hovered_tag = hovered_tag
            self.base._on_event_cb("hover", hovered_tag)

    def _build_drag_plane(self, start_point: Point3):
        normal = self.base.render.getRelativeVector(self.base.cam, Vec3(0, 1, 0))
        normal.normalize()
        return Plane(normal, start_point)

    def _mouse_to_plane(self, m_pos):
        if self.drag_plane is None:
            return None

        ray_origin, ray_dir = self._mouse_to_ray(m_pos)
        if ray_origin is None or ray_dir is None:
            return None

        hit = Point3()
        if self.drag_plane.intersectsLine(hit, ray_origin, ray_origin + ray_dir * 1000000.0):
            return [hit[0], hit[1], hit[2]]
        return None

    def _mouse_to_ray(self, m_pos):
        p_from = Point3()
        p_to = Point3()
        if not self.base.camLens.extrude(m_pos, p_from, p_to):
            return None, None

        dir_cam = Vec3(p_to - p_from)
        dir_cam.normalize()

        # Sécurise l'origine sur le plan focal pour une précision Float32 parfaite
        if abs(dir_cam.getY()) > 1e-6:
            t = (0 - p_from.getY()) / dir_cam.getY()
            origin_cam = p_from + dir_cam * t
        else:
            origin_cam = p_from

        p_from_world = self.base.render.getRelativePoint(self.base.cam, origin_cam)
        direction = self.base.render.getRelativeVector(self.base.cam, dir_cam)

        return p_from_world, direction

    def _closest_point_on_axis_to_ray(self, ray_origin, ray_dir, axis_origin, axis_dir):
        w0 = ray_origin - axis_origin
        a = ray_dir.dot(ray_dir)
        b = ray_dir.dot(axis_dir)
        c = axis_dir.dot(axis_dir)
        d = ray_dir.dot(w0)
        e = axis_dir.dot(w0)
        denom = a * c - b * b
        if abs(denom) < 1e-10:
            return None
        t_axis = (a * e - b * d) / denom
        hit = axis_origin + axis_dir * t_axis
        return [hit[0], hit[1], hit[2]]

    def _plane_normal_from_mask(self, mask):
        if mask == 3:
            return Vec3(0, 0, 1)
        if mask == 5:
            return Vec3(0, 1, 0)
        if mask == 6:
            return Vec3(1, 0, 0)
        return None

    def _mouse_to_constrained_axis(self, m_pos):
        if self.drag_start_world_pos is None:
            return None
        start = self.drag_start_world_pos
        mask = int(self.drag_active_mask)
        if mask == 0:
            return [start[0], start[1], start[2]]
        if mask == 7:
            return self._mouse_to_plane(m_pos)

        ray_origin, ray_dir = self._mouse_to_ray(m_pos)
        if ray_origin is None or ray_dir is None:
            return None

        if mask in (1, 2, 4):
            axis_map = {
                1: Vec3(1, 0, 0),
                2: Vec3(0, 1, 0),
                4: Vec3(0, 0, 1),
            }
            axis_origin = Point3(start[0], start[1], start[2])
            axis_dir = axis_map[mask]
            result = self._closest_point_on_axis_to_ray(
                ray_origin, ray_dir, axis_origin, axis_dir
            )
            if result is not None:
                return result
            fallback = self._mouse_to_plane(m_pos)
            return self._apply_axis_constraint(start, fallback)

        plane_normal = self._plane_normal_from_mask(mask)
        if plane_normal is not None:
            plane = Plane(plane_normal, Point3(start[0], start[1], start[2]))
            ray_to = ray_origin + ray_dir * 100000.0
            hit = Point3()
            if plane.intersectsLine(hit, ray_origin, ray_to):
                return [hit[0], hit[1], hit[2]]
            fallback = self._mouse_to_plane(m_pos)
            return self._apply_axis_constraint(start, fallback)

        fallback = self._mouse_to_plane(m_pos)
        return self._apply_axis_constraint(start, fallback)

    def _handle_cp_interaction(self, m_pos, left_down):
        if not getattr(self, "edit_mode_enabled", False) and not getattr(
            self, "dragging_cp", False
        ):
            return

        # NOTE: Check si une interaction pick un cp vient de commencer
        if left_down and not self._left_was_down and not self.dragging_cp:
            entry = self._pick_entry(m_pos, "cp")
            if entry is None:
                return

            metadata = self._entry_metadata(entry)
            if (
                metadata["pick_kind"] != "cp"
                or metadata["curve_tag"] is None
                or metadata["cp_index"] is None
            ):
                return
            if (
                self.active_curve_tag is not None
                and metadata["curve_tag"] != self.active_curve_tag
            ):
                return

            self.dragging_cp = True
            self.drag_curve_tag = metadata["curve_tag"]
            self.drag_cp_index = int(metadata["cp_index"])
            self.drag_plane = self._build_drag_plane(metadata["point"])
            self.drag_start_world_pos = [
                metadata["point"][0],
                metadata["point"][1],
                metadata["point"][2],
            ]
            self.drag_last_valid_world_pos = list(self.drag_start_world_pos)
            self.drag_active_mask = int(self.axis_constraint_mask)

            initial_hit = self._mouse_to_constrained_axis(m_pos)
            if initial_hit is not None:
                self.drag_offset = [
                    self.drag_start_world_pos[0] - initial_hit[0],
                    self.drag_start_world_pos[1] - initial_hit[1],
                    self.drag_start_world_pos[2] - initial_hit[2],
                ]
            else:
                self.drag_offset = [0.0, 0.0, 0.0]

            self.base._scene.set_cp_color(
                self.drag_curve_tag, self.drag_cp_index, [1, 0.5, 0, 1]
            )
            if getattr(self.base, "_scene", None) is not None:
                self.base._scene.show_axis_guide(
                    self.drag_start_world_pos, self.drag_active_mask
                )
            self.base._on_event_cb(
                "cp_pick_start",
                {
                    "tag": self.drag_curve_tag,
                    "cp_index": self.drag_cp_index,
                    "world_pos": self.drag_start_world_pos,
                },
            )
            return

        # NOTE: le drag du cp est en cours, un envoie régulier de la nouvelle position du cp est envoyé au processus parent
        if self.dragging_cp and left_down:
            self.drag_active_mask = int(self.axis_constraint_mask)
            world_pos = self._mouse_to_constrained_axis(m_pos)
            if world_pos is None:
                return
            world_pos = [
                world_pos[0] + self.drag_offset[0],
                world_pos[1] + self.drag_offset[1],
                world_pos[2] + self.drag_offset[2],
            ]
            self.drag_last_valid_world_pos = list(world_pos)
            if getattr(self.base, "_scene", None) is not None:
                self.base._scene.preview_control_point(
                    int(self.drag_curve_tag), self.drag_cp_index, world_pos
                )
                self.base._scene.update_axis_guide(world_pos, self.drag_active_mask)
            self.base._on_event_cb(
                "cp_drag",
                {
                    "tag": self.drag_curve_tag,
                    "cp_index": self.drag_cp_index,
                    "world_pos": world_pos,
                },
            )
            return

        # NOTE: Fin de déplacement du cp, envoie de la posistion final du cp
        if self.dragging_cp and not left_down and self._left_was_down:
            self.drag_active_mask = int(self.axis_constraint_mask)
            world_pos = self._mouse_to_constrained_axis(m_pos)
            if world_pos is None:
                world_pos = self.drag_last_valid_world_pos
            else:
                world_pos = [
                    world_pos[0] + self.drag_offset[0],
                    world_pos[1] + self.drag_offset[1],
                    world_pos[2] + self.drag_offset[2],
                ]
            self._finalize_drag(world_pos)

    def _handle_curve_click(self, m_pos, left_down):
        if getattr(self, "dragging_cp", False):
            return
        if not left_down or self._left_was_down:
            return

        if getattr(self, "edit_mode_enabled", False):
            cp_entry = self._pick_entry(m_pos, "cp")
            if cp_entry is not None:
                return

        entry = self._pick_entry(m_pos, "curve")
        if entry is None:
            return
        metadata = self._entry_metadata(entry)
        if metadata["pick_kind"] == "curve" and metadata["curve_tag"] is not None:
            self.base._on_event_cb("curve_selected", metadata["curve_tag"])

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
                    self.base.messenger.send(
                        "cmd_pan", [delta.getX(), delta.getY()]
                    )

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
        if not self.base.mouseWatcherNode.hasMouse():
            if self.dragging_cp:
                # On finalise de force pour éviter de rester bloqué dans cet état
                self._finalize_drag(self.drag_last_valid_world_pos)
            self._left_was_down = False
            self.prev_mouse_pos = None
            return task.cont
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
        return inputState.isSet("shift")

from direct.showbase.InputStateGlobal import inputState
from panda3d.core import MouseButton, Point2, Point3

# Importons nos nouveaux modules (Assure-toi que les chemins correspondent à ton projet)
from bot.control.picker import RayPicker
from bot.math.constraints import ConstraintManager


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

        self.picker = RayPicker(self.base)
        self.constraints = ConstraintManager(self.base)

        self.last_hovered_tag = None
        self.edit_mode_enabled = False
        self.active_curve_tag = None

        self.dragging_cp = False
        self.drag_curve_tag = None
        self.drag_cp_index = None
        self.drag_last_valid_world_pos = None
        self.drag_offset = [0.0, 0.0, 0.0]

        # Bindings molette souris
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
        self.constraints.set_axis_constraint(mask)

    def _reset_drag_state(self):
        self.dragging_cp = False
        self.drag_curve_tag = None
        self.drag_cp_index = None
        self.drag_last_valid_world_pos = None
        self.drag_offset = [0.0, 0.0, 0.0]
        self.constraints.drag_start_world_pos = None
        self.constraints.drag_plane = None

    def _finalize_drag(self, world_pos):
        if self.drag_curve_tag is not None and self.drag_cp_index is not None:
            if getattr(self.base, "_scene", None) is not None:
                self.base._scene.set_cp_color(
                    self.drag_curve_tag, self.drag_cp_index, [0.5, 0.5, 0.5, 1]
                )
                self.base._scene.hide_axis_guide()

                curve = self.base._scene.curves.get(int(self.drag_curve_tag))
                if curve is not None:
                    curve.attach_collision_node()
                    curve.rebuild_cp_collision()

            self.base._on_event_cb(
                "cp_pick_end",
                {
                    "tag": self.drag_curve_tag,
                    "cp_index": self.drag_cp_index,
                    "world_pos": world_pos,
                },
            )
        self._reset_drag_state()

    def _handle_hover(self, m_pos: Point2):
        hovered_tag = None
        hover_entry = self.picker.pick_entry(m_pos, "curve")
        if hover_entry is not None:
            metadata = self.picker.get_metadata(hover_entry)
            hovered_tag = metadata.get("curve_tag")

        if hovered_tag != self.last_hovered_tag:
            self.last_hovered_tag = hovered_tag
            self.base._on_event_cb("hover", hovered_tag)

    def _handle_cp_interaction(self, m_pos: Point2, left_down: bool):
        if not self.edit_mode_enabled and not self.dragging_cp:
            return

        # 1. Début de l'interaction (Pick)
        if left_down and not self._left_was_down and not self.dragging_cp:
            entry = self.picker.pick_entry(m_pos, "cp")
            if entry is None:
                return

            metadata = self.picker.get_metadata(entry)
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

            self._start_cp_drag(metadata, m_pos)
            return

        # 2. Déplacement en cours
        if self.dragging_cp and left_down:
            self._update_cp_drag(m_pos)
            return

        # 3. Fin du déplacement
        if self.dragging_cp and not left_down and self._left_was_down:
            self._end_cp_drag(m_pos)

    def _start_cp_drag(self, metadata: dict, m_pos: Point2):
        """Initialise les données lors du clic sur un point de contrôle."""
        self.dragging_cp = True
        self.drag_curve_tag = metadata["curve_tag"]
        self.drag_cp_index = int(metadata["cp_index"])

        start_point = Point3(*metadata["point"])
        self.constraints.drag_plane = self.constraints.build_drag_plane(start_point)
        self.constraints.drag_start_world_pos = list(start_point)
        self.drag_last_valid_world_pos = list(start_point)
        self.constraints.drag_active_mask = int(self.constraints.axis_constraint_mask)

        initial_hit = self.constraints.mouse_to_constrained_axis(m_pos)
        if initial_hit is not None:
            self.drag_offset = [start_point[i] - initial_hit[i] for i in range(3)]
        else:
            self.drag_offset = [0.0, 0.0, 0.0]

        self.base._scene.set_cp_color(
            self.drag_curve_tag, self.drag_cp_index, [1, 0.5, 0, 1]
        )
        if getattr(self.base, "_scene", None) is not None:
            self.base._scene.show_axis_guide(
                start_point, self.constraints.drag_active_mask
            )

        self.base._on_event_cb(
            "cp_pick_start",
            {
                "tag": self.drag_curve_tag,
                "cp_index": self.drag_cp_index,
                "world_pos": list(start_point),
            },
        )

    def _update_cp_drag(self, m_pos: Point2):
        """Met à jour la position pendant le déplacement de la souris."""
        self.constraints.drag_active_mask = int(self.constraints.axis_constraint_mask)
        world_pos = self.constraints.mouse_to_constrained_axis(m_pos)
        if world_pos is None:
            return

        world_pos = [world_pos[i] + self.drag_offset[i] for i in range(3)]
        self.drag_last_valid_world_pos = list(world_pos)

        if getattr(self.base, "_scene", None) is not None:
            self.base._scene.preview_control_point(
                int(self.drag_curve_tag), self.drag_cp_index, world_pos
            )
            self.base._scene.update_axis_guide(
                world_pos, self.constraints.drag_active_mask
            )

        self.base._on_event_cb(
            "cp_drag",
            {
                "tag": self.drag_curve_tag,
                "cp_index": self.drag_cp_index,
                "world_pos": world_pos,
            },
        )

    def _end_cp_drag(self, m_pos: Point2):
        """Finalise le déplacement lors du relâchement du clic."""
        self.constraints.drag_active_mask = int(self.constraints.axis_constraint_mask)
        world_pos = self.constraints.mouse_to_constrained_axis(m_pos)
        if world_pos is None:
            world_pos = self.drag_last_valid_world_pos
        else:
            world_pos = [world_pos[i] + self.drag_offset[i] for i in range(3)]

        self._finalize_drag(world_pos)

    def _handle_curve_click(self, m_pos: Point2, left_down: bool):
        if self.dragging_cp or not left_down or self._left_was_down:
            return

        if self.edit_mode_enabled:
            if self.picker.pick_entry(m_pos, "cp") is not None:
                return

        entry = self.picker.pick_entry(m_pos, "curve")
        if entry is None:
            return

        metadata = self.picker.get_metadata(entry)
        if (
            metadata.get("pick_kind") == "curve"
            and metadata.get("curve_tag") is not None
        ):
            self.base._on_event_cb("curve_selected", metadata["curve_tag"])

    def _handle_drag(self, curr_pos: Point2):
        if self.dragging_cp:
            self.prev_mouse_pos = Point2(curr_pos)
            return

        if self.base.mouseWatcherNode.isButtonDown(MouseButton.one()):
            if self.prev_mouse_pos is not None:
                delta = curr_pos - self.prev_mouse_pos
                if delta.lengthSquared() > 0:
                    self.base.messenger.send("cmd_pan", [delta.getX(), delta.getY()])
            self.prev_mouse_pos = Point2(curr_pos)
        else:
            self.prev_mouse_pos = None

    def update(self, task):
        if not self.base.mouseWatcherNode.hasMouse():
            if self.dragging_cp:
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

    def is_shift_down(self) -> bool:
        return inputState.isSet("shift")

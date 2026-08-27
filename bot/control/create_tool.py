import copy

from panda3d.core import LineSegs, Point2, Point3

from bot.core.spline import SplineModel
from bot.viewer.contracts import ViewEventType


class CreateSplineTool:
    """
    Tool for managing the B-Spline creation state machine and interaction flow.
    It handles 3D point projection, rubber-band preview generation, and event firing.
    """

    def __init__(self, base, constraints, on_event_cb):
        self.base = base
        self.constraints = constraints
        self.on_event_cb = on_event_cb
        self.is_active = False
        self.state = "IDLE"
        self.points = []
        self.preview_node = self.base.render.attachNewNode("spline_preview_root")
        self.preview_node.setLightOff()
        self._current_preview_np = None

    def set_enabled(self, enabled: bool):
        """Activates or deactivates the creation mode."""
        self.is_active = enabled
        if self.is_active:
            self.state = "WAITING_FIRST_POINT"
        else:
            self._discard_curve()

    def _get_initial_focus(self):
        """Retrieves the camera's focal point to avoid placing the curve too far into the depth."""
        if hasattr(self.base, "_camera_controller") and self.base._camera_controller:
            return list(self.base._camera_controller.model_center)
        return [0.0, 0.0, 0.0]

    def on_mouse_click(self, m_pos: Point2, button: str):
        """Handles mouse clicks to advance the state machine."""
        if not self.is_active or button != "right":
            return

        if self.state == "WAITING_FIRST_POINT":
            start_pos = self._get_initial_focus()
            self.constraints.drag_start_world_pos = start_pos
            self.constraints.drag_plane = self.constraints.build_drag_plane(
                Point3(*start_pos)
            )
            self.constraints.drag_active_mask = 7
        else:
            self.constraints.drag_active_mask = self.constraints.axis_constraint_mask

        world_pos = self.constraints.mouse_to_constrained_axis(m_pos)
        if world_pos:
            self.points.append(world_pos)
            self.state = "DRAWING"
            self.constraints.drag_start_world_pos = world_pos
            self.constraints.drag_plane = self.constraints.build_drag_plane(
                Point3(*world_pos)
            )
            self._draw_preview()

    def on_mouse_move(self, m_pos: Point2):
        """Updates the real-time rubber-band preview locally when moving the mouse."""
        if not self.is_active or self.state != "DRAWING":
            return

        self.constraints.drag_active_mask = self.constraints.axis_constraint_mask

        if (
            self.constraints.drag_active_mask == 7
            and self.constraints.drag_start_world_pos
        ):
            self.constraints.drag_plane = self.constraints.build_drag_plane(
                Point3(*self.constraints.drag_start_world_pos)
            )

        world_pos = self.constraints.mouse_to_constrained_axis(m_pos)
        if world_pos:
            preview_points = self.points + [world_pos]
            self._draw_preview(preview_points)

    def handle_key_press(self, key: str) -> bool:
        """Handles keyboard shortcuts specific to the drawing context."""
        if not self.is_active:
            return False

        if key == "escape":
            if self.state == "DRAWING":
                self._discard_curve(keep_active=True)
                if hasattr(self.base, "hud"):
                    self.base.hud.setText(
                        "Curve discarded. Right click to start a new one."
                    )
                return False
            else:
                self.set_enabled(False)
                return True
        elif key == "enter":
            self._commit_curve()
            return False
        return False

    def _draw_preview(self, points_to_draw=None):
        """Renders a temporary spline or polyline connecting the current points."""
        if self._current_preview_np is not None:
            self._current_preview_np.removeNode()
            self._current_preview_np = None

        pts = points_to_draw if points_to_draw is not None else self.points
        if len(pts) < 2:
            return

        lines = LineSegs()
        lines.setThickness(2.0)
        lines.setColor(0, 0.5, 1, 1)

        if len(pts) > 2:
            try:
                # Generate a smooth approximation for the preview
                smooth_pts = SplineModel.preview_evaluate(
                    type="bezier", degree=len(pts) - 1, control_points=pts, sample=30
                )
                if len(smooth_pts) > 0:
                    lines.moveTo(*smooth_pts[0])
                    for p in smooth_pts[1:]:
                        lines.drawTo(*p)
            except Exception():
                # Fallback to linear segments
                lines.moveTo(*pts[0])
                for p in pts[1:]:
                    lines.drawTo(*p)
        else:
            lines.moveTo(*pts[0])
            for p in pts[1:]:
                lines.drawTo(*p)

        self._current_preview_np = self.preview_node.attachNewNode(lines.create())

    def _commit_curve(self):
        """Validates the curve, sends it to the kernel via IPC, and readies the machine for the next curve."""
        if len(self.points) >= 2:
            payload = {
                "points": copy.deepcopy(self.points),
                "degree": len(self.points) - 1,
            }
            self.on_event_cb(ViewEventType.CREATE_SPLINE, payload)

            if hasattr(self.base, "hud"):
                self.base.hud.setText(
                    f"Curve created with {len(self.points)} points. Ready for next."
                )
        self._discard_curve(keep_active=True)

    def _discard_curve(self, keep_active=False):
        """Clears the current drawing state without exiting the tool completely."""
        self.points.clear()
        if self._current_preview_np is not None:
            self._current_preview_np.removeNode()
            self._current_preview_np = None

        if keep_active:
            self.state = "WAITING_FIRST_POINT"
        else:
            self.state = "IDLE"

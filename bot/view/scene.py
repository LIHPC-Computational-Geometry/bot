from typing import Any, dict, list

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    LColor,
    LineSegs,
    NodePath,
    Vec3,
    Vec4,
)

from bot.view.curve_app import CurveApp
from bot.viewer.contracts import ScenePayload
from bot.viewer.serialize import payload_to_geom_data

_DEFAULT_BOUNDS = {
    "min": [0, 0, 0],
    "max": [0, 0, 0],
    "center": [0, 0, 0],
    "size": [1, 1, 1],
}


class HUDGizmo:
    """
    Orientation indicator (Gizmo) displayed in a corner of the 3D view (pixel2d space).
    Displays the axes (X=red, Y=green).
    """

    def __init__(self, parent: NodePath):
        self.root = parent.attachNewNode("hud_gizmo_root")
        self.root.setPos(80, 0, -80)
        self.root.setScale(200)
        self._create_axes()

    def _create_axes(self):
        """Draws the colored axis segments."""
        ls = LineSegs()
        ls.setThickness(2.0)

        # X Axis (Red) and Y Axis (Green)
        for i, col in enumerate([(1, 0, 0), (0, 1, 0)]):
            ls.setColor(LColor(*col, 1))
            ls.moveTo(0, 0, 0)
            target = [0, 0, 0]
            target[i] = 0.1
            ls.drawTo(*target)

        self.root.attachNewNode(ls.create())

    def update(self, camera_quat):
        """Aligns the gizmo with the camera orientation."""
        self.root.setQuat(camera_quat)


class Scene:
    """
    Manages the Panda3D scene: geometry, lights, and the orientation gizmo.
    Delegates curve logic to CurveApp.
    """

    def __init__(self, base, geom_data: dict[str, Any], settings: dict[str, Any]):
        self.base = base
        self._geom_data = geom_data

        self.background_color: list[float] = settings.get(
            "background_color", [0.1, 0.1, 0.12]
        )
        self.base.set_background_color(self.background_color)

        self.line_thickness: float = float(settings.get("line_thickness", 2.0))
        self.curves: dict[str, CurveApp] = {}

        self.active_curve_tag: str | None = None
        self.edit_mode_enabled: bool = False
        self.axis_constraint_mask: int = 3

        self._constraint_guide_np: NodePath | None = None
        self._world_axes_np: NodePath | None = None
        self._transform_gizmo_np: NodePath | None = None
        self._constraint_guide_origin: list[float] | None = None
        self._constraint_guide_visible: bool = False
        self.last_units_per_pixel: float = 0.01

        # Scene root nodes
        self._constraint_guide_np = self.base.render.attachNewNode(
            "constraint_guide_root"
        )
        self._constraint_guide_np.hide()
        self._world_axes_np = self.base.render.attachNewNode("world_axes_root")
        self._transform_gizmo_np = self.base.render.attachNewNode(
            "transform_gizmo_root"
        )
        self._transform_gizmo_np.hide()

        self.geom_node = self._build_from_data(geom_data)
        self.gizmo = HUDGizmo(self.base.pixel2d)

        self.add_lighting()
        self.base.accept("zoom_changed", self._on_zoom_changed)

    @property
    def bounds(self) -> dict[str, Any]:
        """Returns the dimensions of the scene's bounding box."""
        return self._geom_data.get("bounds", _DEFAULT_BOUNDS)

    def _get_curve(self, tag: Any) -> CurveApp | None:
        """Safe utility to retrieve a curve by its namespaced tag."""
        if tag is None:
            return None
        return self.curves.get(str(tag))

    def _build_from_data(self, geom_data: dict[str, Any]) -> NodePath:
        """
        Builds the geometry tree from CAD data.
        """
        curves_data = geom_data.get("curves", {})
        self.curves.clear()

        # Instantiation of CurveApp objects
        for tag, curve_info in curves_data.items():
            self.curves[str(tag)] = CurveApp(str(tag), curve_info)

        geom_root = self.base.render.attachNewNode("geom_root")

        # Visual and physical initialization of the curves
        for tag, curve in self.curves.items():
            curve.update_collision_sizes(self.last_units_per_pixel)
            curve.line_thickness = self.line_thickness

            root_node = geom_root.attachNewNode(f"curve_{tag}")
            curve.attach_curve_node(root_node)

        if self.edit_mode_enabled and self.active_curve_tag is not None:
            self.set_active_curve(self.active_curve_tag)

        return geom_root

    def set_curve_color(self, tag: Any, color: list[float]):
        """Modifies the color of a curve."""
        curve = self._get_curve(tag)
        if curve is not None:
            curve.set_color(color)

    def set_cp_color(self, tag: Any, cp_index: int, color: list[float]):
        """Modifies the color of a specific control point."""
        curve = self._get_curve(tag)
        if curve is not None:
            curve.set_cp_color(cp_index, color)

    def set_edit_mode(self, enabled: bool):
        """Enables or disables global edit mode."""
        self.edit_mode_enabled = enabled
        if not enabled:
            self.active_curve_tag = None
            for curve in self.curves.values():
                curve.is_selected(False)

    def set_active_curve(self, tag: Any):
        """Sets the currently selected curve for editing."""
        normalized = str(tag) if tag is not None else None
        self.active_curve_tag = normalized
        for curve_tag, curve in self.curves.items():
            curve.is_selected(self.edit_mode_enabled and normalized == curve_tag)

    def preview_evaluate(self, tag: str, cp_index: int, new_pos: list[float]):
        """Previews the displacement of a control point in real-time."""
        curve = self._get_curve(tag)
        if curve is not None:
            curve.preview_evaluate(int(cp_index), new_pos)

        if self._constraint_guide_visible:
            self.update_axis_guide(new_pos, self.axis_constraint_mask)

    def set_axis_constraint(self, mask: int):
        self.axis_constraint_mask = max(0, min(7, int(mask)))
        if self._constraint_guide_visible and self._constraint_guide_origin is not None:
            self.update_axis_guide(
                self._constraint_guide_origin, self.axis_constraint_mask
            )

    # =========================================================================
    # VISUAL AXIS GUIDES MANAGEMENT (TRANSFORM GIZMO)
    # =========================================================================

    def _guide_length(self) -> float:
        size = self.bounds.get("size", [1, 1, 1])
        max_size = max(size) if size else 1.0
        return max(2.0, float(max_size) * 0.15)

    def _draw_axis_line(
        self, root: NodePath, origin: list[float], axis: str, length: float
    ):
        colors = {"x": (1, 0, 0, 0.2), "y": (0, 1, 0, 0.2), "z": (0, 0, 1, 0.2)}
        vectors = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}

        color = colors[axis]
        vx, vy, vz = vectors[axis]

        ls = LineSegs()
        ls.setThickness(2.0)
        ls.setColor(*color)

        ls.moveTo(
            origin[0] - vx * length, origin[1] - vy * length, origin[2] - vz * length
        )
        ls.drawTo(
            origin[0] + vx * length, origin[1] + vy * length, origin[2] + vz * length
        )

        root.attachNewNode(ls.create())

    def _update_transform_gizmo(self, origin: list[float], mask: int):
        if self._transform_gizmo_np is None:
            return

        self._transform_gizmo_np.getChildren().detach()
        length = self._guide_length()

        if mask & 1:
            self._draw_axis_line(self._transform_gizmo_np, origin, "x", length)
        if mask & 2:
            self._draw_axis_line(self._transform_gizmo_np, origin, "y", length)
        if mask & 4:
            self._draw_axis_line(self._transform_gizmo_np, origin, "z", length)

    def show_axis_guide(self, origin: list[float], mask: int):
        self._constraint_guide_visible = True
        self.update_axis_guide(origin, mask)
        self._constraint_guide_np.show()
        if self._transform_gizmo_np is not None:
            self._transform_gizmo_np.show()

    def update_axis_guide(self, origin: list[float], mask: int):
        if self._constraint_guide_np is None:
            return

        self._constraint_guide_origin = [origin[0], origin[1], origin[2]]
        self._constraint_guide_np.getChildren().detach()

        length = self._guide_length()
        if mask & 1:
            self._draw_axis_line(self._constraint_guide_np, origin, "x", length)
        if mask & 2:
            self._draw_axis_line(self._constraint_guide_np, origin, "y", length)
        if mask & 4:
            self._draw_axis_line(self._constraint_guide_np, origin, "z", length)

        self._update_transform_gizmo(origin, mask)

    def hide_axis_guide(self):
        self._constraint_guide_visible = False
        self._constraint_guide_origin = None

        for np in [self._constraint_guide_np, self._transform_gizmo_np]:
            if np is not None:
                np.getChildren().detach()
                np.hide()

    # =========================================================================
    # RELOADING AND LIFECYCLE
    # =========================================================================

    def rebuild(self, geom_data: dict[str, Any]):
        """Rebuilds the scene geometry with new data."""
        self._geom_data = geom_data
        if self.geom_node is not None:
            self.geom_node.removeNode()
        self.geom_node = self._build_from_data(geom_data)

    def apply_patch(self, payload: ScenePayload) -> None:
        """Apply incremental curve geometry updates from the parent process."""
        for tag, delta in payload.get("changed_curves", {}).items():
            curve = self._get_curve(tag)
            if curve is None:
                continue
            geometry = delta["geometry"]
            curve.apply_geometry_bytes(
                geometry["curve_vertices"], delta["vertex_count"]
            )
            cp_vertices = geometry.get("cp_vertices")
            if cp_vertices is not None and delta.get("cp_count"):
                curve.apply_control_vertices_bytes(cp_vertices, delta["cp_count"])

    def remove_curves(self, tags: list[str]) -> None:
        """Remove curves identified by namespaced tags."""
        for tag in tags:
            curve = self.curves.pop(str(tag), None)
            if curve is not None and curve.root_node is not None:
                curve.root_node.removeNode()

    def load_from_payload(self, payload: ScenePayload) -> None:
        """Load or rebuild the scene from a full add payload."""
        geom_data = payload_to_geom_data(payload)
        self.rebuild(geom_data)

    def clear(self):
        """Cleans up all scene nodes."""
        for attr in [
            "geom_node",
            "_constraint_guide_np",
            "_world_axes_np",
            "_transform_gizmo_np",
        ]:
            np = getattr(self, attr, None)
            if np is not None:
                np.removeNode()
                setattr(self, attr, None)

        if (
            hasattr(self, "gizmo")
            and self.gizmo is not None
            and hasattr(self.gizmo, "root")
        ):
            self.gizmo.root.removeNode()

    def apply_settings(self, settings: dict[str, Any]):
        """Allows hot-reloading certain parameters without rebuilding everything."""
        if "background_color" in settings:
            self.background_color = settings["background_color"]
            self.base.set_background_color(self.background_color)

        if "line_thickness" in settings:
            self.line_thickness = float(settings["line_thickness"])
            if self.geom_node is not None:
                self.geom_node.removeNode()
            self.geom_node = self._build_from_data(self._geom_data)

    def add_lighting(self):
        """Adds the default lighting configuration for the scene."""
        ambient = AmbientLight("ambientLight")
        ambient.setColor(Vec4(0.3, 0.3, 0.3, 1))

        directional = DirectionalLight("directionalLight")
        directional.setColor(Vec4(1, 1, 1, 1))
        directional.setDirection(Vec3(-1, -1, -1))

        self.base.render.setLight(self.base.render.attachNewNode(ambient))
        self.base.render.setLight(self.base.render.attachNewNode(directional))

    def _on_zoom_changed(self, film_size: float):
        """Updates the selection radius so it remains constant on the screen."""
        win_width = self.base.win.getXSize() or 1000
        self.last_units_per_pixel = film_size / win_width
        for curve in self.curves.values():
            curve.update_collision_sizes(self.last_units_per_pixel)

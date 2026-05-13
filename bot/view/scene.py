from panda3d.core import (
    LineSegs,
    NodePath,
    LColor,
    Vec4,
    Vec3,
    DirectionalLight,
    AmbientLight,
)
from panda3d.core import CollisionNode, CollisionTube

from bot.view.curve_app import CurveApp

_DEFAULT_BOUNDS = {
    "min": [0, 0, 0],
    "max": [0, 0, 0],
    "center": [0, 0, 0],
    "size": [1, 1, 1],
}


class HUDGizmo:
    """
    Orientation indicator displayed in a corner of the viewport (pixel2d space).

    Shows the three world axes (X=red, Y=green, Z=blue) and rotates to match
    the current camera orientation, giving the user a persistent sense of
    direction in the 3D view.
    """

    def __init__(self, parent):
        """
        Build the axis segments and attach them to *parent* (typically pixel2d).

        Args:
            parent: Panda3D NodePath to attach the gizmo to.
        """
        self.root = parent.attachNewNode("hud_gizmo_root")
        self.root.setPos(80, 0, -80)
        self.root.setScale(400)
        self._create_axes()

    def _create_axes(self):
        """Draw the three RGB axis segments."""
        ls = LineSegs()
        ls.setThickness(2)
        # for i, col in enumerate([(1, 0, 0), (0, 1, 0), (0, 0, 1)]):
        for i, col in enumerate([(1, 0, 0), (0, 1, 0)]):
            ls.setColor(LColor(*col, 1))
            ls.moveTo(0, 0, 0)
            target = [0, 0, 0]
            target[i] = 0.1
            ls.drawTo(*target)
        self.root.attachNewNode(ls.create())

    def update(self, camera_quat):
        """
        Rotate the gizmo to match the current camera orientation.

        Args:
            camera_quat: Quaternion of the camera relative to the render root.
        """
        self.root.setQuat(camera_quat)


class Scene:
    """
    Manages the Panda3D scene: geometry, lighting and the orientation gizmo.

    Geometry is built from a ``render_data`` dict produced by the CAD model::

        {'points': [(x,y,z), ...], 'edges': [(idxA, idxB, curve_tag), ...], 'bounds': {...}}

    Settings (background colour, line thickness) can be hot-reloaded via
    :meth:`apply_settings` without recreating the whole scene.
    """

    def __init__(self, base, geom_data: dict, settings: dict):
        """
        Build the scene from *geom_data* and apply *settings*.

        Args:
            base:      Panda3D ShowBase instance.
            geom_data: Render data dict from the CAD model.
            settings:  Scene configuration dict (background_color, line_thickness).
        """
        self.base = base
        self._geom_data = geom_data
        self.background_color = settings.get("background_color", [0.1, 0.1, 0.12])
        self.base.set_background_color(self.background_color)
        self.line_thickness = settings.get("line_thickness", 2)
        self.curves = {}
        self.active_curve_tag = None
        self.edit_mode_enabled = False
        self.axis_constraint_mask = 3
        self._constraint_guide_np = None
        self._world_axes_np = None
        self._transform_gizmo_np = None
        self._constraint_guide_origin = None
        self._constraint_guide_visible = False
        self.last_units_per_pixel = 0.01

        self.geom_node = self._build_from_data(geom_data)
        self._constraint_guide_np = self.base.render.attachNewNode(
            "constraint_guide_root"
        )
        self._constraint_guide_np.hide()
        self._world_axes_np = self.base.render.attachNewNode("world_axes_root")
        self._transform_gizmo_np = self.base.render.attachNewNode(
            "transform_gizmo_root"
        )
        self._transform_gizmo_np.hide()
        self.gizmo = HUDGizmo(self.base.pixel2d)
        self.add_lighting()

        self.base.accept("zoom_changed", self._on_zoom_changed)

    @property
    def bounds(self) -> dict:
        """Bounding-box data of the current geometry (center, size, min, max)."""
        return self._geom_data.get("bounds", _DEFAULT_BOUNDS)

    def _group_edges_by_tag(self, edges: list) -> dict:
        # NOTE: A curve is a liste of small edges. This function group all these edges for set the same color
        """Groups a list of edges by their curve tag."""
        edges_by_tag = {}
        for e in edges:
            idxA, idxB = e[0], e[1]
            tag = str(e[2]) if len(e) > 2 else "default"
            if tag not in edges_by_tag:
                edges_by_tag[tag] = []
            edges_by_tag[tag].append((idxA, idxB))
        return edges_by_tag

    def _create_curve_geometry(self, tag: str, tag_edges: list, points: list):
        """Creates the visible lines and invisible collision nodes for a set of edges."""
        lines = LineSegs()
        is_control_polygon = tag.endswith("_cp")

        if is_control_polygon:
            lines.setThickness(1.0)
            lines.setColor(0.5, 0.5, 0.5, 1)
        else:
            lines.setThickness(self.line_thickness)

        cnode = CollisionNode(f"col_{tag}")
        cnode.setFromCollideMask(0)

        for idxA, idxB in tag_edges:
            ptA = points[idxA]
            ptB = points[idxB]
            # NOTE: '*' pour décompresser la liste/tuple en 3 arguments (x, y, z) pour Panda3D
            lines.moveTo(*ptA)
            lines.drawTo(*ptB)

            if not is_control_polygon:
                # NOTE: Calcul de la distance au carré (plus rapide qu'une racine carrée)
                dx = ptA[0] - ptB[0]
                dy = ptA[1] - ptB[1]
                dz = ptA[2] - ptB[2]
                dist_sq = dx*dx + dy*dy + dz*dz

                # NOTE: Si les points sont distincts, on crée le tube
                if dist_sq > 1e-8:
                    radius = 1.0
                    tube = CollisionTube(
                        ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], radius
                    )
                    cnode.addSolid(tube)

        if is_control_polygon:
            unique_indices = dict.fromkeys(idx for edge in tag_edges for idx in edge)
            extremities = [points[idx] for idx in unique_indices]
        else:
            extremities = []

        return lines, cnode, is_control_polygon, extremities

    def _build_from_data(self, geom_data: dict):
        """
        Builds the 3D geometry and collision nodes from the CAD render data.

        This method groups the edges by their `curve_tag`. For each distinct curve, it:
        1. Generates the visible 3D line segments and stores the resulting
           NodePath in `self.curve_nodes` to allow dynamic highlighting.
        2. Generates an invisible CollisionTube around each segment, configured
           to receive raycasts (for mouse hovering and picking) without emitting them.

        Args:
            geom_data (dict): Render data dict containing 'points' and 'edges'.

        Returns:
            NodePath: The root node containing all visible and collision geometry,
                      attached to `render`. Returns `None` if there are no edges.
        """
        curves = geom_data.get("curves", [])

        self.curves = {}

        for tag, curve in curves.items():
            self.curves[int(tag)] = CurveApp(tag, curve)
        geom_root = self.base.render.attachNewNode("geom_root")

        for tag, curve in self.curves.items():
            curve.update_collision_sizes(self.last_units_per_pixel)
            curve.create_curve_geometry(self.line_thickness)
            node_path = geom_root.attachNewNode(f"curve_{tag}")
            curve.attachCuveNode(node_path)

        if self.edit_mode_enabled and self.active_curve_tag is not None:
            self.set_active_curve(self.active_curve_tag)
        return geom_root

    def set_curve_color(self, tag: str, color: list):
        """Change the color of a curve."""
        curve = None
        if tag in self.curves:
            curve = self.curves[tag]
        else:
            try:
                curve = self.curves.get(int(tag))
            except (TypeError, ValueError):
                curve = None

        if curve is not None:
            curve.set_color(color)

    def set_cp_color(self, tag: str, cp_index: int, color: list):
        curve = None
        if tag in self.curves:
            curve = self.curves[tag]
        else:
            try:
                curve = self.curves.get(int(tag))
            except (TypeError, ValueError):
                curve = None

        if curve is not None:
            curve.set_cp_color(cp_index, color)

    def set_edit_mode(self, enabled: bool):
        self.edit_mode_enabled = enabled
        if not enabled:
            self.active_curve_tag = None
            for curve in self.curves.values():
                curve.set_cp_visible(False)

    def set_active_curve(self, tag):
        try:
            normalized = int(tag) if tag is not None else None
        except (TypeError, ValueError):
            normalized = None
        self.active_curve_tag = normalized
        for curve_tag, curve in self.curves.items():
            curve.set_cp_visible(self.edit_mode_enabled and normalized == curve_tag)

    def preview_control_point(self, tag: int, cp_index: int, new_pos: list[float]):
        curve = self.curves.get(int(tag))
        if curve is not None:
            curve.preview_control_point(int(cp_index), new_pos)
        if self._constraint_guide_visible:
            self.update_axis_guide(new_pos, self.axis_constraint_mask)

    def set_axis_constraint(self, mask: int):
        self.axis_constraint_mask = max(0, min(7, int(mask)))
        if self._constraint_guide_visible and self._constraint_guide_origin is not None:
            self.update_axis_guide(
                self._constraint_guide_origin, self.axis_constraint_mask
            )

    def _guide_length(self) -> float:
        size = self.bounds.get("size", [1, 1, 1])
        max_size = max(size) if size else 1
        return max(2.0, float(max_size) * 0.15)

    def _world_axes_length(self) -> float:
        size = self.bounds.get("size", [1, 1, 1])
        max_size = max(size) if size else 1
        return max(1000.0, float(max_size) * 100.0)

    def _draw_axis_line(
        self, root: NodePath, origin: list[float], axis: str, length: float
    ):
        colors = {"x": (1, 0, 0, 0.2), "y": (0, 1, 0, 0.2), "z": (0, 0, 1, 0.2)}
        vectors = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}
        color = colors[axis]
        vx, vy, vz = vectors[axis]

        ls = LineSegs()
        ls.setThickness(2)
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
        if self._constraint_guide_np is not None:
            self._constraint_guide_np.getChildren().detach()
            self._constraint_guide_np.hide()
        if self._transform_gizmo_np is not None:
            self._transform_gizmo_np.getChildren().detach()
            self._transform_gizmo_np.hide()

    def rebuild(self, geom_data: dict):
        """Replace displayed geometry with new render data."""
        self._geom_data = geom_data
        if self.geom_node is not None:
            self.geom_node.removeNode()
        self.geom_node = self._build_from_data(geom_data)

    def clear(self):
        """Remove all geometry from the scene."""
        if self.geom_node is not None:
            self.geom_node.removeNode()
            self.geom_node = None
        if self._constraint_guide_np is not None:
            self._constraint_guide_np.removeNode()
            self._constraint_guide_np = None
        if self._world_axes_np is not None:
            self._world_axes_np.removeNode()
            self._world_axes_np = None
        if self._transform_gizmo_np is not None:
            self._transform_gizmo_np.removeNode()
            self._transform_gizmo_np = None
        if (
            hasattr(self, "gizmo")
            and self.gizmo is not None
            and hasattr(self.gizmo, "root")
        ):
            self.gizmo.root.removeNode()

    def apply_settings(self, settings: dict):
        """
        Hot-reload scene settings without recreating the whole scene.

        Supported keys: ``background_color``, ``line_thickness``.

        Args:
            settings: Partial or full scene configuration dict.
        """
        if "background_color" in settings:
            self.background_color = settings["background_color"]
            self.base.set_background_color(self.background_color)
        if "line_thickness" in settings:
            self.line_thickness = settings["line_thickness"]
            if self.geom_node is not None:
                self.geom_node.removeNode()
            self.geom_node = self._build_from_data(self._geom_data)

    def add_lighting(self):
        """Add a default ambient + directional light rig to the render root."""
        ambient = AmbientLight("ambientLight")
        ambient.setColor(Vec4(0.3, 0.3, 0.3, 1))
        directional = DirectionalLight("directionalLight")
        directional.setColor(Vec4(1, 1, 1, 1))
        directional.setDirection(Vec3(-1, -1, -1))

        self.base.render.setLight(self.base.render.attachNewNode(ambient))
        self.base.render.setLight(self.base.render.attachNewNode(directional))

    def _on_zoom_changed(self, film_size):
        """Met à jour le rayon de sélection pour qu'il reste constant à l'écran"""
        win_width = self.base.win.getXSize() or 1000
        self.last_units_per_pixel = film_size / win_width
        for curve in self.curves.values():
            curve.update_collision_sizes(self.last_units_per_pixel)
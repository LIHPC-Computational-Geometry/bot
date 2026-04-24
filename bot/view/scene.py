from panda3d.core import LineSegs, NodePath, LColor, Vec4, Vec3, DirectionalLight, AmbientLight
from panda3d.core import CollisionNode, CollisionTube
from panda3d.core import GeomVertexFormat, GeomVertexData, Geom, GeomPoints, GeomNode, GeomVertexWriter

from bot.view.curve_app import CurveApp

_DEFAULT_BOUNDS = {
    'min': [0, 0, 0], 'max': [0, 0, 0],
    'center': [0, 0, 0], 'size': [1, 1, 1],
}


class Gizmo:
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
        self.root = parent.attachNewNode("gizmo_root")
        self.root.setPos(80, 0, -80)
        self.root.setScale(400)
        self._create_axes()

    def _create_axes(self):
        """Draw the three RGB axis segments."""
        ls = LineSegs()
        ls.setThickness(2)
        for i, col in enumerate([(1, 0, 0), (0, 1, 0), (0, 0, 1)]):
            ls.setColor(LColor(*col, 1))
            ls.moveTo(0, 0, 0)
            target = [0, 0, 0]; target[i] = 0.1
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
        self.background_color = settings.get('background_color', [0.1, 0.1, 0.12])
        self.base.set_background_color(self.background_color)
        self.line_thickness = settings.get('line_thickness', 2)
        self.curves = {}
        self.active_curve_tag = None
        self.edit_mode_enabled = False

        self.geom_node = self._build_from_data(geom_data)
        self.gizmo = Gizmo(self.base.pixel2d)
        self.add_lighting()

    @property
    def bounds(self) -> dict:
        """Bounding-box data of the current geometry (center, size, min, max)."""
        return self._geom_data.get('bounds', _DEFAULT_BOUNDS)

    def _group_edges_by_tag(self, edges: list) -> dict:
        # NOTE: A curve is a liste of small edges. This function group all these edges for set the same color
        """Groups a list of edges by their curve tag.
        """
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
        is_control_polygon = tag.endswith('_cp')

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
                radius = 1.0
                tube = CollisionTube(ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], radius)
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
        curves = geom_data.get('curves', [])

        self.curves = {}

        for tag, curve in curves.items():
            self.curves[int(tag)] = CurveApp(tag, curve)
        geom_root = self.base.render.attachNewNode("geom_root")

        for tag, curve in self.curves.items():
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

    def apply_settings(self, settings: dict):
        """
        Hot-reload scene settings without recreating the whole scene.

        Supported keys: ``background_color``, ``line_thickness``.

        Args:
            settings: Partial or full scene configuration dict.
        """
        if 'background_color' in settings:
            self.background_color = settings['background_color']
            self.base.set_background_color(self.background_color)
        if 'line_thickness' in settings:
            self.line_thickness = settings['line_thickness']
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

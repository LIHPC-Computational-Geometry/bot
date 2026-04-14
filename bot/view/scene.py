from panda3d.core import LineSegs, NodePath, LColor, Vec4, Vec3, DirectionalLight, AmbientLight
from panda3d.core import CollisionNode, CollisionTube

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

        self.geom_node = self._build_from_data(geom_data)
        self.gizmo = Gizmo(self.base.pixel2d)
        self.add_lighting()

    @property
    def bounds(self) -> dict:
        """Bounding-box data of the current geometry (center, size, min, max)."""
        return self._geom_data.get('bounds', _DEFAULT_BOUNDS)

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
        points = geom_data.get('points', [])
        edges = geom_data.get('edges', [])
        if not edges:
            return None

        self.curve_nodes = {}
        geom_root = self.base.render.attachNewNode("geom_root")

        edges_by_tag = {}
        for e in edges:
            idxA, idxB = e[0], e[1]
            tag = str(e[2]) if len(e) > 2 else "default"
            if tag not in edges_by_tag:
                edges_by_tag[tag] = []
            edges_by_tag[tag].append((idxA, idxB))

        for tag, tag_edges in edges_by_tag.items():
            lines = LineSegs()
            lines.setThickness(self.line_thickness)

            cnode = CollisionNode(f"col_{tag}")

            cnode.setFromCollideMask(0)

            for idxA, idxB in tag_edges:
                ptA = points[idxA]
                ptB = points[idxB]
                lines.moveTo(ptA)
                lines.drawTo(ptB)

                radius = 1.0
                tube = CollisionTube(ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], radius)
                cnode.addSolid(tube)

            node_path = geom_root.attachNewNode(lines.create())
            self.curve_nodes[tag] = node_path

            cnp = node_path.attachNewNode(cnode)
            cnp.setTag('curve_tag', tag)

        return geom_root

    def set_curve_color(self, tag: str, color: list):
        """Change the color of a curve."""
        tag_str = str(tag)
        if tag_str in self.curve_nodes:
            node = self.curve_nodes[tag_str]
            node.setColor(color[0], color[1], color[2], color[3], 1)
            node.setLightOff(1)


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

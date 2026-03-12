from panda3d.core import LineSegs, NodePath, LColor, Vec4, Vec3, DirectionalLight, AmbientLight

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
        Tessellate *geom_data* into a Panda3D LineSegs node.

        Returns:
            NodePath attached to ``render``, or ``None`` if there are no edges.
        """
        points = geom_data.get('points', [])
        edges = geom_data.get('edges', [])
        if not edges:
            return None
        lines = LineSegs()
        lines.setThickness(self.line_thickness)
        for e in edges:
            lines.moveTo(points[e[0]])
            lines.drawTo(points[e[1]])
        return self.base.render.attachNewNode(lines.create())

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

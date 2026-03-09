from panda3d.core import LineSegs, NodePath, LColor, Vec4, Vec3, DirectionalLight, AmbientLight, Geom, GeomNode
import colorsys

_DEFAULT_BOUNDS = {
    'min': [0, 0, 0], 'max': [0, 0, 0],
    'center': [0, 0, 0], 'size': [1, 1, 1],
}

class ColorGenerator:
    @staticmethod
    def generate_distinct_colors(n):
        """
        Generate n visually distinct RGB colors using HSV spacing.

        Args:
            n (int): Number of colors to generate.

        Returns:
            List of (r, g, b) tuples in [0, 1]
        """
        return [colorsys.hsv_to_rgb(i / n, 0.65, 1.0) for i in range(n)]

class Gizmo:
    def __init__(self, parent):
        self.root = parent.attachNewNode("gizmo_root")
        self.root.setPos(80, 0, -80)
        self.root.setScale(400)
        self._create_axes()

    def _create_axes(self):
        ls = LineSegs()
        ls.setThickness(2)
        for i, col in enumerate([(1,0,0), (0,1,0), (0,0,1)]):
            ls.setColor(LColor(*col, 1))
            ls.moveTo(0,0,0)
            target = [0,0,0]; target[i] = 0.1
            ls.drawTo(*target)
        self.root.attachNewNode(ls.create())

    def update(self, camera_quat):
        self.root.setQuat(camera_quat)


class Scene:
    def __init__(self, base, geom_data: dict, settings: dict):
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
        return self._geom_data.get('bounds', _DEFAULT_BOUNDS)

    def _build_from_data(self, geom_data: dict):
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
        """Update the modifiable settings of the scene."""
        if 'background_color' in settings:
            self.background_color = settings['background_color']
            self.base.set_background_color(self.background_color)
        if 'line_thickness' in settings:
            self.line_thickness = settings['line_thickness']
            if self.geom_node is not None:
                self.geom_node.removeNode()
            self.geom_node = self._build_from_data(self._geom_data)
         
    
    def add_lighting(self):
        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor(Vec4(0.3, 0.3, 0.3, 1))
        directionalLight = DirectionalLight("directionalLight")
        directionalLight.setColor(Vec4(1, 1, 1, 1))
        directionalLight.setDirection(Vec3(-1, -1, -1))

        self.base.render.setLight(self.base.render.attachNewNode(ambientLight))
        self.base.render.setLight(self.base.render.attachNewNode(directionalLight))

from panda3d.core import LineSegs, NodePath, LColor, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomLines, Geom, GeomNode
from core.cad import Model as CADModel
import colorsys

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


class BotView:
    def __init__(self, base, model : CADModel):
        self.base = base
        self.model = model
        self.geom_node = self._build_model()
        self.gizmo = Gizmo(self.base.pixel2d)

    def _build_model(self):
        format = GeomVertexFormat.getV3()
        vdata = GeomVertexData('data', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        points, edges = self.model.get_curve_discretization()

        for p in points: vertex.addData3(*p)
        
        lines = GeomLines(Geom.UHStatic)
        for e in edges: lines.addVertices(e[0], e[1])
        
        geom = Geom(vdata)
        geom.addPrimitive(lines)
        node = GeomNode('model_node')
        node.addGeom(geom)
        np = self.base.render.attachNewNode(node)
        np.setRenderModeThickness(2)
        return np
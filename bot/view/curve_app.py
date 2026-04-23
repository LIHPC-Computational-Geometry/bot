from panda3d.core import LineSegs, NodePath, LColor, Vec4, Vec3, DirectionalLight, AmbientLight
from panda3d.core import CollisionNode, CollisionTube
from panda3d.core import GeomVertexFormat, GeomVertexData, Geom, GeomPoints, GeomNode, GeomVertexWriter

class CurveApp:
    def __init__(self, tag: str, curve_data: dict):
        self.tag: int = int(tag)
        self.edges: list = curve_data['edges']
        self.points: list = curve_data['points']
        self.type: str = curve_data['type']

        self.node_path: NodePath | None = None
        self.cp_node: NodePath | None = None
        self.control_points: list | None = None
        self.degree: int | None = None
        self.knots: list | None = None

        if self.type == 'bezier' or self.type == 'bspline':
            self.control_points = curve_data['control_points']
            self.degree = curve_data['degree']

        if self.type == 'bspline':
            self.knots = curve_data['knots']


    def _draw_control_points(self, node_path: NodePath):
        format = GeomVertexFormat.getV3()
        # NOTE: correspond à l'espace mémoire utilisé pour stocker les points 3D
        vdata = GeomVertexData('anchors', format, Geom.UHDynamic)
        # NOTE: permet d'écrire dans l'espace mémoire vdata dans la 'colonne' nommé 'vertex'
        vertex = GeomVertexWriter(vdata, 'vertex')
        # NOTE: Permet de dire au GPU de traiter les coordonnée en tant que point flottant (on pourrait très bien utiliser GeomTriangles(Geom.UHDynamic) pour dessiner des surffaces)
        prim = GeomPoints(Geom.UHDynamic)

        for i, pt in enumerate(self.control_points):
            vertex.addData3f(*pt)
            prim.addVertex(i)

        prim.closePrimitive()
        # NOTE: relie les données vdata avec les instructions à respecter sur ces données
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        # NOTE: Emballe le Geom pour être lisible par le moteur 3D
        gnode = GeomNode(f'anchors_{self.tag}')
        gnode.addGeom(geom)

        pts_np = node_path.attachNewNode(gnode)
        pts_np.setRenderModeThickness(10)

        # Draw connecting segments
        lines = LineSegs()
        lines.setThickness(1)
        for i, pt in enumerate(self.control_points):
            if i == 0:
                lines.moveTo(*pt)
            else:
                lines.drawTo(*pt)
        node_path.attachNewNode(lines.create())


    def _attachCPNode(self):
        self.cp_node = self.node_path.attachNewNode("cp_node")
        self._draw_control_points(self.cp_node)
        self.cp_node.setColor(0.5, 0.5, 0.5, 1, 1)
        self.cp_node.setLightOff(1)
        self.cp_node.hide()
        return self.cp_node


    def _create_collision(self, cnode: NodePath):
        for idxA, idxB in self.edges:
            ptA = self.points[idxA]
            ptB = self.points[idxB]
            radius = 1.0
            tube = CollisionTube(ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], radius)
            cnode.addSolid(tube)


    def _attachColissionNode(self):
        cnode = CollisionNode(f"col_{self.tag}")
        cnode.setFromCollideMask(0)
        self._create_collision(cnode)
        cnp = self.node_path.attachNewNode(cnode)
        cnp.setTag('curve_tag', str(self.tag))
        return cnp


    def attachCuveNode(self, node_path: NodePath):
        self.node_path = node_path
        self.node_path.setTag('curve_tag', str(self.tag))
        self._attachColissionNode()
        if self.control_points is not None:
            self._attachCPNode()
        return self.node_path


    def set_color(self, color: list):
        self.node_path.setColor(color[0], color[1], color[2], color[3], 1)
        self.node_path.setLightOff(1)
        if self.cp_node is not None:
            if color[:3] == [1.0, 1.0, 1.0]:
                self.cp_node.hide()
            else:
                self.cp_node.show()


    def draw_curve(self, lines: LineSegs):
        for idxA, idxB in self.edges:
            ptA = self.points[idxA]
            ptB = self.points[idxB]
            # NOTE: '*' pour décompresser la liste/tuple en 3 arguments (x, y, z) pour Panda3D
            lines.moveTo(*ptA)
            lines.drawTo(*ptB)

    def create_curve_geometry(self, line_thickness: str):
        lines = LineSegs()
        lines.setThickness(int(line_thickness))
        self.draw_curve(lines)
        return lines




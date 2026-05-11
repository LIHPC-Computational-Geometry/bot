from panda3d.core import BitMask32, CollisionNode, CollisionSphere, CollisionTube
from panda3d.core import (
    Geom,
    GeomNode,
    GeomPoints,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
)
from panda3d.core import LineSegs, NodePath

import nurbslib
import numpy as np


# NOTE: Un mask permet de filtrer les objet que l'on veux collisionner
MASK_CURVE_PICK = BitMask32.bit(1)
MASK_CP_PICK = BitMask32.bit(2)


class CurveApp:
    def __init__(self, tag: str, curve_data: dict):
        self.tag: int = int(tag)
        self.edges: list = curve_data["edges"]
        self.points: list = curve_data["points"]
        self.type: str = curve_data["type"]

        self.node_path: NodePath | None = None
        self.curve_render_node: NodePath | None = None
        self.curve_collision_node: NodePath | None = None
        self.cp_render_node: NodePath | None = None
        self.cp_collision_node: NodePath | None = None
        self.cp_node: NodePath | None = None
        self._curve_geom_node: NodePath | None = None
        self._cp_geom_node: NodePath | None = None
        self._cp_line_node: NodePath | None = None
        self.control_points: list | None = None
        self.degree: int | None = None
        self.knots: list | None = None
        self.cp_visible = False
        self.line_thickness = 2
        self.cp_color: list | None = None

        if self.type == "bezier" or self.type == "bspline":
            self.control_points = curve_data["control_points"]
            self.cp_color = [
                [0.5, 0.5, 0.5, 1] for _ in range(len(self.control_points))
            ]
            self.degree = curve_data["degree"]

        # TODO: bspline / nurbs not already implemented
        if self.type == "bspline":
            self.knots = curve_data["knots"]

    def _draw_control_points(self, node_path: NodePath):
        format = GeomVertexFormat.getV3cp()
        # NOTE: correspond à l'espace mémoire utilisé pour stocker les points 3D
        vdata = GeomVertexData("anchors", format, Geom.UHDynamic)
        # NOTE: permet d'écrire dans l'espace mémoire vdata dans la 'colonne' nommé 'vertex'
        vertex = GeomVertexWriter(vdata, "vertex")
        color_writer = GeomVertexWriter(vdata, "color")

        # NOTE: Permet de dire au GPU de traiter les coordonnée en tant que point flottant (on pourrait très bien utiliser GeomTriangles(Geom.UHDynamic) pour dessiner des surffaces)
        prim = GeomPoints(Geom.UHDynamic)

        for i, pt in enumerate(self.control_points):
            vertex.addData3f(*pt)
            color_writer.addData4f(*self.cp_color[i])
            prim.addVertex(i)

        prim.closePrimitive()
        # NOTE: relie les données vdata avec les instructions à respecter sur ces données
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        # NOTE: Emballe le Geom pour être lisible par le moteur 3D
        gnode = GeomNode(f"anchors_{self.tag}")
        gnode.addGeom(geom)

        if self._cp_geom_node is not None:
            self._cp_geom_node.removeNode()
        self._cp_geom_node = node_path.attachNewNode(gnode)
        self._cp_geom_node.setRenderModeThickness(10)

        # Draw connecting segments
        lines = LineSegs()
        lines.setThickness(1)
        for i, pt in enumerate(self.control_points):
            if i == 0:
                lines.moveTo(*pt)
            else:
                lines.drawTo(*pt)
        if self._cp_line_node is not None:
            self._cp_line_node.removeNode()
        self._cp_line_node = node_path.attachNewNode(lines.create())

    def _attachCPNode(self):
        self.cp_render_node = self.node_path.attachNewNode("cp_render")
        self.cp_collision_node = self.node_path.attachNewNode("cp_collision")
        self.cp_collision_node.setCollideMask(MASK_CP_PICK)

        self.cp_node = self.cp_render_node
        self._draw_control_points(self.cp_render_node)
        self._rebuild_cp_collision()
        self.cp_node.setLightOff(1)
        self.cp_node.hide()
        return self.cp_node

    def _rebuild_cp_collision(self):
        if self.cp_collision_node is None or self.control_points is None:
            return

        self.cp_collision_node.getChildren().detach()
        for i, pt in enumerate(self.control_points):
            cnode = CollisionNode(f"cp_{self.tag}_{i}")
            cnode.setIntoCollideMask(MASK_CP_PICK)
            cnode.setFromCollideMask(BitMask32.allOff())
            cnode.addSolid(CollisionSphere(pt[0], pt[1], pt[2], 1.2))
            cnp = self.cp_collision_node.attachNewNode(cnode)
            cnp.setTag("curve_tag", str(self.tag))
            cnp.setTag("cp_index", str(i))
            cnp.setTag("pick_kind", "cp")

    def _create_collision(self, cnode: NodePath):
        for idxA, idxB in self.edges:
            ptA = self.points[idxA]
            ptB = self.points[idxB]
            radius = 0.4
            tube = CollisionTube(ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], radius)
            cnode.addSolid(tube)

    def _attachColissionNode(self):
        cnode = CollisionNode(f"col_{self.tag}")
        cnode.setFromCollideMask(BitMask32.allOff())
        cnode.setIntoCollideMask(MASK_CURVE_PICK)
        self._create_collision(cnode)
        if self.curve_collision_node is not None:
            self.curve_collision_node.removeNode()
        self.curve_collision_node = self.node_path.attachNewNode("curve_collision")
        cnp = self.curve_collision_node.attachNewNode(cnode)
        cnp.setTag("curve_tag", str(self.tag))
        cnp.setTag("pick_kind", "curve")
        return cnp

    def _draw_curve(self):
        lines = LineSegs()
        lines.setThickness(float(self.line_thickness))
        self.draw_curve(lines)
        if self._curve_geom_node is not None:
            self._curve_geom_node.removeNode()
        self._curve_geom_node = self.curve_render_node.attachNewNode(lines.create())

    def attachCuveNode(self, node_path: NodePath):
        self.node_path = node_path
        self.node_path.setTag("curve_tag", str(self.tag))
        self.curve_render_node = self.node_path.attachNewNode("curve_render")
        self._draw_curve()
        self._attachColissionNode()
        if self.control_points is not None:
            self._attachCPNode()
        return self.node_path

    def set_cp_color(self, cp_index: int, color: list):
        self.cp_color[cp_index] = color
        if self.cp_node is not None:
            self._draw_control_points(self.cp_node)

    def set_color(self, color: list):
        self.curve_render_node.setColor(color[0], color[1], color[2], color[3], 1)
        self.curve_render_node.setLightOff(1)
        if self.cp_node is not None:
            if self.cp_visible:
                self.cp_node.show()
            else:
                self.cp_node.hide()

    def draw_curve(self, lines: LineSegs):
        for idxA, idxB in self.edges:
            ptA = self.points[idxA]
            ptB = self.points[idxB]
            lines.moveTo(*ptA)
            lines.drawTo(*ptB)

    def create_curve_geometry(self, line_thickness: str):
        self.line_thickness = int(line_thickness)
        return None

    def set_cp_visible(self, visible: bool):
        self.cp_visible = visible
        if self.cp_node is None:
            return
        if visible:
            self.cp_node.show()
        else:
            self.cp_node.hide()

    def preview_control_point(self, cp_index: int, new_pos: list[float]):
        if self.control_points is None:
            return
        if cp_index < 0 or cp_index >= len(self.control_points):
            return

        self.control_points[cp_index] = [new_pos[0], new_pos[1], new_pos[2]]

        if self.type == "bezier" and self.degree is not None:
            cp_array = np.array(self.control_points, dtype=np.float64)
            engine = nurbslib.PyBezierCurve(int(self.degree), cp_array, None)

            pts = engine.evaluate(100, False)
            if len(pts.shape) == 2 and pts.shape[0] in (2, 3) and pts.shape[1] > 3:
                pts = pts.T

            self.points = pts.tolist()
            self.edges = [(i, i + 1) for i in range(len(self.points) - 1)]

        if self.curve_render_node is not None:
            self._draw_curve()
        if self.cp_render_node is not None:
            self._draw_control_points(self.cp_render_node)
        self._attachColissionNode()
        self._rebuild_cp_collision()

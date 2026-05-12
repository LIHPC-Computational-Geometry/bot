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

    def _attachColissionNode(self):
        # NETTOYAGE ABSOLU : On détruit l'ancien noeud et tous ses enfants
        if getattr(self, "curve_collision_node", None) is not None:
            self.curve_collision_node.removeNode()

        self.curve_collision_node = self.node_path.attachNewNode("curve_collision")

        cnode = CollisionNode(f"col_{self.tag}")
        cnode.setFromCollideMask(BitMask32.allOff())
        cnode.setIntoCollideMask(MASK_CURVE_PICK)

        radius = getattr(self, 'curve_pick_radius', 0.2)
        self._create_collision(cnode, radius)

        cnp = self.curve_collision_node.attachNewNode(cnode)
        cnp.setTag("curve_tag", str(self.tag))
        cnp.setTag("pick_kind", "curve")
        cnp.show()
        return cnp

    def _rebuild_cp_collision(self):
        if self.control_points is None or getattr(self, "node_path", None) is None:
            return

        # NETTOYAGE ABSOLU pour les points de contrôle
        if getattr(self, "cp_collision_node", None) is not None:
            self.cp_collision_node.removeNode()

        self.cp_collision_node = self.node_path.attachNewNode("cp_collision")

        radius = getattr(self, 'cp_pick_radius', 0.4)
        current_mask = MASK_CP_PICK if self.cp_visible else BitMask32.allOff()

        for i, pt in enumerate(self.control_points):
            cnode = CollisionNode(f"cp_{self.tag}_{i}")
            cnode.setIntoCollideMask(current_mask)
            cnode.setFromCollideMask(BitMask32.allOff())
            cnode.addSolid(CollisionSphere(pt[0], pt[1], pt[2], radius))
            cnp = self.cp_collision_node.attachNewNode(cnode)
            cnp.setTag("curve_tag", str(self.tag))
            cnp.setTag("cp_index", str(i))
            cnp.setTag("pick_kind", "cp")
            cnp.show()

    def _create_collision(self, cnode: CollisionNode, radius=0.4):
        for idxA, idxB in self.edges:
            ptA = self.points[idxA]
            ptB = self.points[idxB]

            # SÉCURITÉ PANDA3D MAXIMALE :
            # Empêche la division par zéro et l'apparition des Hitboxes Infinies.
            dist_sq = (ptA[0]-ptB[0])**2 + (ptA[1]-ptB[1])**2 + (ptA[2]-ptB[2])**2
            if dist_sq < 1e-5:
                # Si le segment est microscopique, on ne lui donne pas de hitbox.
                continue

            tube = CollisionTube(ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], radius)
            cnode.addSolid(tube)

    def _draw_curve(self):
        lines = LineSegs()
        lines.setThickness(float(self.line_thickness))
        self.draw_curve(lines)
        if self._curve_geom_node is not None:
            self._curve_geom_node.removeNode()
        self._curve_geom_node = self.curve_render_node.attachNewNode(lines.create())

    def attachCuveNode(self, node_path: NodePath):
        if self.curve_render_node: self.curve_render_node.removeNode()
        if self.curve_collision_node: self.curve_collision_node.removeNode()
        if self.cp_render_node: self.cp_render_node.removeNode()
        if self.cp_collision_node: self.cp_collision_node.removeNode()
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

        # SÉCURITÉ : On désactive physiquement les clics sur les points masqués
        if self.cp_collision_node is not None:
            current_mask = MASK_CP_PICK if visible else BitMask32.allOff()
            for cnp in self.cp_collision_node.getChildren():
                cnp.node().setIntoCollideMask(current_mask)
                cnp.setCollideMask(current_mask) # Force la MAJ Panda3D

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


    def update_collision_sizes(self, units_per_pixel: float):
        self.curve_pick_radius = units_per_pixel * 6.0
        self.cp_pick_radius = units_per_pixel * 12.0

        # Le détachement/rattachement est la seule façon de garantir que
        # le CollisionTraverser mette à jour son arbre de recherche global.
        if self.node_path is not None:
            self._attachColissionNode()
            self._rebuild_cp_collision()
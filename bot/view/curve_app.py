from typing import Dict, List, Optional
from panda3d.core import (
    BitMask32,
    CollisionNode,
    CollisionSphere,
    CollisionTube,
    Geom,
    GeomNode,
    GeomPoints,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
    NodePath,
)
import numpy as np
from bot.core.rust_block import SplineModel

MASK_CURVE_PICK = BitMask32.bit(1)
MASK_CP_PICK = BitMask32.bit(2)


class CurveApp:
    """
    Represents a 3D curve (visual and physical) manipulable in the editor.
    """

    def __init__(self, tag: str, curve_data: Dict):
        self.tag: int = int(tag)
        self.edges: List = curve_data["edges"]
        self.points: List = curve_data["points"]
        self.type: str = curve_data["type"]

        self.node_path: Optional[NodePath] = None
        self.curve_render_node: Optional[NodePath] = None
        self.curve_collision_node: Optional[NodePath] = None

        self.cp_render_node: Optional[NodePath] = None
        self.cp_collision_node: Optional[NodePath] = None
        self.cp_node: Optional[NodePath] = None

        self._curve_geom_node: Optional[NodePath] = None
        self._cp_geom_node: Optional[NodePath] = None
        self._cp_line_node: Optional[NodePath] = None

        self.control_points: Optional[List] = None
        self.degree: Optional[int] = None
        self.knots: Optional[List] = None

        self.cp_visible: bool = False
        self.line_thickness: float = 2.0
        self.cp_color: Optional[List[List[float]]] = None

        self.curve_pick_radius: float = 0.2
        self.cp_pick_radius: float = 0.4

        if self.type in ("bezier", "bspline"):
            self.control_points = curve_data.get("control_points", [])
            self.cp_color = [
                [0.5, 0.5, 0.5, 1.0] for _ in range(len(self.control_points))
            ]
            self.degree = curve_data.get("degree")

        if self.type == "bspline":
            self.knots = curve_data.get("knots")

    # =========================================================================
    # VISUAL PART (RENDERING)
    # =========================================================================

    def _draw_control_points(self, parent_node: NodePath):
        """Generates the visual geometry for control points and their connections."""
        format = GeomVertexFormat.getV3cp()
        vdata = GeomVertexData("anchors", format, Geom.UHDynamic)
        vertex_writer = GeomVertexWriter(vdata, "vertex")
        color_writer = GeomVertexWriter(vdata, "color")
        prim = GeomPoints(Geom.UHDynamic)

        for i, pt in enumerate(self.control_points):
            vertex_writer.addData3f(*pt)
            color_writer.addData4f(*self.cp_color[i])
            prim.addVertex(i)

        prim.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(prim)

        gnode = GeomNode(f"anchors_{self.tag}")
        gnode.addGeom(geom)

        if self._cp_geom_node is not None:
            self._cp_geom_node.removeNode()
        self._cp_geom_node = parent_node.attachNewNode(gnode)
        self._cp_geom_node.setRenderModeThickness(10)

        # Drawing connections (segments)
        lines = LineSegs()
        lines.setThickness(1)
        for i, pt in enumerate(self.control_points):
            if i == 0:
                lines.moveTo(*pt)
            else:
                lines.drawTo(*pt)

        if self._cp_line_node is not None:
            self._cp_line_node.removeNode()
        self._cp_line_node = parent_node.attachNewNode(lines.create())

    def _draw_curve(self):
        """Generates the main visual line of the curve."""
        lines = LineSegs()
        lines.setThickness(float(self.line_thickness))

        for idxA, idxB in self.edges:
            lines.moveTo(*self.points[idxA])
            lines.drawTo(*self.points[idxB])

        if self._curve_geom_node is not None:
            self._curve_geom_node.removeNode()
        self._curve_geom_node = self.curve_render_node.attachNewNode(lines.create())

    # =========================================================================
    # PHYSICAL PART (COLLISIONS)
    # =========================================================================

    def attach_collision_node(self) -> NodePath:
        """Attaches collision volumes for the main curve."""
        if self.curve_collision_node is not None:
            self.curve_collision_node.removeNode()

        self.curve_collision_node = self.node_path.attachNewNode("curve_collision")
        cnode = CollisionNode(f"col_{self.tag}")
        cnode.setFromCollideMask(BitMask32.allOff())
        cnode.setIntoCollideMask(MASK_CURVE_PICK)

        self._populate_curve_collision_solids(cnode)

        cnp = self.curve_collision_node.attachNewNode(cnode)
        cnp.setTag("curve_tag", str(self.tag))
        cnp.setTag("pick_kind", "curve")
        return cnp

    def _populate_curve_collision_solids(self, cnode: CollisionNode):
        """Generates collision tubes for the curve edges."""
        for idxA, idxB in self.edges:
            ptA, ptB = self.points[idxA], self.points[idxB]
            dist_sq = sum((ptA[i] - ptB[i]) ** 2 for i in range(3))

            # Avoids division by zero and infinite hitboxes
            if dist_sq < 1e-5:
                continue

            tube = CollisionTube(
                ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], self.curve_pick_radius
            )
            cnode.addSolid(tube)

    def rebuild_cp_collision(self):
        """Rebuilds the collision spheres for the control points."""
        if self.control_points is None or self.node_path is None:
            return

        if self.cp_collision_node is not None:
            self.cp_collision_node.removeNode()

        self.cp_collision_node = self.node_path.attachNewNode("cp_collision")
        current_mask = MASK_CP_PICK if self.cp_visible else BitMask32.allOff()

        for i, pt in enumerate(self.control_points):
            cnode = CollisionNode(f"cp_{self.tag}_{i}")
            cnode.setIntoCollideMask(current_mask)
            cnode.setFromCollideMask(BitMask32.allOff())
            cnode.addSolid(CollisionSphere(pt[0], pt[1], pt[2], self.cp_pick_radius))

            cnp = self.cp_collision_node.attachNewNode(cnode)
            cnp.setTag("curve_tag", str(self.tag))
            cnp.setTag("cp_index", str(i))
            cnp.setTag("pick_kind", "cp")

    # =========================================================================
    # PARENT NODE MANAGEMENT AND UTILITIES
    # =========================================================================

    def attach_curve_node(self, node_path: NodePath) -> NodePath:
        """Fully initializes the visual and physical hierarchy of the curve."""
        self._clean_nodes()
        self.node_path = node_path
        self.node_path.setTag("curve_tag", str(self.tag))

        self.curve_render_node = self.node_path.attachNewNode("curve_render")
        self._draw_curve()
        self.attach_collision_node()

        if self.control_points is not None:
            self._attach_cp_node()

        return self.node_path

    def _attach_cp_node(self) -> NodePath:
        """Initializes the parent node for the control points."""
        self.cp_render_node = self.node_path.attachNewNode("cp_render")
        self.cp_node = self.cp_render_node
        self._draw_control_points(self.cp_render_node)
        self.rebuild_cp_collision()

        self.cp_node.setLightOff(1)
        self.cp_node.hide()
        return self.cp_node

    def _clean_nodes(self):
        """Cleans up all existing nodes before reinitialization."""
        if self.curve_render_node:
            self.curve_render_node.removeNode()
        if self.curve_collision_node:
            self.curve_collision_node.removeNode()
        if self.cp_render_node:
            self.cp_render_node.removeNode()
        if self.cp_collision_node:
            self.cp_collision_node.removeNode()

    def set_cp_color(self, cp_index: int, color: List[float]):
        self.cp_color[cp_index] = color
        if self.cp_node is not None:
            self._draw_control_points(self.cp_node)

    def set_color(self, color: List[float]):
        if self.curve_render_node:
            self.curve_render_node.setColor(*color[:4], 1)
            self.curve_render_node.setLightOff(1)

        if self.cp_node is not None:
            self.cp_node.show() if self.cp_visible else self.cp_node.hide()

    def set_cp_visible(self, visible: bool):
        self.cp_visible = visible
        if self.cp_node is None:
            return

        self.cp_node.show() if visible else self.cp_node.hide()

        if self.cp_collision_node is not None:
            current_mask = MASK_CP_PICK if visible else BitMask32.allOff()
            for cnp in self.cp_collision_node.getChildren():
                cnp.node().setIntoCollideMask(current_mask)
                cnp.setCollideMask(current_mask)

    def preview_control_point(self, cp_index: int, new_pos: List[float]):
        if not self.control_points or not (0 <= cp_index < len(self.control_points)):
            return

        self.control_points[cp_index] = [new_pos[0], new_pos[1], new_pos[2]]

        if self.type == "bezier" and self.degree is not None:
            engine = SplineModel(str(self.tag), self.control_points, int(self.degree))
            pts = np.array(engine.get_render_data()["curve"], dtype=np.float64)
            if len(pts.shape) == 2 and pts.shape[0] in (2, 3) and pts.shape[1] > 3:
                pts = pts.T

            self.points = pts.tolist()
            self.edges = [(i, i + 1) for i in range(len(self.points) - 1)]

        if self.curve_render_node:
            self._draw_curve()
        if self.cp_render_node:
            self._draw_control_points(self.cp_render_node)

    def update_collision_sizes(self, units_per_pixel: float):
        safe_units = max(0.001, units_per_pixel)
        self.curve_pick_radius = safe_units * 6.0
        self.cp_pick_radius = safe_units * 12.0

        if self.node_path is not None:
            self.attach_collision_node()
            self.rebuild_cp_collision()

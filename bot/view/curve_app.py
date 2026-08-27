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
from bot.core.spline import SplineModel

MASK_CURVE_PICK = BitMask32.bit(1)
MASK_CP_PICK = BitMask32.bit(2)


class CurveApp:
    """
    Represents a 3D curve (visual and physical) manipulable in the editor.
    """

    def __init__(self, tag: str, curve_data: Dict):
        self.tag: str = str(tag)
        self.edges: List = curve_data["edges"]
        self.points: List = curve_data["points"]
        self.type: str = curve_data["type"]
        self.degree = curve_data.get("degree")
        self.weights = curve_data.get("weights") or None

        # ==========================================
        # NODEPATH VARIABLES
        # ==========================================

        # 1. Global object root
        self.root_node: Optional[NodePath] = None

        # 2. Node of the curve
        self.curve_render_node: Optional[NodePath] = None
        self.curve_geom_node: Optional[NodePath] = None
        self.curve_collision_node: Optional[NodePath] = None

        # 3. Node of control points
        self.cp_render_node: Optional[NodePath] = None
        self.cp_points_geom_node: Optional[NodePath] = None
        self.cp_lines_geom_node: Optional[NodePath] = None
        self.cp_collision_node: Optional[NodePath] = None

        # 4. Node of knots
        self.knots_render_node: Optional[NodePath] = None
        self.knots_geom_node: Optional[NodePath] = None

        # ==========================================
        # CONTROLE POINTS
        # ==========================================

        self.control_points = curve_data.get("control_points", []) or None
        self.cp_color: Optional[List[List[float]]] = None
        if self.control_points is not None:
            self.cp_color = [
                [0.5, 0.5, 0.5, 1.0] for _ in range(len(self.control_points))
            ]

        # ==========================================
        # KNOTS
        # ==========================================

        self.knots = curve_data.get("knots") or None
        if self.knots is not None:
            self.knots_color = [
                [0.8, 0.5, 0.2, 1.0]
                for _ in range(self.degree, len(self.knots) - self.degree)
            ]

        # ==========================================
        # OTHER PROPERTIES
        # ==========================================

        self.selected: bool = False
        self.line_thickness: float = 2.0

        self.curve_pick_radius: float = 0.2
        self.cp_pick_radius: float = 0.4

    # =========================================================================
    # VISUAL PART (RENDERING)
    # =========================================================================

    def __draw_knots(self, parent_node: NodePath):
        """Generates the visual geometry for knots by interpolating curve points."""
        if self.knots is None or self.degree is None or not self.points:
            return

        format = GeomVertexFormat.getV3cp()
        vdata = GeomVertexData("knots_data", format, Geom.UHDynamic)
        vertex_writer = GeomVertexWriter(vdata, "vertex")
        color_writer = GeomVertexWriter(vdata, "color")
        prim = GeomPoints(Geom.UHDynamic)

        vertex_index = 0
        num_points = len(self.points)

        for i in range(self.degree, len(self.knots) - self.degree):
            t = self.knots[i]

            idx_float = t * (num_points - 1)
            idx_int = int(idx_float)
            frac = idx_float - idx_int

            if idx_int >= num_points - 1:
                pt = self.points[-1]
            else:
                p1 = self.points[idx_int]
                p2 = self.points[idx_int + 1]
                pt = [
                    p1[0] + frac * (p2[0] - p1[0]),
                    p1[1] + frac * (p2[1] - p1[1]),
                    p1[2] + frac * (p2[2] - p1[2]),
                ]

            vertex_writer.addData3f(*pt)
            color_writer.addData4f(*self.knots_color[i - self.degree])
            prim.addVertex(vertex_index)
            vertex_index += 1

        prim.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        gnode = GeomNode(f"knots_geom_{self.tag}")
        gnode.addGeom(geom)

        if self.knots_geom_node is not None:
            self.knots_geom_node.removeNode()

        self.knots_geom_node = parent_node.attachNewNode(gnode)
        self.knots_geom_node.setRenderModeThickness(12)

    def __draw_control_points(self, parent_node: NodePath):
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

        if self.cp_points_geom_node is not None:
            self.cp_points_geom_node.removeNode()

        self.cp_points_geom_node = parent_node.attachNewNode(gnode)
        self.cp_points_geom_node.setRenderModeThickness(10)

        # Drawing connections (segments)
        lines = LineSegs()
        lines.setThickness(1)
        for i, pt in enumerate(self.control_points):
            if i == 0:
                lines.moveTo(*pt)
            else:
                lines.drawTo(*pt)

        if self.cp_lines_geom_node is not None:
            self.cp_lines_geom_node.removeNode()

        self.cp_lines_geom_node = parent_node.attachNewNode(lines.create())

    def __draw_curve(self):
        """Generates the main visual line of the curve."""
        lines = LineSegs()
        lines.setThickness(float(self.line_thickness))
        if self.tag.split(":")[0] == "spline":
            lines.setColor(0, 1, 1, 1)
        else:
            lines.setColor(1, 0, 1, 1)

        for idxA, idxB in self.edges:
            lines.moveTo(*self.points[idxA])
            lines.drawTo(*self.points[idxB])
        if self.curve_geom_node is not None:
            self.curve_geom_node.removeNode()

        self.curve_geom_node = self.curve_render_node.attachNewNode(lines.create())

    # =========================================================================
    # PHYSICAL PART (COLLISIONS)
    # =========================================================================

    def attach_collision_node(self) -> NodePath:
        """Attaches collision volumes for the main curve."""
        if self.curve_collision_node is not None:
            self.curve_collision_node.removeNode()

        self.curve_collision_node = self.root_node.attachNewNode("curve_collision")
        cnode = CollisionNode(f"col_{self.tag}")
        cnode.setFromCollideMask(BitMask32.allOff())
        cnode.setIntoCollideMask(MASK_CURVE_PICK)

        self.__populate_curve_collision_solids(cnode)

        cnp = self.curve_collision_node.attachNewNode(cnode)
        cnp.setTag("curve_tag", str(self.tag))
        cnp.setTag("pick_kind", "curve")
        return cnp

    def __populate_curve_collision_solids(self, cnode: CollisionNode):
        """Generates collision tubes for the curve edges."""
        for idxA, idxB in self.edges:
            ptA, ptB = self.points[idxA], self.points[idxB]
            dist_sq = sum((ptA[i] - ptB[i]) ** 2 for i in range(3))

            if dist_sq < 1e-5:
                continue

            tube = CollisionTube(
                ptA[0], ptA[1], ptA[2], ptB[0], ptB[1], ptB[2], self.curve_pick_radius
            )
            cnode.addSolid(tube)

    def rebuild_cp_collision(self):
        """Rebuilds the collision spheres for the control points."""
        if self.control_points is None or self.root_node is None:
            return

        if self.cp_collision_node is not None:
            self.cp_collision_node.removeNode()

        self.cp_collision_node = self.root_node.attachNewNode("cp_collision")
        current_mask = MASK_CP_PICK if self.selected else BitMask32.allOff()

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
        self.__clean_nodes()
        self.root_node = node_path
        self.root_node.setTag("curve_tag", str(self.tag))

        self.curve_render_node = self.root_node.attachNewNode("curve_render")
        self.__draw_curve()
        self.attach_collision_node()

        if self.control_points is not None:
            self.__attach_cp_node()

        if self.knots is not None:
            self.__attach_knots_node()

        return self.root_node

    def __attach_knots_node(self) -> NodePath:
        """Initializes the parent node for the curve knots."""
        self.knots_render_node = self.root_node.attachNewNode("knots_render")
        self.__draw_knots(self.knots_render_node)

        self.knots_render_node.setLightOff(1)
        self.knots_render_node.hide()
        return self.knots_render_node

    def __attach_cp_node(self) -> NodePath:
        """Initializes the parent node for the control points."""
        self.cp_render_node = self.root_node.attachNewNode("cp_render")

        self.__draw_control_points(self.cp_render_node)
        self.rebuild_cp_collision()

        self.cp_render_node.setLightOff(1)
        self.cp_render_node.hide()
        return self.cp_render_node

    def __clean_nodes(self):
        """Cleans up all existing nodes before reinitialization."""
        if self.curve_render_node:
            self.curve_render_node.removeNode()
        if self.curve_collision_node:
            self.curve_collision_node.removeNode()
        if self.cp_render_node:
            self.cp_render_node.removeNode()
        if self.cp_collision_node:
            self.cp_collision_node.removeNode()
        if self.knots_render_node:
            self.knots_render_node.removeNode()

    def set_cp_color(self, cp_index: int, color: List[float]):
        """Updates the color of a specific control point and refreshes its rendering."""
        self.cp_color[cp_index] = color
        if self.cp_render_node is not None:
            self.__draw_control_points(self.cp_render_node)

    def set_color(self, color: List[float]):
        """Sets the color of the main curve geometry."""
        if self.curve_render_node:
            self.curve_render_node.setColor(*color[:4], 1)
            self.curve_render_node.setLightOff(1)

        if self.cp_render_node is not None:
            self.cp_render_node.show() if self.selected else self.cp_render_node.hide()
        if self.knots_render_node is not None:
            self.knots_render_node.show() if self.selected else self.knots_render_node.hide()

    def is_selected(self, visible: bool):
        """Toggles the visibility and collision mask of the control points."""
        self.selected = visible
        if self.cp_render_node is None:
            return

        self.cp_render_node.show() if visible else self.cp_render_node.hide()

        if self.knots_render_node is not None:
            self.knots_render_node.show() if visible else self.knots_render_node.hide()

        if self.cp_collision_node is not None:
            current_mask = MASK_CP_PICK if visible else BitMask32.allOff()
            for cnp in self.cp_collision_node.getChildren():
                cnp.node().setIntoCollideMask(current_mask)
                cnp.setCollideMask(current_mask)

    def preview_evaluate(self, cp_index: int, new_pos: List[float]):
        """Updates a control point position and re-evaluates the curve for real-time preview."""
        if not self.control_points or not (0 <= cp_index < len(self.control_points)):
            return

        self.control_points[cp_index] = [new_pos[0], new_pos[1], new_pos[2]]

        if self.degree is not None:
            pts = SplineModel.preview_evaluate(
                self.type,
                self.degree,
                np.array(self.control_points, dtype=np.float64),
                knots=self.knots,
            )

            if len(pts.shape) == 2 and pts.shape[0] in (2, 3) and pts.shape[1] > 3:
                pts = pts.T

            self.points = pts.tolist()
            self.edges = [(i, i + 1) for i in range(len(self.points) - 1)]

        if self.curve_render_node:
            self.__draw_curve()
        if self.cp_render_node:
            self.__draw_control_points(self.cp_render_node)
        if self.knots_render_node is not None:
            self.__draw_knots(self.knots_render_node)

    def update_collision_sizes(self, units_per_pixel: float):
        """Adjusts collision radius based on the current zoom level to maintain consistent screen-space picking."""
        safe_units = max(0.001, units_per_pixel)
        self.curve_pick_radius = safe_units * 6.0
        self.cp_pick_radius = safe_units * 12.0

        if self.root_node is not None:
            self.attach_collision_node()
            self.rebuild_cp_collision()

    def apply_geometry_bytes(self, buf: bytes, vertex_count: int) -> None:
        """Update curve polyline vertices from a float32 byte buffer."""
        arr = np.frombuffer(buf, dtype=np.float32, count=vertex_count * 3)
        self.points = arr.reshape(vertex_count, 3).tolist()
        self.edges = [(i, i + 1) for i in range(vertex_count - 1)]
        if self.curve_render_node is not None:
            self.__draw_curve()
        if self.root_node is not None:
            self.attach_collision_node()

    def apply_control_vertices_bytes(self, buf: bytes, cp_count: int) -> None:
        """Update control point positions from a float32 byte buffer."""
        if self.control_points is None:
            return
        arr = np.frombuffer(buf, dtype=np.float32, count=cp_count * 3)
        self.control_points = arr.reshape(cp_count, 3).tolist()
        if self.cp_render_node is not None:
            self.__draw_control_points(self.cp_render_node)
            self.rebuild_cp_collision()
        if self.knots_render_node is not None:
            self.__draw_knots(self.knots_render_node)

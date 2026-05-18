from typing import Optional, Dict, Any, Tuple
from panda3d.core import (
    BitMask32,
    CollisionHandlerQueue,
    CollisionNode,
    CollisionRay,
    CollisionTraverser,
    Point2,
)


class RayPicker:
    """
    Manages ray casting from the camera to select 3D objects (curves, control points).
    """

    MASK_CURVE = BitMask32.bit(1)
    MASK_CP = BitMask32.bit(2)

    def __init__(self, base):
        """Initializes the collision system for mouse picking."""
        self.base = base
        self.traverser = CollisionTraverser()
        self.queue = CollisionHandlerQueue()

        self.picker_node = CollisionNode("mouseRay")
        self.picker_np = self.base.camera.attachNewNode(self.picker_node)
        self.picker_node.setFromCollideMask(self.MASK_CURVE | self.MASK_CP)
        self.picker_node.setIntoCollideMask(BitMask32.allOff())

        self.picker_ray = CollisionRay()
        self.picker_node.addSolid(self.picker_ray)
        self.traverser.addCollider(self.picker_np, self.queue)

    def pick_entry(self, m_pos: Point2, expected_kind: str) -> Optional[Any]:
        """
        Casts a ray from the mouse position and returns the entry corresponding to the expected kind.
        """
        self.picker_node.setFromCollideMask(self.MASK_CURVE | self.MASK_CP)
        self.picker_ray.setFromLens(self.base.camNode, m_pos.getX(), m_pos.getY())
        self.traverser.traverse(self.base.render)

        if self.queue.getNumEntries() == 0:
            return None

        entries = [self.queue.getEntry(i) for i in range(self.queue.getNumEntries())]
        entries.sort(key=lambda e: self._get_priority_distance_depth(e, m_pos))

        for entry in entries:
            np = entry.getIntoNodePath()
            if np.hasNetTag("pick_kind") and np.getNetTag("pick_kind") == expected_kind:
                return entry

        return None

    def get_metadata(self, entry: Any) -> Dict[str, Any]:
        """Extracts metadata (tag, index, position) from a collision entry."""
        np = entry.getIntoNodePath()
        pick_kind = np.getNetTag("pick_kind") if np.hasNetTag("pick_kind") else None
        point = entry.getSurfacePoint(self.base.render)

        if pick_kind == "cp":
            solid = entry.getInto()
            if hasattr(solid, "getCenter"):
                point = self.base.render.getRelativePoint(np, solid.getCenter())

        return {
            "curve_tag": np.getNetTag("curve_tag") if np.hasNetTag("curve_tag") else None,
            "cp_index": np.getNetTag("cp_index") if np.hasNetTag("cp_index") else None,
            "pick_kind": pick_kind,
            "point": point,
        }

    def _get_priority_distance_depth(self, entry: Any, m_pos: Point2) -> Tuple[int, float, float]:
        """Calculates the priority score for sorting collisions (favors CPs)."""
        np = entry.getIntoNodePath()
        pick_kind = np.getNetTag("pick_kind") if np.hasNetTag("pick_kind") else ""
        depth = entry.getSurfacePoint(self.base.cam).getY()

        if pick_kind == "cp":
            solid = entry.getInto()
            if hasattr(solid, "getCenter"):
                cp_world = self.base.render.getRelativePoint(np, solid.getCenter())
                p2d = Point2()
                if self.base.camLens.project(cp_world, p2d):
                    dist_sq = (p2d.getX() - m_pos.getX())**2 + (p2d.getY() - m_pos.getY())**2
                    return (0, dist_sq, depth)
            return (0, 0.0, depth)

        return (1, 0.0, depth)

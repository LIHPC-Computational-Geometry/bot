from typing import Optional, List, Tuple
from panda3d.core import Plane, Point2, Point3, Vec3


class ConstraintManager:
    """
    Manages 3D mouse projection mathematics and axis constraints.
    """

    def __init__(self, base):
        self.base = base
        self.axis_constraint_mask: int = 7
        self.drag_start_world_pos: Optional[List[float]] = None
        self.drag_active_mask: int = 7
        self.drag_plane: Optional[Plane] = None

    def set_axis_constraint(self, mask: int):
        self.axis_constraint_mask = max(0, min(7, int(mask)))

    def build_drag_plane(self, start_point: Point3) -> Plane:
        """Creates a plane facing the camera passing through the start point."""
        normal = self.base.render.getRelativeVector(self.base.cam, Vec3(0, 1, 0))
        normal.normalize()
        return Plane(normal, start_point)

    def mouse_to_constrained_axis(self, m_pos: Point2) -> Optional[List[float]]:
        """Calculates the constrained world position on axes based on the mouse."""
        if self.drag_start_world_pos is None:
            return None

        start = self.drag_start_world_pos
        mask = int(self.drag_active_mask)

        if mask == 0:
            return list(start)
        if mask == 7:
            return self._mouse_to_plane(m_pos)

        ray_origin, ray_dir = self._mouse_to_ray(m_pos)
        if ray_origin is None or ray_dir is None:
            return None

        # Constraint on 1 axis (X=1, Y=2, Z=4)
        if mask in (1, 2, 4):
            axis_map = {1: Vec3(1, 0, 0), 2: Vec3(0, 1, 0), 4: Vec3(0, 0, 1)}
            axis_origin = Point3(*start)
            result = self._closest_point_on_axis_to_ray(
                ray_origin, ray_dir, axis_origin, axis_map[mask]
            )
            if result is not None:
                return result
            return self._apply_axis_constraint(start, self._mouse_to_plane(m_pos))

        # Constraint on plane (XY, XZ, YZ)
        plane_normal = self._plane_normal_from_mask(mask)
        if plane_normal is not None:
            plane = Plane(plane_normal, Point3(*start))
            ray_to = ray_origin + ray_dir * 1e9
            hit = Point3()
            if plane.intersectsLine(hit, ray_origin, ray_to):
                return [hit[0], hit[1], hit[2]]

        return self._apply_axis_constraint(start, self._mouse_to_plane(m_pos))

    def _mouse_to_ray(self, m_pos: Point2) -> Tuple[Optional[Point3], Optional[Vec3]]:
        """Projects the 2D mouse position into a 3D ray (origin, direction)."""
        p_from, p_to = Point3(), Point3()
        if not self.base.camLens.extrude(m_pos, p_from, p_to):
            return None, None

        dir_cam = Vec3(p_to - p_from)
        dir_cam.normalize()

        if abs(dir_cam.getY()) > 1e-6:
            t = (0 - p_from.getY()) / dir_cam.getY()
            origin_cam = p_from + dir_cam * t
        else:
            origin_cam = p_from

        p_from_world = self.base.render.getRelativePoint(self.base.cam, origin_cam)
        direction = self.base.render.getRelativeVector(self.base.cam, dir_cam)
        return p_from_world, direction

    def _mouse_to_plane(self, m_pos: Point2) -> Optional[List[float]]:
        if self.drag_plane is None:
            return None
        ray_origin, ray_dir = self._mouse_to_ray(m_pos)
        if ray_origin is None or ray_dir is None:
            return None

        hit = Point3()
        if self.drag_plane.intersectsLine(hit, ray_origin, ray_origin + ray_dir * 1e9):
            return [hit[0], hit[1], hit[2]]
        return None

    def _apply_axis_constraint(
        self, start_pos: List[float], candidate_pos: Optional[List[float]]
    ) -> Optional[List[float]]:
        if start_pos is None or candidate_pos is None:
            return candidate_pos
        if self.axis_constraint_mask == 0:
            return list(start_pos)

        constrained = list(candidate_pos)
        if not (self.axis_constraint_mask & 1):
            constrained[0] = start_pos[0]
        if not (self.axis_constraint_mask & 2):
            constrained[1] = start_pos[1]
        if not (self.axis_constraint_mask & 4):
            constrained[2] = start_pos[2]
        return constrained

    def _closest_point_on_axis_to_ray(
        self, ray_origin, ray_dir, axis_origin, axis_dir
    ) -> Optional[List[float]]:
        w0 = ray_origin - axis_origin
        a = ray_dir.dot(ray_dir)
        b = ray_dir.dot(axis_dir)
        c = axis_dir.dot(axis_dir)
        d = ray_dir.dot(w0)
        e = axis_dir.dot(w0)
        denom = a * c - b * b
        if abs(denom) < 1e-10:
            return None
        t_axis = (a * e - b * d) / denom
        hit = axis_origin + axis_dir * t_axis
        return [hit[0], hit[1], hit[2]]

    def _plane_normal_from_mask(self, mask: int) -> Optional[Vec3]:
        match mask:
            case 3:
                return Vec3(0, 0, 1)
            case 5:
                return Vec3(0, 1, 0)
            case 6:
                return Vec3(1, 0, 0)
            case _:
                return None

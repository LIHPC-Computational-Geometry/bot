"""Binary serialization helpers for IPC geometry payloads."""

from __future__ import annotations

import struct
from typing import Any, Iterable, Sequence

import numpy as np

from bot.viewer.contracts import CurveDelta, CurveGeometry, ScenePayload, SceneUpdateOp


def floats_to_bytes(points: Sequence[Sequence[float]] | np.ndarray) -> bytes:
    """Pack xyz triples as a contiguous float32 byte array."""
    arr = np.asarray(points, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 3)
    elif arr.ndim == 2 and arr.shape[0] in (2, 3) and arr.shape[1] > 3:
        arr = arr.T
    return arr.reshape(-1).tobytes()


def bytes_to_floats(buf: bytes, vertex_count: int) -> memoryview:
    """Return an O(1) memoryview over ``vertex_count`` xyz vertices."""
    expected = vertex_count * 12
    return memoryview(buf)[:expected]


def vertex_count_from_bytes(buf: bytes) -> int:
    """Return the number of xyz vertices encoded in a float32 buffer."""
    return len(buf) // 12


def pack_curve_geometry(
    curve_points: Sequence[Sequence[float]] | np.ndarray,
    control_points: Sequence[Sequence[float]] | np.ndarray | None = None,
) -> CurveGeometry:
    """Build a CurveGeometry dict with float32 byte channels."""
    geometry: CurveGeometry = {"curve_vertices": floats_to_bytes(curve_points)}
    if control_points is not None and len(control_points) > 0:
        geometry["control_vertices"] = floats_to_bytes(control_points)
    return geometry


def pack_curve_delta(
    curve_points: Sequence[Sequence[float]] | np.ndarray,
    edges: list[tuple[int, int]] | None,
    curve_type: str = "linear",
    control_points: Sequence[Sequence[float]] | np.ndarray | None = None,
    degree: int | None = None,
) -> CurveDelta:
    """Build a single CurveDelta entry."""
    geometry = pack_curve_geometry(curve_points, control_points)
    vertex_count = vertex_count_from_bytes(geometry["curve_vertices"])
    delta: CurveDelta = {
        "geometry": geometry,
        "vertex_count": vertex_count,
        "type": curve_type,  # type: ignore[typeddict-item]
        "edges": edges,
    }
    if control_points is not None:
        delta["cp_count"] = len(control_points)
    if degree is not None:
        delta["degree"] = degree
    if edges is not None:
        delta["edges"] = edges
    return delta


def merge_deltas(*payloads: ScenePayload) -> ScenePayload:
    """Merge multiple ScenePayload snapshots (same ``op``) into one payload."""
    merged_curves: dict[str, CurveDelta] = {}
    deleted: list[str] = []
    bounds: dict[str, Any] | None = None
    points: bytes | None = None
    edges: list[tuple[int, int, str]] | None = None
    op: SceneUpdateOp = SceneUpdateOp.ADD

    for payload in payloads:
        op = payload.get("op", op)
        merged_curves.update(payload.get("changed_curves", {}))
        deleted.extend(payload.get("deleted_curves", []))
        if "bounds" in payload:
            bounds = payload["bounds"]
        if "points" in payload:
            points = payload["points"]
        if "edges" in payload:
            edges = payload["edges"]

    result: ScenePayload = {"op": op, "changed_curves": merged_curves}
    if deleted:
        result["deleted_curves"] = deleted
    if bounds is not None:
        result["bounds"] = bounds
    if points is not None:
        result["points"] = points
    if edges is not None:
        result["edges"] = edges
    return result


def bytes_to_point_list(buf: bytes, vertex_count: int) -> list[list[float]]:
    """Decode float32 xyz bytes into a nested Python list for legacy scene build."""
    mv = bytes_to_floats(buf, vertex_count)
    floats = struct.unpack(f"{vertex_count * 3}f", mv)
    return [[floats[i], floats[i + 1], floats[i + 2]] for i in range(0, len(floats), 3)]


def curve_delta_to_curve_info(tag: str, delta: CurveDelta) -> dict[str, Any]:
    """Convert a CurveDelta into the dict format expected by CurveApp."""
    points = bytes_to_point_list(
        delta["geometry"]["curve_vertices"], delta["vertex_count"]
    )
    edges = delta.get("edges")
    if edges is None:
        edges = [(i, i + 1) for i in range(len(points) - 1)]

    info: dict[str, Any] = {
        "points": points,
        "edges": edges,
        "type": delta["type"],
    }
    control_vertices = delta["geometry"].get("control_vertices")
    if control_vertices is not None and delta.get("cp_count"):
        info["control_points"] = bytes_to_point_list(
            control_vertices, delta["cp_count"]
        )
    if "degree" in delta:
        info["degree"] = delta["degree"]
    return info


def payload_to_geom_data(payload: ScenePayload) -> ScenePayload:
    """Convert a load ScenePayload into legacy geom_data for Scene construction."""
    curves: ScenePayload = {}
    for tag, delta in payload.get("changed_curves", {}).items():
        curves[str(tag)] = curve_delta_to_curve_info(str(tag), delta)

    geom_data: ScenePayload = {
        "curves": curves,
        "bounds": payload.get("bounds", {}),
    }

    flat_points: list[list[float]] = []
    flat_edges: list[tuple[int, int, int]] = []

    if "points" in payload and payload["points"]:
        point_count = vertex_count_from_bytes(payload["points"])
        flat_points = bytes_to_point_list(payload["points"], point_count)

    if "edges" in payload:
        for idx_a, idx_b, tag in payload["edges"]:
            flat_edges.append((idx_a, idx_b, str(tag)))
    else:
        offset = 0
        for tag, curve_info in curves.items():
            pts = curve_info["points"]
            flat_points.extend(pts)
            for idx_a, idx_b in curve_info["edges"]:
                flat_edges.append((offset + idx_a, offset + idx_b, str(tag)))
            offset += len(pts)

    geom_data["points"] = flat_points
    geom_data["edges"] = flat_edges
    return geom_data


def flatten_points_to_bytes(
    points: Iterable[Sequence[float]],
) -> bytes:
    """Serialize a flat point list for load payloads."""
    return floats_to_bytes(list(points))

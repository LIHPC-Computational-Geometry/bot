# Core Module (`bot.core`)

The `bot.core` module serves as the mathematical and geometric kernel of the **BOT** project. It isolates the heavy geometric computations and CAD integrations from the visual 3D rendering pipeline.

This module provides three main classes: `Observable`, `CADModel`, and `SplineModel`.

---

## 1. The Observer Pattern: `Observable`

Located in `bot/core/observable.py`.

To maintain a clean Anti-Corruption Layer (ACL), the core models do not know anything about Panda3D or the Viewer. Instead, they inherit from the `Observable` base class.

When a geometric mutation occurs (e.g., adding a point, moving a spline), the model calls `self._notify_observers()`. The attached adapters (like `CADAdapter` or `SplineAdapter`) listen to these notifications and automatically generate updated rendering payloads.

### Key Methods
*   `add_observer(observer)`: Registers a new listener (usually an Adapter).
*   `remove_observer(observer)`: Detaches a listener.
*   `_notify_observers()`: Triggers the `update(self)` method on all registered observers.

---

## 2. The CAD Engine: `CADModel`

Located in `bot/core/cad.py`.

The `CADModel` class is a wrapper around the [gmsh](https://gmsh.info/) library and the OpenCASCADE technology. It allows the system to open standard CAD files (like `.geo`, `msh`, `brep` or `.step`), query geometric topology, and add new spatial points.

### Lifecycle Methods
*   `initialize()`: Starts the `gmsh` context. Must be called before any geometric operations.
*   `finalize()`: Cleans up and shuts down the `gmsh` context.
*   `open(filename: str)`: Loads a geometric model from a file path and normalizes its scale (`self.scale_factor`) so it fits gracefully within the 3D viewer.

### Geometry Queries
*   `get_point_tags()` / `get_curve_tags()` / `get_surface_tags()`: Returns lists of integer IDs (tags) representing the entities currently in the model.
*   `get_end_points(curve_tag: int)`: Returns the tags of the starting and ending points of a given curve.
*   `get_point_coords(point_tag: int) -> list[float]`: Returns the `[x, y, z]` spatial coordinates of a point.
*   `getClosestPoint(dim: int, tag: int, coord: list) -> list[float]`: Projects a given 3D coordinate orthogonally onto the specified entity (curve or surface) and returns the closest valid `[x, y, z]`.
*   `get_curve_discretization() -> dict`: Computes the 1D mesh representation of all curves, returning a dictionary mapping each curve to its vertices and edges. This is primarily used by the viewer for rendering.

### Mutations
*   `add_point(coords: list, mesh_size: float = 1.0) -> int`: Adds a free point to the spatial model and automatically notifies the observers to trigger a visual update.

---

## 3. The Spline Engine: `SplineModel`

Located in `bot/core/spline.py`.

The `SplineModel` class manages the creation, evaluation, and manipulation of B-Splines (Bézier and NURBS curves). It acts as a Python bridge to the `ferrispline` Rust-backed library.

### Curve Types
The module exports two constants for curve instantiation:
*   `BEZIER_TYP = "bezier"`
*   `NURBS_TYP = "nurbs"`

### Curve Creation and Deletion
*   `add_curve(type: str, degree: int, control_points: list[list[float]], weights=None, knots=None) -> str`: Creates a new curve and returns its unique string tag.
*   `add_interpolated_curve(points: list[list[float]], degree: int) -> str`: Generates a curve that strictly passes through a given set of 3D points.
*   `remove_curve(tag: str)`: Deletes a specific curve from the model.

### Interaction and Evaluation
*   `get_control_points(curve_tag: str) -> list[list[float]]`: Retrieves the current `[x, y, z]` positions of a curve's control points.
*   `move_control_point(tag: str, cp_index: int, new_pt: list[float])`: Updates the spatial location of a specific control point and triggers `_notify_observers()`.
*   `preview_evaluate(...) -> list[list[float]]`: A stateless static method used by the Viewer to calculate smooth temporary curves (like rubber-band previews) without mutating the actual data model.
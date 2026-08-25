# Math Module (`bot.math`)

The `bot.math` module provides low-level mathematical operations and geometric constraints required for mapping 2D screen inputs to 3D spatial coordinates.

## 1. Constraint Management: `ConstraintManager`

Located in `bot/math/constraints.py`.

The `ConstraintManager` class is essential for handling 3D mouse projection mathematics and enforcing axis constraints during interactive editing (e.g., when a user drags a control point).

### Core Responsibilities
*   **Raycasting Math**: Converts a 2D mouse position into a 3D ray originating from the camera lens (`_mouse_to_ray`).
*   **Plane Projection**: Projects the camera ray onto a virtual dragging plane facing the camera (`_mouse_to_plane`, `build_drag_plane`).
*   **Axis Constraining**: Calculates the closest point on a constrained 3D axis (X, Y, Z, or combinations like XY) based on the user's mouse movement (`mouse_to_constrained_axis`).

### Axis Constraint Masks
The manager uses bitmasks to determine which axes are currently active for movement:
*   `1`: X-axis only
*   `2`: Y-axis only
*   `4`: Z-axis only
*   `3`: XY-plane (X=1 | Y=2)
*   `5`: XZ-plane (X=1 | Z=4)
*   `6`: YZ-plane (Y=2 | Z=4)
*   `7`: Free movement (all axes active)

### API Usage Example
```python
# Set constraint to X-axis only
constraints.set_axis_constraint(1)

# Calculate new 3D world position based on 2D mouse input
world_pos = constraints.mouse_to_constrained_axis(m_pos)
```

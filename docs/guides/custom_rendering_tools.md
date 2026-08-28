# Custom Rendering Tools and UI Elements

Welcome to the guide on creating custom rendering tools for the **BOT** project!

The 3D viewer is built on top of [Panda3D](https://www.panda3d.org/). While the core logic of the viewer handles standard model synchronization (like rendering curves and control points), you might want to create your own interactive tools, such as dynamic drawing guides, custom cursors, or new 2D on-screen displays (HUD).

This guide explains how to interact with the rendering layer located in the `bot.view` and `bot.control` submodules.

---

## 1. Creating Dynamic 3D Visual Tools

When building interactive tools (like drawing a new spline), you often need to render temporary graphics that update every frame based on the mouse position.

In Panda3D, the easiest way to draw dynamic lines is by using `LineSegs`.

### Example: A Simple Rubber-Band Line

Here is an example inspired by the `CreateSplineTool`. It shows how to draw a temporary line between a fixed point and the current mouse cursor in the 3D world (`render`).

```python
from panda3d.core import LineSegs, NodePath

class SimpleDrawingTool:
    def __init__(self, base):
        self.base = base
        # Create a parent node attached to the 3D world (render)
        self.preview_node = self.base.render.attachNewNode("preview_root")
        self.preview_node.setLightOff() # We don't want lighting to affect our lines
        self.current_line_np = None     # Will hold our dynamic line

    def draw_rubber_band(self, start_point, current_mouse_world_pos):
        # 1. Clean up the old line if it exists
        if self.current_line_np is not None:
            self.current_line_np.removeNode()

        # 2. Setup LineSegs
        lines = LineSegs()
        lines.setThickness(2.0)
        lines.setColor(0.0, 1.0, 0.0, 1.0) # Green color (R, G, B, Alpha)

        # 3. Define the line geometry
        lines.moveTo(*start_point)
        lines.drawTo(*current_mouse_world_pos)

        # 4. Create the node and attach it to our root
        self.current_line_np = self.preview_node.attachNewNode(lines.create())

    def clear(self):
        # Removes the preview from the screen.
        if self.current_line_np is not None:
            self.current_line_np.removeNode()
            self.current_line_np = None
```

**How it works:**
* You instantiate `LineSegs()`, configure its thickness and color, and map its vertices using `moveTo()` and `drawTo()`.
* Calling `.create()` compiles the geometry, which you then attach to the scene graph using `attachNewNode()`.
* Because the user is constantly moving the mouse, you clear the old node and generate a new one every frame.

---

## 2. Adding 2D HUD Elements (Heads-Up Display)

Sometimes, you need to overlay 2D elements directly on the screen, unaffected by the 3D camera rotation. Panda3D provides special root nodes for this:
* `base.render2d`: A 2D coordinate system ranging from -1 to 1 across the window.
* `base.pixel2d`: A 2D coordinate system where 1 unit = 1 pixel (origin is at the top-left).

### Example: Custom Text and Crosshair

Here is how you can add a simple text overlay and a custom crosshair, similar to how the `CursorManager` operates.

```python
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, LineSegs

class CustomHUD:
    def __init__(self, base):
        self.base = base

        # 1. Adding On-Screen Text (using render2d coordinate space)
        self.info_text = OnscreenText(
            text="Tool Active: Ready",
            pos=(-1.3, 0.9),          # Top-Left corner
            scale=0.07,
            fg=(1, 1, 1, 1),          # White text
            align=TextNode.ALeft
        )

        # 2. Adding a Custom 2D Crosshair at the center of the screen
        self.crosshair = self._create_crosshair()

    def _create_crosshair(self):
        lines = LineSegs()
        lines.setThickness(2.0)
        lines.setColor(1.0, 0.0, 0.0, 1.0) # Red crosshair

        size = 0.05
        # Draw horizontal line
        lines.moveTo(-size, 0, 0)
        lines.drawTo(size, 0, 0)
        # Draw vertical line
        lines.moveTo(0, 0, -size)
        lines.drawTo(0, 0, size)

        # Attach to render2d so it stays fixed on the screen
        crosshair_np = self.base.render2d.attachNewNode(lines.create())
        return crosshair_np

    def update_text(self, new_message):
        # Update the text dynamically.
        self.info_text.setText(new_message)
```

## Summary of Panda3D Scene Roots in BOT

When attaching your custom tools, always pick the right root node from the `base` (ShowBase) instance:

| Node | Purpose | Behavior |
| :--- | :--- | :--- |
| `base.render` | 3D World | Affected by camera zoom, pan, and rotation. Use for models, 3D grids, and drawing paths. |
| `base.render2d` | 2D Screen (Relative) | Fixed to the screen. Coordinates go from -1 to 1. Great for crosshairs or full-screen overlays. |
| `base.pixel2d` | 2D Screen (Pixels) | Fixed to the screen. 1 unit = 1 pixel. Ideal for exact placement of UI panels or Gizmos. |
| `base.a2dTopLeft` | 2D Screen Anchors | Sticks to window corners regardless of aspect ratio. Used for the help menu in `shortcuts_registry`. |

To see these concepts in action, check out `bot/control/create_tool.py` and `bot/view/scene.py` inside the project source code!
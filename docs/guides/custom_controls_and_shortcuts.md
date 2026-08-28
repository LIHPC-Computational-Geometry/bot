# Custom Controls and Shortcuts

Welcome to the guide on customizing controls and shortcuts for the **BOT** project! This guide will show you how to easily add your own keyboard and mouse interactions using the `bot.control` module.

## The Shortcut Registry

The project uses a centralized declarative registry to manage all user inputs. You can find it in `bot/control/shortcuts_registry.py`. We use a simple decorator called `@bind` to attach an input (like a key press or a mouse click) to a specific function.

There are two main "scopes" for shortcuts, depending on what you want to achieve:

1. **Local Scope (`scope="local"`)**:
   These shortcuts run directly inside the child process (the Panda3D 3D viewer). They are perfect for UI changes, camera movements, rendering updates, or toggling visual modes.
2. **Domain Scope (`scope="domain"`)**:
   These shortcuts send a message back to your main Python script (the parent process). They are used when you need to execute mathematical operations, modify the CAD geometry, or alter Spline models.

---

## Example 1: Creating a Local Shortcut

Let's say we want to add a shortcut to reset the camera to the center using the "r" key, and display a message on the screen.

```python
from bot.control.shortcuts import bind, Key

@bind(Key("r"), scope="local")
def reset_camera(ctx):
    # 'ctx' (InputContext) gives you access to the viewer's internal state.
    # We send a command to the local messenger to center the camera.
    ctx.messenger.send("cmd_center")

    # We can also interact with the HUD (Heads-Up Display) if it exists.
    if hasattr(ctx.base, "hud"):
        ctx.base.hud.setText("Camera reset to center!")
```

---

## Example 2: Creating a Domain Shortcut

If you want to trigger a heavy mathematical operation or manipulate the core model in your main script when you press "m":

```python
from bot.control.shortcuts import bind, Key

@bind(Key("m"), scope="domain")
def trigger_math_operation(ctx):
    # Returning a dictionary automatically emits a ViewEventType.SHORTCUT event
    # across the IPC pipe to the parent process.
    # The "action" key is automatically populated with the function name if omitted,
    # but it is good practice to be explicit.
    return {
        "action": "my_custom_math",
        "value": 42
    }
```

In your main script (the parent process), you would then catch this event using a callback:

```python
import bot
from bot.viewer.contracts import ViewEventType

# Initialize your viewer
viewer = bot.Viewer()

# Define the callback handler
def my_shortcut_handler(event_data):
    if event_data.get("action") == "my_custom_math":
        print(f"Math operation triggered with value: {event_data.get('value')}")

# Register the callback
viewer.add_callback(ViewEventType.SHORTCUT, my_shortcut_handler)
```

---

## Available Input Binding Types

You can bind much more than just single keys! The `bot.control.shortcuts` module provides several robust input types. Import them as needed:

* **`Key("a")`**: A single key press. You can use modifiers like `"shift-x"` or `"alt-z"`.
* **`Seq("a", "b")`**: An ordered sequence of keys. Fires only when the full sequence matches within a short timeout.
* **`Hold("arrow_up")`**: Keys held down. The handler is called every frame with a dictionary of the pressed states.
* **`Click("left", modifiers={"shift"})`**: A mouse click without significant movement.
* **`Drag("right")`**: A continuous mouse drag. The handler receives `(ctx, delta)` each frame to calculate movement.
* **`Wheel("up")`**: A mouse wheel tick (can be `"up"` or `"down"`).

### How to Register Your Custom Shortcuts

To ensure your shortcuts are loaded, simply define them in `bot/control/shortcuts_registry.py` or import your custom shortcut module before running `viewer.run()`. The registry will automatically install them into the Panda3D event loop.
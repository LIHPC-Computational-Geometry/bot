# Bot - Developer Documentation

Welcome to the **BOT** developer documentation. This guide is designed to help you understand the internal architecture of the project, learn how to extend it with new mathematical models, and customize user interactions.

## Documentation Map

### 1. Architecture & Internals
* **[Architecture & IPC Flow](architecture.md)**: Understand the multi-process design (Parent vs. Child process), the IPC communication pipe, and the geometry transport system.
* **[Advanced Internals](advanced_internals.md)**: A deep dive into low-level mechanics, including the Rust (FerriSpline) integration and future memory optimizations.

### 2. API Reference
Detailed documentation on the four main submodules that make up the project:
* **[Core Module (`bot.core`)](api/core.md)**: The mathematical and geometric kernel (CAD and Splines).
* **[Viewer Module (`bot.viewer`)](api/viewer.md)**: The public API, IPC contracts, and Anti-Corruption Layer (Adapters).
* **[View Module (`bot.view`)](api/view.md)**: The Panda3D rendering engine and scene management.
* **[Control Module (`bot.control`)](api/control.md)**: Input management, raycasting, camera logic, and shortcut registry.

### 3. Guides & Customization
Step-by-step guides for extending the platform:
* **[Connecting a Custom Model](guides/custom_model.md)**: Using the Adapter protocol to bridge new mathematical models to the 3D viewer.
* **[Customizing Callbacks](guides/callbacks.md)**: Intercepting UI events without breaking default behavior.
* **[Custom Controls and Shortcuts](guides/custom-controls-and-shortcuts.md)**: Adding new mouse and keyboard interactions via the declarative registry.
* **[Custom Rendering Tools](guides/custom_rendering_tools.md)**: Creating dynamic 3D tools (like drawing splines) and 2D HUD elements.
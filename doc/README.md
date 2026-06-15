# Bot — Developer Documentation

Welcome to the **bot** developer documentation. This guide is designed to help you understand the internal architecture of the project, learn how to extend it with new mathematical models, and customize user interactions.

## Documentation Map

1. **[Architecture & IPC Flow](architecture.md)**: Understand the multi-process design (Parent vs. Child process), the IPC communication pipe, and the vital differences between Events and Commands.
2. **[Connecting a New Model](custom_model.md)**: A step-by-step guide on using the IViewable protocol to bridge any custom mathematical or geometric model to the 3D viewer.
3. **[Customizing Callbacks](callbacks.md)**: Learn how to intercept user interactions using custom Python callbacks without breaking the default UI behavior.

## Directory Layout of the Source Code

* `bot/core/`: The mathematical kernel. Contains core domain models (CADModel utilizing Gmsh and SplineModel utilizing Ferrispline).
* `bot/viewer/`: The public API and the Anti-Corruption Layer (ACL). Includes Viewer, adapters, and serialization helpers.
* `bot/view/`: Internal rendering engine layers built on top of Panda3D (Scene, CurveApp).bot/control/: Input management scripts capturing mouse, keyboard, and camera physics.
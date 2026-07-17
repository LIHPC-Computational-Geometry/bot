# Bot — Developer Documentation

Welcome to the **bot** developer documentation. This guide helps you understand the architecture, extend the viewer bridge for new models, and customize interaction behavior.

## Documentation Map

1. **[Architecture & IPC Flow](architecture.md)**: Parent/child split, IPC pipe, and event-vs-command model.
2. **[Connecting a New Model](custom_model.md)**: `IViewable` bridge pattern for custom mathematical/geometric models.
3. **[Customizing Callbacks](callbacks.md)**: User callbacks and default handler integration.
4. **[Technical Reference V1](technical_reference_v1.md)**: Exhaustive reference for architecture, zero-copy/IPC behavior, raycasting, full API, and CI/CD.

## Directory Layout of the Source Code

- `bot/core/`: Mathematical kernel with `CADModel` (gmsh) and `SplineModel` (FerriSpline-backed).
- `bot/viewer/`: Public API and anti-corruption layer (viewer, adapters, contracts, serialization).
- `bot/view/`: Panda3D rendering internals (`Scene`, `CurveApp`).
- `bot/control/`: Input handling (mouse, keyboard, camera, picker).

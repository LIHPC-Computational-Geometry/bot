"""Thin keyboard adapter: Hold state is owned by the shortcut registry."""


class KeyboardHandler:
    """
    Keyboard input adapter for the shortcut registry.

    One-shot keys and sequences are installed by ``ShortcutRegistry.install``.
    This class remains as a stable hook for callers that expect ``kb_handler``.
    """

    def __init__(self, base):
        """
        Args:
            base: Panda3D ShowBase instance.
        """
        self.base = base

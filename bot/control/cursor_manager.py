from panda3d.core import LineSegs, WindowProperties


class CursorManager:
    def __init__(self, base, size: float = 0.025, thickness: float = 2.0):
        self.base = base
        self.is_custom = False
        self.size = size
        self.thickness = thickness
        self.custom_cursor = None
        self._setup_custom_cursor()

    def _setup_custom_cursor(self):
        """
        Creates a 2D vector cross whose intersection is exactly at the origin
        (0, 0, 0).
        """
        lines = LineSegs()
        lines.setThickness(self.thickness)
        lines.setColor(1, 1, 1, 1)

        lines.moveTo(-self.size, 0, 0)
        lines.drawTo(self.size, 0, 0)

        lines.moveTo(0, 0, -self.size)
        lines.drawTo(0, 0, self.size)

        self.custom_cursor = self.base.render2d.attachNewNode(lines.create())

        self.custom_cursor.setBin("fixed", 100)
        self.custom_cursor.setDepthWrite(False)
        self.custom_cursor.setLightOff()
        self.custom_cursor.hide()

    def set_cursor_mode(self, use_custom: bool | None = None):
        props = WindowProperties()

        if not self.is_custom or use_custom:
            if not self.is_custom:
                props.setCursorHidden(True)
                self.base.win.requestProperties(props)
                self.custom_cursor.show()
                self.base.mouseWatcherNode.setGeometry(self.custom_cursor.node())
                self.is_custom = True
        else:
            if self.is_custom:
                props.setCursorHidden(False)
                self.base.win.requestProperties(props)
                self.custom_cursor.hide()
                self.base.mouseWatcherNode.clearGeometry()
                self.is_custom = False

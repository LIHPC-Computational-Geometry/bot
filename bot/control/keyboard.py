from direct.showbase.DirectObject import DirectObject
from direct.showbase.InputStateGlobal import inputState
import sys

class KeyboardHandler(DirectObject):
    def __init__(self):
        DirectObject.__init__(self)
        
        # Actions directes (Events)
        self.accept('escape', sys.exit)
        
        self.accept('f5', lambda: base.messenger.send("cmd_hot_reload"))

        self.accept('c', lambda: base.messenger.send("cmd_center_camera"))

        self.accept('x', lambda: base.messenger.send("cmd_align_plane", ["x"]))
        self.accept('y', lambda: base.messenger.send("cmd_align_plane", ["y"]))
        self.accept('z', lambda: base.messenger.send("cmd_align_plane", ["z"]))
        # Flèches directionnelles
        self.accept('arrow_left',  lambda: base.messenger.send("cmd_pan", [-1, 0]))
        self.accept('arrow_right', lambda: base.messenger.send("cmd_pan", [1, 0]))
        self.accept('arrow_up',    lambda: base.messenger.send("cmd_pan", [0, 1]))
        self.accept('arrow_down',  lambda: base.messenger.send("cmd_pan", [0, -1]))

        self.accept('p', lambda: base.messenger.send("cmd_toggle_marker"))
        inputState.watchWithModifiers('up', 'arrow_up')
        inputState.watchWithModifiers('down', 'arrow_down')
        inputState.watchWithModifiers('left', 'arrow_left')
        inputState.watchWithModifiers('right', 'arrow_right')
from direct.showbase.DirectObject import DirectObject
from direct.showbase.InputStateGlobal import inputState
from panda3d.core import Point2 

class MouseHandler(DirectObject):
    def __init__(self):
        DirectObject.__init__(self)
        self.prev_mouse = None
        
        # 1. Modificateurs et Molette (Events)
        inputState.watchWithModifiers('shift', 'shift')
        self.accept('wheel_up',   lambda: base.messenger.send("cmd_zoom", [1.1]))
        self.accept('wheel_down', lambda: base.messenger.send("cmd_zoom", [0.9]))

        # 2. Mouvement continu (Task)
        taskMgr.add(self.update_mouse_task, "MouseUpdateTask")

    def is_shift_down(self):
        return inputState.isSet('shift')

    def update_mouse_task(self, task):
        if base.mouseWatcherNode.hasMouse():
            m_pos = base.mouseWatcherNode.getMouse()
            curr_pos = Point2(m_pos.getX(), m_pos.getY())

            # On ne calcule le déplacement que si on a une position précédente
            if self.prev_mouse is not None:
                delta = curr_pos - self.prev_mouse
                
                # On vérifie si un bouton est enfoncé pour agir
                # mouse1 = clic gauche, mouse2 = clic milieu, mouse3 = clic droit
                if base.mouseWatcherNode.isButtonDown("mouse1"):
                    if inputState.isSet('shift'):
                        # On envoie dx et dy pour le Pan
                        base.messenger.send("cmd_pan", [delta.getX(), delta.getY()])
                    else:
                        # On envoie dx et dy pour la Rotation
                        base.messenger.send("cmd_rotate", [delta.getX(), delta.getY()])
            
            self.prev_mouse = curr_pos
        else:
            # Si la souris sort de la fenêtre, on reset pour éviter un saut au retour
            self.prev_mouse = None
            
        return task.cont
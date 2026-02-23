from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from direct.showbase.InputStateGlobal import inputState
from panda3d.core import Point2, AmbientLight, Vec4, DirectionalLight, Vec3
from panda3d.core import GeomLines, Geom, GeomNode, GeomVertexFormat, GeomVertexData, GeomVertexWriter

from core.cad import Model as CADModel
from view.components import BotView
from control.camera import CameraController
from control.mouse import MouseHandler
from control.keyboard import KeyboardHandler
from view.ActorBuilder import ActorBuilder
import tomllib, os, sys

class BotApp(ShowBase):

    def __init__(self, filename, config_filename):
        ShowBase.__init__(self)
        
        #======================================================
        # We first load the config file that will inject dependencies 
        # inside each MVC controller class
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # We store the filepath as an attribute for the hot reload procedure
        self.filepath = os.path.join(base_dir, config_filename)
        self.config_data = self.load_config()
        self.accept("cmd_hot_reload", self.reload)
        #======================================================
        # Model
        self.model = CADModel()
        self.model.open(filename)
        #======================================================
        # View
        self.view = BotView(self, self.model)
        self.add_lighting()

        #======================================================
        # System Control 
        # On instancie les handlers (ils s'enregistrent via self.accept)
        self.kb_handler = KeyboardHandler()
        self.disable_mouse()
        self.mouse_handler = MouseHandler()
        
        # On instancie le contrôleur qui possède le Rig
        # Il va écouter les messages "cmd_pan", "cmd_zoom", etc.
        self.camera_controller = CameraController(self, self.view)

        # We finally update the controllers' parameters with the 
        # values given in the configuration file. We do that after
        # creating the controller instances because of the hot reload
        # procedure that must work when the objects are already created.
        self.sync_config_to_controllers()
       
    
    def load_config(self):
        """ Load the content of the config_file
        """
        if os.path.exists(self.filepath):
            with open(self.filepath, "rb") as f:
                return tomllib.load(f)
        print(f"Warning: {self.filepath} unfound, load default values.")
        return {}
    
    def reload(self):
        """Reload the configuration from the file system."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "rb") as f:
                self.config_data = tomllib.load(f)
            print("Configuration reloaded with success")
            return True
        return False

    def sync_config_to_controllers(self):
        """We inject dependencies into the main controller of each component"""
        
        # Préparation du dictionnaire de réglages pour la caméra
        camera_settings = {
            'pan_speed': self.config_data['view']['camera']['pan_speed'],
            'bg_color': self.config_data['view']['display']['background_color'],
            'line_thickness': self.config_data['view']['display']['line_thickness']
        }
        print(camera_settings)
        # On pousse les réglages
        self.camera_controller.apply_settings(camera_settings)
        print("Synchronisation des paramètres effectuée.")

    def trigger_hot_reload(self):
        """Méthode appelée par la touche F5."""
        if self.reload():
            self.sync_config_to_controllers()

    def add_lighting(self):
        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor(Vec4(0.3, 0.3, 0.3, 1))
        directionalLight = DirectionalLight("directionalLight")
        directionalLight.setColor(Vec4(1, 1, 1, 1))
        directionalLight.setDirection(Vec3(-1, -1, -1))

        self.render.setLight(self.render.attachNewNode(ambientLight))
        self.render.setLight(self.render.attachNewNode(directionalLight))

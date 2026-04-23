import gmsh
import numbers
from pathlib import Path

""""global value to indicate how to round floating numbers"""
nb_digit_rounding = 4

class Model:
    """
    The geometric model provides simple and basic function to load geometric files and to query a geometric model
    based on the OpenCascade technology. To do so, we totally rely on the gmsh library.
    """
    def __init__(self):
        self.initialize()
        self._observers = []
        self.bounds = {'min': [0,0,0], 'max': [0,0,0]}
        self.curves = {}

    def set_curve(self, tag: int, curve_object):
        """Stocke une courbe modifiée (ex: BezierCurve) et notifie l'interface."""
        self.curves[tag] = curve_object
        self._notify_observers()

    def get_curve(self, tag: int):
        return self.curves.get(tag)

    def add_observer(self, observer):
        self._observers.append(observer)

    def remove_observer(self, observer):
        self._observers.remove(observer)

    def _notify_observers(self):
        for observer in self._observers:
            observer.update(self)

    def initialize(self):
        """
        core.cad.Model.initialize()

        initialize the gmsh context useful for the geometric model. This operation must be called before any
        other operations.
        """
        gmsh.initialize()
        # We clear the gmsh context in order to add new
        gmsh.clear()
        # to avoid messages on the console
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMin", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 5)

    def finalize(self):
        """
        core.cad.Model.finalize()
        This operation must be called at the end of the program to finalize the gmsh context.

        If this operation is called, it is impossible to use this obkject anymore.
        """
        gmsh.finalize()

    def open(self,filename):
        """
        core.cad.Model.open(filename)

        open the model contained in the file named `filename`, which is the path to
        the file to import. The model is clear beforehand

        Types:
        - `filename`: string
        """
        if Path(filename).suffix == ".geo":
                gmsh.open(filename)
        else:
            gmsh.model.occ.importShapes(filename)

        self._discretize_curves()
        self._recompute_bounds()
        self.__synchronize()

    def _recompute_bounds(self):
        node_tags, coords, _ = gmsh.model.mesh.getNodes()
        # The map will be used later to store some geom info
        # node_map = {tag: i for i, tag in enumerate(node_tags)}
        self.points = [(coords[i], coords[i+1], coords[i+2]) for i in range(0, len(coords), 3)]
        if not self.points:
            return
        #Compute now the bounds for automatic rescaling
        xs, ys, zs = zip(*self.points)
        self.bounds = {
            'min': [min(xs), min(ys), min(zs)],
            'max': [max(xs), max(ys), max(zs)],
            'center': [(min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2],
            'size': [max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)],
        }

    def get_render_data(self) -> dict:
        """Return all display data needed by the viewer (thread-safe, no gmsh dependency)."""
        curves_data = {}

        node_tags, coords, _ = gmsh.model.mesh.getNodes()
        node_id_to_coords = {
            tag: (coords[i*3], coords[i*3+1], coords[i*3+2])
            for i, tag in enumerate(node_tags)
        }

        for entity in gmsh.model.getEntities(1):
            tag = entity[1]
            _, _, node_tags_per_elem = gmsh.model.mesh.getElements(1, tag)

            if not node_tags_per_elem:
                continue

            connectivity = node_tags_per_elem[0]

            # Index local à cette courbe
            seen = {}
            local_points = []
            local_edges = []

            for i in range(0, len(connectivity), 2):
                for node_tag in (connectivity[i], connectivity[i+1]):
                    if node_tag not in seen:
                        seen[node_tag] = len(local_points)
                        local_points.append(node_id_to_coords[node_tag])
                local_edges.append((seen[connectivity[i]], seen[connectivity[i+1]]))

            curve_entry = {
                'points': local_points,
                'edges': local_edges,
                'type': 'linear',
            }

            # Surcharge si courbe paramétrique connue
            if tag in self.curves:
                custom = self.curves[tag]
                render = custom.get_render_data()
                curve_entry.update({
                    'type': 'bezier',
                    'degree': render['degree'],
                    'control_points': render['control_points'],
                    'cp_edges': [(i, i+1) for i in range(len(render['control_points'])-1)],
                    'points': render['curve'],   # écrase les pts gmsh
                    'edges': [(i, i+1) for i in range(len(render['curve'])-1)],
                })

            curves_data[str(tag)] = curve_entry

        return {
            'curves': curves_data,
            'bounds': dict(self.bounds),
        }

    def add_point(self, coords: list, mesh_size: float = 1.0) -> int:
        """
        Add a free point to the model at position coords = [x, y, z].
        Returns the gmsh tag of the new point.
        Notifies all connected viewers.
        """
        tag = gmsh.model.occ.addPoint(coords[0], coords[1], coords[2], mesh_size)
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.clear()
        gmsh.model.mesh.generate(1)
        self._recompute_bounds()
        self._notify_observers()
        return tag

    def __synchronize(self):
        """
       core.cad.Model.synchronize()

        This operation must be invocated after applying geometric operations to be sure to have a consistent state.
        We advise to call this method before starting the meshing stage.
        """
        gmsh.model.occ.synchronize()


    def __get_cell_tags(self, dim):
        """
        Private method that returns the tags, i.e. the ids, of the cells of dimension dim.
        This operation is private and must not be called directly outside the scope of public operations of
        cad.Model

        Args:
        dim (int): An int included in [0,3].

        Raises:
        - ValueError: if 'dim' is not included in [0,3].
        - TypeError: if 'dim' is not an int.
        """
        if not isinstance(dim, int):
            raise TypeError("the parameter must be an int.")
        if dim < 0 or dim > 3:
            raise ValueError("the parameter must be an int comprised between 0 and 3.")

        info = gmsh.model.occ.getEntities(dim)
        tags = []
        for i, j in info:
            tags.append(j)
        return tags


    def get_point_tags(self):
        """
        core.cad.Model.get_point_tags(dim)

        returns the tags of all the points
        """
        return self.__get_cell_tags(0)

    def get_curve_tags(self):
        """
        core.cad.Model.get_curve_tags(dim)

        return the tags of all the curves
        """
        return self.__get_cell_tags(1)

    def get_surface_tags(self):
        """
        core.cad.Model.get_surface_tags(dim)

        return the tags of all the surfaces
        """
        return self.__get_cell_tags(2)


    def getClosestPoint(self,dim, tag, coord):
        """
        core.cad.Model.getClosestPoint(dim, tag, coord)

        Get the points `closestCoord` on the entity of dimension `dim` (1 or 2) and
        tag `tag` to the points `coord`, by orthogonal projection. `coord` is given
        as x, y, z coordinates, concatenated: [p1x, p1y,
        p1z, p2x, ...]. The
        closest points can lie outside the (trimmed) entities: use `isInside()` to
        check.

        Return `closestCoord`, `parametricCoord`.

        Types:
        - `dim`: integer
        - `tag`: integer
        - `coord`: vector of doubles
        """
        if not isinstance(dim, int):
            raise TypeError("the dimension parameter (dim) must be an int.")
        if not isinstance(tag, int):
            raise TypeError("the tag parameter (tag) must be an int.")
        if not isinstance(coord, (list, tuple)) or len(coord)%3 != 0 or not all(
                isinstance(x, numbers.Real) for x in coord):
            raise TypeError("the coord parameter must be a list or tuple of 3 real numbers.")
        if dim < 1 or dim > 2:
            raise ValueError("the dim parameter must be an int comprised between 1 and 2.")

        return gmsh.model.getClosestPoint(dim, tag, coord)[0]

    def get_end_points(self,curve_tag):
        """
        core.cad.Model.get_end_points(curve_tag)

        Get the tags of the end points of the curve of id `curve_tag `
        Return `closestCoord`, `parametricCoord`.
        """
        data = gmsh.model.getAdjacencies(1, curve_tag)
        return data[1]

    def get_adjacent_curves_of_point(self, point_tag):

        # We check if the tag is an existing point tag
        if not point_tag in self.get_point_tags() :
            raise ValueError("Invalid point tag")

        curves = []
        # Traverse all the model curves
        for curve_tag in self.get_curve_tags():
            # get curve end points
            end_points = self.get_end_points(curve_tag)
            if end_points[0] == point_tag :
                curves.append(curve_tag)
            elif end_points[1] == point_tag :
                curves.append(curve_tag)
        return curves

    def get_adjacent_points(self, curve_tag):
        return list(self.get_end_points(curve_tag))

    def get_curves(self, face_tag):
        """
        Get all the curves that surround face defined by the tag face_tag

        This function accesses the Gmsh framework to extract a list of curves
        that define the boundary of a specified face. It utilizes the
        get_curve_loops method from the occ Model. Only the primary set of
        curves is returned from the nested output.

        :param face_tag: The identifier tag of the target face in the Gmsh model.
        :type face_tag: int
        :return: A list of curve identifiers that form the boundary of the specified face.
        :rtype: list[int]
        """
        return gmsh.model.occ.get_curve_loops(face_tag)[1][0]

    # Dans bot/core/cad.py

    def get_point_coords(self, point_tag: int) -> list[float]:
        """
        Récupère les coordonnées spatiales [x, y, z] d'un point géométrique.

        :param: point_tag: L'identifiant (tag) du point dans le modèle Gmsh.
        :type: point_tag:int
        :return: Une liste de trois flottants représentant les coordonnées.
        :rtype: list[float]
        """
        # La dimension 0 correspond aux points dans l'API Gmsh.
        # gmsh.model.getValue(dimension, tag, parametric_coords)
        coords = gmsh.model.getValue(0, point_tag, [])
        return list(coords)

    def get_end_points_coords(self, point_tag) -> list[list[float]]:
        """
        Retrieves the spatial coordinates [x, y, z] of the two endpoints of a given curve.

        :param point_tag: The tag (identifier) of the curve in the Gmsh model.
        :type point_tag: int or str
        :return: A list containing two lists of three floats representing the coordinates of the two endpoints.
        :rtype: list[list[float]]
        """
        tags_ext = self.get_end_points(int(point_tag))

        coords_a = self.get_point_coords(tags_ext[0])
        coords_b = self.get_point_coords(tags_ext[1])
        return [coords_a, coords_b]

    def get_corners(self, face_tag):
        """
        Extracts and returns the corner points of a given face in a geometric model. The method analyzes
        the adjacency information of the face and identifies the common points between consecutive curves
        that make up the face to determine the corners.

        :param face_tag: The tag of the face for which corner points are to be determined.
        :type face_tag: int
        :return: A list of corner point tags that outline the geometry of the face.
        :rtype: list[int]
        """
        curves = gmsh.model.getAdjacencies(2, face_tag)[1]
        corners = []
        for i_curve in range(0, len(curves)):
            j_index = i_curve - 1
            if i_curve == 0:
                j_index = len(curves) - 1
            prev_pnts = self.get_end_points(curves[j_index])
            current_pnts = self.get_end_points(curves[i_curve])
            common_pnt = 0
            if prev_pnts[0] == current_pnts[0]:
                common_pnt = current_pnts[0]
            elif prev_pnts[0] == current_pnts[1]:
                common_pnt = current_pnts[1]
            elif prev_pnts[1] == current_pnts[0]:
                common_pnt = current_pnts[0]
            else:
                common_pnt = current_pnts[1]
            corners.append(common_pnt)

        return corners

    def get_curve_discretization(self):
        # Get mesh node tags and their coordinates
        node_tags, coords, _ = gmsh.model.mesh.getNodes()
        node_id_to_index = {tag: i for i, tag in enumerate(node_tags)}
        # Get all the entities of dim 1
        elem_types, elem_tags, elem_node_tags = gmsh.model.mesh.getElements(dim=1)


        # On transforme la liste plate [x,y,z,x,y,z] en liste de tuples [(x,y,z), ...]
        points_3d = []
        for i in range(0, len(coords), 3):
            points_3d.append((coords[i], coords[i+1], coords[i+2]))



        # 2. Liste finale des données
        # Structure : (index_sommet_A, index_sommet_B, tag_courbe_origine)
        edges_with_metadata = []

        # 3. Parcourir chaque "Courbe" (entité de dimension 1)
        entities = gmsh.model.getEntities(1)

        for entity in entities:
            curve_tag = entity[1] # C'est le Tag de la courbe CAO

            # Récupérer les éléments (segments) appartenant UNIQUEMENT à cette courbe
            _, _, node_tags_per_elem = gmsh.model.mesh.getElements(1, curve_tag)

            if len(node_tags_per_elem) > 0:
                connectivity = node_tags_per_elem[0]

                # Parcourir les nœuds par paires pour former les arêtes
                for i in range(0, len(connectivity), 2):
                    tag_a = connectivity[i]
                    tag_b = connectivity[i+1]

                    # Conversion en indices (0, 1, 2...) pour Panda3D
                    idx_a = node_id_to_index[tag_a]
                    idx_b = node_id_to_index[tag_b]

                    edges_with_metadata.append((idx_a, idx_b, curve_tag))

        return points_3d, edges_with_metadata

    def _discretize_curves(self):
        self.__synchronize()
        gmsh.model.mesh.clear()
        gmsh.model.mesh.generate(1)

    def __discretize_surfaces(self):
        self.__synchronize()
        gmsh.model.mesh.generate(2)
        # Get mesh nodes
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        num_nodes = len(node_tags)
        node_coords_3d = list(zip(*(iter(node_coords),) * 3))  # (x, y, z) tuples

        # Build a node_id -> (x, y, z) map for later use
        node_map = dict(zip(node_tags, node_coords_3d))

        # === 2. Get all face elements (triangles & quads) ===
        surfaces = []
        # type 1 = edge, type 2 = triangle, type 15 = point
        surf_tags = self.get_surface_tags()
        for i in surf_tags:
            element_types, element_tags, node_tags_list = gmsh.model.mesh.getElements(2, i)
            faces=[]
            for elem_tags, elem_node_tags in zip(element_tags, node_tags_list):
                for i in range(len(elem_tags)):
                    elem_id = elem_tags[i]
                    node_ids = [nid - 1 for nid in elem_node_tags[i * 3: (i + 1) * 3]]
                    faces.append(node_ids)
            surfaces.append(faces)

        return node_coords_3d, surfaces

    def update_control_point(self, tag: int, cp_index: int, new_pt: list(float)):
        """Met à jour un point de contrôle d'une courbe et rafraîchit l'affichage."""
        if tag in self.curves:
            curve = self.curves[tag]

            cps = curve.get_control_points()

            if 0 <= cp_index < len(cps):
                cps[cp_index] = new_pt

                degree = curve.get_degree()
                new_curve = type(curve)(str(tag), cps, degree) # FIXME: We recreate the curve :(
                self.curves[tag] = new_curve

                self._notify_observers()
            else:
                print(f"Erreur : L'index {cp_index} n'existe pas. La courbe a {len(cps)} points de contrôle.")
        else:
            print(f"Erreur : La courbe {tag} n'est pas une courbe personnalisée.")
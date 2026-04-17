"""
Unit tests for bot.core.curve.BezierCurve.

The external Rust dependency (nurbslib) is mocked to allow testing the
Python bridge and logic without requiring the compiled engine.
"""
import unittest
from unittest.mock import MagicMock, patch

from bot.core.curve import BezierCurve


class TestBezierCurve(unittest.TestCase):

    @patch('bot.core.curve.nurbslib')
    def test_initialization_and_attributes(self, mock_nurbslib):
        """Test l'initialisation de la courbe et l'accès à ses attributs de base."""
        # 1. Préparation des données
        tag = "curve_1"
        control_points = [[0.0, 0.0, 0.0], [5.0, 5.0, 0.0], [10.0, 0.0, 0.0]]
        degree = 2

        # 2. Configuration du mock pour simuler le moteur nurbslib
        mock_engine_instance = MagicMock()
        mock_engine_instance.get_control_points.return_value = control_points
        mock_engine_instance.get_degree.return_value = degree
        mock_nurbslib.PyBezierCurve.return_value = mock_engine_instance

        # 3. Création de l'objet
        curve = BezierCurve(tag, control_points, degree)

        # 4. Vérifications (Assertions)
        self.assertEqual(curve.get_tag(), "curve_1")
        self.assertEqual(curve.get_control_points(), control_points)
        self.assertEqual(curve.get_degree(), degree)

        # On s'assure que le moteur Rust a bien été appelé avec les bons arguments
        mock_nurbslib.PyBezierCurve.assert_called_once_with(degree, control_points, None)

    def test_default_control_points_default_degree(self):
        """Test que la méthode utilise bien le degré 3 par défaut si non précisé."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [30.0, 0.0, 0.0]

        # Appel SANS spécifier le degré
        pts = BezierCurve._default_control_points(coords_a, coords_b)

        # Le degré par défaut étant 3, on s'attend à 3 + 1 = 4 points
        expected_pts = [
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [20.0, 0.0, 0.0],
            [30.0, 0.0, 0.0]
        ]
        self.assertEqual(len(pts), 4)
        self.assertEqual(pts, expected_pts)

    def test_default_control_points_distribution(self):
        """Test la répartition spatiale uniforme des points générés par défaut."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [10.0, 0.0, 0.0]
        degree = 2

        # Exécution de la méthode statique
        pts = BezierCurve._default_control_points(coords_a, coords_b, degree)

        # On s'attend à 3 points : le point A, le point milieu, et le point B
        expected_pts = [
            [0.0, 0.0, 0.0],
            [5.0, 0.0, 0.0],
            [10.0, 0.0, 0.0]
        ]
        self.assertEqual(pts, expected_pts)

    def test_default_control_points_count(self):
        """Test que le nombre de points générés correspond toujours au degré + 1."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [10.0, 10.0, 10.0]

        # On vérifie pour plusieurs degrés différents
        for degree in [1, 3, 5, 10]:
            pts = BezierCurve._default_control_points(coords_a, coords_b, degree)
            self.assertEqual(len(pts), degree + 1)

    def test_default_control_points_degree_zero(self):
        """Test le cas limite où le degré de la courbe est 0."""
        coords_a = [1.0, 2.0, 3.0]
        coords_b = [4.0, 5.0, 6.0]

        pts = BezierCurve._default_control_points(coords_a, coords_b, degree=0)

        # Pour un degré 0, il ne doit y avoir qu'un seul point (le point A)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0], coords_a)

    @patch('bot.core.curve.nurbslib')
    def test_get_render_data(self, mock_nurbslib):
        """Test la structure et le contenu du dictionnaire de rendu (utilisé par le viewer)."""
        tag = "42"
        control_points = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
        degree = 1

        # Résultat simulé de l'évaluation de la courbe par le moteur
        mock_curve_eval = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [1.0, 1.0, 1.0]]

        # Configuration du mock
        mock_engine_instance = MagicMock()
        mock_engine_instance.get_control_points.return_value = control_points
        mock_engine_instance.get_degree.return_value = degree
        mock_engine_instance.evaluate.return_value = mock_curve_eval
        mock_nurbslib.PyBezierCurve.return_value = mock_engine_instance

        # Création et récupération des données
        curve = BezierCurve(tag, control_points, degree)
        data = curve.get_render_data()

        # Vérification de la présence de toutes les clés nécessaires
        self.assertIn('tag', data)
        self.assertIn('control_points', data)
        self.assertIn('degree', data)
        self.assertIn('curve', data)

        # Vérification des valeurs
        self.assertEqual(data['tag'], "42")
        self.assertEqual(data['control_points'], control_points)
        self.assertEqual(data['degree'], degree)
        self.assertEqual(data['curve'], mock_curve_eval)

        # Vérification que le moteur a bien été sollicité pour générer 100 points
        mock_engine_instance.evaluate.assert_called_once_with(100, False)


if __name__ == '__main__':
    unittest.main()
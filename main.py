import bot
import math

if __name__ == '__main__':
    # 1. Chargement de la géométrie
    model = bot.CADModel()
    model.open("data/profil_1.geo")

    # 2. Lancement du visualiseur
    viewer = bot.Viewer()
    viewer.connect(model).run()

    # --- INITIALISATION DU HUD ---
    viewer.set_hud_text("Prêt. Survolez ou cliquez sur les courbes.")

    # --- GESTION DU SURVOL (HOVERING) ---
    last_hovered = None  # On crée une variable pour mémoriser la courbe

    def on_hover(tag):
        global last_hovered

        if tag is not None:
            # Si on passe directement d'une courbe à une autre, on nettoie la précédente
            if last_hovered is not None and last_hovered != tag:
                viewer.highlight_curve(last_hovered, [1, 1, 1, 1])

            viewer.set_hud_text(f"Survol de la courbe {tag}...")
            viewer.highlight_curve(tag, [1, 0, 0, 1]) # Rouge
            last_hovered = tag # On mémorise

        else:
            # Si on survole le vide, on remet la dernière courbe connue en blanc
            if last_hovered is not None:
                viewer.highlight_curve(last_hovered, [1, 1, 1, 1])
                viewer.set_hud_text("Prêt. Survolez ou cliquez sur les courbes.")
                last_hovered = None

    viewer.on_hover = on_hover

    # --- GESTION DU CLIC (PICKING) ---
    def on_click(coords):
        courbes = model.get_curve_tags()

        courbe_la_plus_proche = None
        point_sur_courbe = None
        distance_min = float('inf') # Initialise à l'infini

        # Parcourir toutes les courbes pour trouver la plus proche du clic
        for tag in courbes:
            try:
                # Trouve le point exact sur la courbe 'tag'
                pt = model.getClosestPoint(1, tag, coords)

                # Calcule la distance en 3D (Théorème de Pythagore)
                dist = math.sqrt((pt[0]-coords[0])**2 + (pt[1]-coords[1])**2 + (pt[2]-coords[2])**2)

                # Si c'est la distance la plus petite trouvée jusqu'à présent, on la sauvegarde
                if dist < distance_min:
                    distance_min = dist
                    courbe_la_plus_proche = tag
                    point_sur_courbe = pt
            except Exception:
                # Ignore si une erreur survient sur une courbe spécifique
                continue

        # Si on a trouvé une courbe valide
        if courbe_la_plus_proche is not None:
            extremites = model.get_end_points(courbe_la_plus_proche)

            # Mise à jour du HUD
            viewer.set_hud_text(f"Courbe {courbe_la_plus_proche} fixée ! Extremités : {extremites}")

            # Surbrillance permanente suite au clic (rouge)
            viewer.highlight_curve(courbe_la_plus_proche, [1.0, 0.0, 0.0, 1.0])

            # Feedback visuel : on ajoute un point sur la courbe
            model.add_point(point_sur_courbe)

    # On branche notre fonction au clic
    viewer.on_pick = on_click

    # 3. Boucle principale du terminal
    input("\nMode interactif actif. Appuyez sur 'Entrée' pour quitter...\n")

    # 4. Nettoyage
    viewer.stop()
    model.finalize()
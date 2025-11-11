"""
FIFA World Coefficients Auto-Updater
Ajuste automatiquement les coefficients FIFA selon les matchs réels (sans API externe).
"""
import json
import os

DATA_PATH = "/app/data/world_coeffs.json"

def adjust_coeffs_from_results(results_file="/app/data/real_scores.jsonl"):
    """
    Ajuste automatiquement les coefficients FIFA selon les matchs réels (sans API externe).
    
    Args:
        results_file: Chemin vers le fichier JSONL des scores réels
    
    Returns:
        dict: Coefficients mis à jour
    """
    # Créer le fichier de base si nécessaire
    if not os.path.exists(DATA_PATH):
        print("[FIFA] Création du fichier de coefficients...")
        base = {
            "France": 1.28, "Brazil": 1.27, "Argentina": 1.26,
            "England": 1.25, "Germany": 1.24, "Spain": 1.22,
            "Portugal": 1.21, "Italy": 1.20, "Croatia": 1.18,
            "Netherlands": 1.17, "Belgium": 1.16, "Uruguay": 1.15
        }
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(base, f, indent=2, ensure_ascii=False)

    # Charger les coefficients actuels
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        coeffs = json.load(f)

    # Vérifier que le fichier de résultats existe
    if not os.path.exists(results_file):
        print("[FIFA] Aucun fichier de résultats réels trouvé, skip.")
        return coeffs

    # Charger les derniers matchs
    with open(results_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated_count = 0
    
    # Traiter les 300 derniers matchs seulement
    for line in lines[-300:]:
        try:
            match = json.loads(line)
            
            # Ne traiter que les matchs internationaux
            if not match.get("is_international"):
                continue

            h = match.get("home_team")
            a = match.get("away_team")
            hs = match.get("home_score")
            as_ = match.get("away_score")
            
            # Vérifier que les données sont valides
            if not all([h, a, hs is not None, as_ is not None]):
                continue
                
        except Exception as e:
            continue

        # Initialiser les coefficients si nécessaire
        coeffs.setdefault(h, 1.0)
        coeffs.setdefault(a, 1.0)

        # Ajustements simples basés sur les résultats
        if hs > as_ and coeffs[a] > coeffs[h]:
            # L'équipe à domicile gagne contre une équipe mieux classée
            coeffs[h] += 0.005
            coeffs[a] -= 0.005
            updated_count += 1
        elif as_ > hs and coeffs[h] > coeffs[a]:
            # L'équipe à l'extérieur gagne contre une équipe mieux classée
            coeffs[a] += 0.005
            coeffs[h] -= 0.005
            updated_count += 1

        # Bornes de stabilité (0.80 - 1.35)
        coeffs[h] = max(0.80, min(1.35, coeffs[h]))
        coeffs[a] = max(0.80, min(1.35, coeffs[a]))

    # Sauvegarder les coefficients mis à jour
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(coeffs, f, indent=2, ensure_ascii=False)
    
    print(f"[FIFA] Mise à jour automatique terminée. {updated_count} ajustements effectués.")
    return coeffs


if __name__ == "__main__":
    adjust_coeffs_from_results()

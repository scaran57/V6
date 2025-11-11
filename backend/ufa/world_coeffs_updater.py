"""
FIFA World Coefficients Auto-Updater
Ajuste automatiquement les coefficients FIFA selon les matchs réels (sans API externe).
"""
import json
import os
import time

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
            "updated": int(os.time.time()),
            "source": "auto_adjusted",
            "teams": {
                "France": {"rank": 1, "coeff": 1.28},
                "Brazil": {"rank": 2, "coeff": 1.27},
                "Argentina": {"rank": 3, "coeff": 1.26},
                "England": {"rank": 4, "coeff": 1.25},
                "Germany": {"rank": 5, "coeff": 1.24},
                "Spain": {"rank": 6, "coeff": 1.22},
                "Portugal": {"rank": 7, "coeff": 1.21},
                "Italy": {"rank": 8, "coeff": 1.20},
                "Croatia": {"rank": 9, "coeff": 1.18},
                "Netherlands": {"rank": 10, "coeff": 1.17},
                "Belgium": {"rank": 11, "coeff": 1.16},
                "Uruguay": {"rank": 12, "coeff": 1.15}
            }
        }
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(base, f, indent=2, ensure_ascii=False)

    # Charger les coefficients actuels
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Gérer les deux formats possibles
    if "teams" in data:
        # Format avec métadonnées
        coeffs = {team: info.get("coeff", 1.0) for team, info in data["teams"].items()}
        has_metadata = True
    else:
        # Format simple
        coeffs = data
        has_metadata = False

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
    if has_metadata:
        # Reconstruire le format avec métadonnées
        teams_data = {}
        for i, (team, coeff) in enumerate(sorted(coeffs.items(), key=lambda x: -x[1]), 1):
            teams_data[team] = {
                "rank": i,
                "coeff": round(coeff, 3)
            }
        
        output = {
            "updated": int(os.path.getctime(DATA_PATH) if os.path.exists(DATA_PATH) else 0),
            "source": "auto_adjusted",
            "teams": teams_data
        }
    else:
        # Format simple
        output = coeffs
    
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"[FIFA] Mise à jour automatique terminée. {updated_count} ajustements effectués sur {len(coeffs)} équipes.")
    return coeffs


if __name__ == "__main__":
    adjust_coeffs_from_results()

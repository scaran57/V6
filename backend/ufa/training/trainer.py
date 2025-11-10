"""
UFA Training System - Apprentissage par ligue
Entraîne le système UFA en comparant les prédictions avec les scores réels.
"""
import json
import numpy as np
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, '/app/backend')
from ufa.analyzer import UFAAnalyzer

DATA_PATH = Path("/app/data/real_scores.jsonl")
STATE_PATH = Path("/app/backend/ufa/training/state.json")
HISTORY_PATH = Path("/app/data/ufa_training_history.jsonl")

def load_real_scores():
    """
    Charge tous les scores réels enregistrés.
    
    Returns:
        Liste des matchs avec scores réels
    """
    if not DATA_PATH.exists():
        return []
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def save_state(state):
    """
    Sauvegarde l'état d'apprentissage.
    
    Args:
        state: Dictionnaire contenant l'état complet
    """
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    
    print(f"[UFA Training] État sauvegardé: {STATE_PATH}")

def save_training_history(history_entry):
    """
    Enregistre l'historique d'entraînement.
    
    Args:
        history_entry: Entrée d'historique à ajouter
    """
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")

def calculate_loss(predicted_distribution, real_score):
    """
    Calcule la perte (loss) entre la prédiction et le score réel.
    Utilise la log-loss (cross-entropy).
    
    Args:
        predicted_distribution: Dict {score: probabilité}
        real_score: Score réel au format "X-Y"
        
    Returns:
        float: Valeur de la perte
    """
    # Récupérer la probabilité prédite pour le score réel
    prob = predicted_distribution.get(real_score, 1e-6)  # Éviter log(0)
    
    # Log-loss
    loss = -np.log(max(prob, 1e-6))
    
    return float(loss)

def train_from_real_matches():
    """
    Entraîne le système UFA à partir des scores réels enregistrés.
    Appelé automatiquement chaque nuit par le scheduler.
    
    Returns:
        Dict: Résumé de l'entraînement
    """
    print("=" * 70)
    print(f"[UFA Training] Démarrage apprentissage : {datetime.now().isoformat()}")
    print("=" * 70)
    
    # Charger les scores réels
    real_matches = load_real_scores()
    
    if not real_matches:
        print("[UFA Training] ⚠️ Aucun score réel trouvé.")
        return {
            "status": "no_data",
            "message": "Aucun score réel disponible pour l'entraînement"
        }
    
    print(f"[UFA Training] 📊 {len(real_matches)} matchs à analyser")
    
    # Initialiser l'analyseur UFA
    analyzer = UFAAnalyzer()
    
    # Statistiques par ligue
    league_stats = {}
    total_loss = 0
    matches_processed = 0
    
    for match in real_matches:
        try:
            league = match.get("league", "Unknown")
            home_team = match.get("home_team", "Unknown")
            away_team = match.get("away_team", "Unknown")
            home_goals = match.get("home_goals", 0)
            away_goals = match.get("away_goals", 0)
            
            # Préparer les données du match
            match_data = {
                "home_team": home_team,
                "away_team": away_team,
                "league": league,
                "home_coef": match.get("home_coef", 1.0),
                "away_coef": match.get("away_coef", 1.0)
            }
            
            # Obtenir les cotes si disponibles
            extracted_scores = match.get("extracted_scores", None)
            
            # Prédire la distribution
            predicted = analyzer.predict_score_distribution(
                match_data,
                extracted_scores=extracted_scores,
                diff_expected=match.get("diff_expected", 1.0)
            )
            
            # Score réel
            real_score = f"{home_goals}-{away_goals}"
            
            # Calculer la perte
            loss = calculate_loss(predicted, real_score)
            
            # Accumuler les statistiques par ligue
            if league not in league_stats:
                league_stats[league] = {
                    "losses": [],
                    "matches": 0,
                    "correct_predictions": 0
                }
            
            league_stats[league]["losses"].append(loss)
            league_stats[league]["matches"] += 1
            
            # Vérifier si la prédiction était correcte
            most_likely_score = max(predicted, key=predicted.get)
            if most_likely_score == real_score:
                league_stats[league]["correct_predictions"] += 1
            
            total_loss += loss
            matches_processed += 1
            
        except Exception as e:
            print(f"[UFA Training] ⚠️ Erreur traitement match: {e}")
            continue
    
    # Calculer les moyennes par ligue
    league_avg_loss = {}
    for lg, stats in league_stats.items():
        if stats["losses"]:
            avg_loss = float(np.mean(stats["losses"]))
            league_avg_loss[lg] = avg_loss
            accuracy = stats["correct_predictions"] / stats["matches"] * 100
            print(f"[UFA Training] 📊 {lg}: Loss={avg_loss:.3f}, Accuracy={accuracy:.1f}% ({stats['matches']} matchs)")
    
    # Ajustement automatique des priors
    new_priors = analyzer.adjust_priors(league_avg_loss)
    
    # Préparer l'état à sauvegarder
    state = {
        "timestamp": datetime.now().isoformat(),
        "matches_processed": matches_processed,
        "avg_loss": league_avg_loss,
        "global_avg_loss": float(total_loss / matches_processed) if matches_processed > 0 else 0,
        "priors": new_priors,
        "league_stats": {
            lg: {
                "avg_loss": league_avg_loss.get(lg, 0),
                "matches": stats["matches"],
                "accuracy": stats["correct_predictions"] / stats["matches"] * 100
            }
            for lg, stats in league_stats.items()
        }
    }
    
    # Sauvegarder l'état
    save_state(state)
    
    # Enregistrer dans l'historique
    save_training_history(state)
    
    print("=" * 70)
    print(f"[UFA Training] ✅ Apprentissage terminé")
    print(f"[UFA Training] 📈 Matchs traités: {matches_processed}")
    print(f"[UFA Training] 📉 Perte moyenne globale: {state['global_avg_loss']:.3f}")
    print("=" * 70)
    
    return state

if __name__ == "__main__":
    # Test du système de training
    result = train_from_real_matches()
    print("\n📊 Résultat de l'entraînement:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

def train_model(dataset_path, save_path=None):
    """
    Fonction wrapper pour l'entraînement du modèle UFA.
    Compatible avec force_retrain_all.py
    
    Args:
        dataset_path: Chemin vers le dataset d'entraînement (training_set.jsonl)
        save_path: Chemin pour sauvegarder le modèle (optionnel)
    
    Returns:
        État du modèle entraîné
    """
    print(f"[UFA Training] Dataset fourni: {dataset_path}")
    if save_path:
        print(f"[UFA Training] Modèle sera sauvegardé dans: {save_path}")
    
    # Pour l'instant, utiliser l'entraînement standard
    # À terme, on peut utiliser le dataset_path pour un entraînement personnalisé
    result = train_from_real_matches()
    
    if save_path and result.get("status") != "no_data":
        # Sauvegarder l'état du modèle dans le chemin spécifié
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[UFA Training] ✅ Modèle sauvegardé: {save_path}")
    
    return result


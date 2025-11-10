#!/usr/bin/env python3
# /app/backend/ufa/performance_tracker.py
"""
Système d'évaluation des performances du modèle UFA par ligue.
Génère un rapport de performance utilisé pour ajuster les coefficients.
"""
import os
import json
from datetime import datetime
from pathlib import Path

PERF_FILE = "/app/data/performance_summary.json"
LOG_FILE = "/app/logs/performance_eval.log"

def log(msg):
    """Log un message."""
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {msg}\n")
    print(msg)

def load_training_data(dataset_path):
    """
    Charge le dataset d'entraînement.
    
    Args:
        dataset_path: Chemin vers training_set.jsonl
        
    Returns:
        Liste des matchs
    """
    if not os.path.exists(dataset_path):
        return []
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def evaluate_model(dataset_path):
    """
    Évalue les performances du modèle par ligue.
    
    Args:
        dataset_path: Chemin vers training_set.jsonl
        
    Returns:
        Dict: Statistiques de performance par ligue
    """
    log("=" * 70)
    log("📊 ÉVALUATION DES PERFORMANCES DU MODÈLE")
    log("=" * 70)
    
    matches = load_training_data(dataset_path)
    
    if not matches:
        log("❌ Aucune donnée d'entraînement trouvée")
        return {}
    
    log(f"📥 {len(matches)} matchs chargés")
    
    # Statistiques par ligue
    league_stats = {}
    
    for match in matches:
        league = match.get("league", "Unknown")
        predicted = match.get("predicted", {})
        actual = match.get("actual", {})
        
        # Initialiser les stats de la ligue si nécessaire
        if league not in league_stats:
            league_stats[league] = {
                "total": 0,
                "correct": 0,
                "avg_error": []
            }
        
        league_stats[league]["total"] += 1
        
        # Vérifier si la prédiction était correcte
        pred_home = predicted.get("home")
        pred_away = predicted.get("away")
        actual_home = actual.get("home_goals") or actual.get("home")
        actual_away = actual.get("away_goals") or actual.get("away")
        
        if pred_home is not None and pred_away is not None and actual_home is not None and actual_away is not None:
            # Prédiction exacte
            if pred_home == actual_home and pred_away == actual_away:
                league_stats[league]["correct"] += 1
            
            # Erreur absolue moyenne
            error = abs(pred_home - actual_home) + abs(pred_away - actual_away)
            league_stats[league]["avg_error"].append(error)
    
    # Calculer les métriques finales
    performance_summary = {}
    
    for league, stats in league_stats.items():
        accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        avg_error = sum(stats["avg_error"]) / len(stats["avg_error"]) if stats["avg_error"] else 0
        
        performance_summary[league] = {
            "accuracy": round(accuracy, 1),
            "matches": stats["total"],
            "correct": stats["correct"],
            "avg_error": round(avg_error, 2)
        }
        
        log(f"📈 {league}: {accuracy:.1f}% accuracy ({stats['correct']}/{stats['total']} matchs), erreur moyenne: {avg_error:.2f}")
    
    # Sauvegarder le résumé
    Path(PERF_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(PERF_FILE, "w", encoding="utf-8") as f:
        json.dump(performance_summary, f, indent=2, ensure_ascii=False)
    
    log(f"💾 Rapport sauvegardé: {PERF_FILE}")
    log("=" * 70)
    
    return performance_summary

if __name__ == "__main__":
    # Test du système d'évaluation
    result = evaluate_model("/app/data/training_set.jsonl")
    print("\n📊 Résumé des performances:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

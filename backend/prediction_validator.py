# /app/backend/prediction_validator.py
"""
Module de validation des prédictions
Compare les prédictions du système avec les résultats réels des matchs
Génère des métriques de performance (accuracy, MAE, RMSE)
"""
import json
import os
import datetime
import math
import statistics
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration des chemins
DATA_DIR = Path("/app/data/validation")
PREDICTIONS_FILE = Path("/app/data/predictions.jsonl")
RESULTS_FILE = Path("/app/data/results.jsonl")
REPORT_FILE = DATA_DIR / "validation_report.json"
HISTORY_FILE = DATA_DIR / "validation_history.jsonl"

def load_jsonl(file_path):
    """Charge un fichier JSONL (une entrée JSON par ligne)"""
    if not os.path.exists(file_path):
        logger.info(f"Fichier {file_path} n'existe pas encore")
        return []
    
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"Ligne invalide dans {file_path}: {e}")
    return data

def save_json(file_path, data):
    """Sauvegarde des données en JSON"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Rapport sauvegardé dans {file_path}")

def append_jsonl(file_path, data):
    """Ajoute une entrée dans un fichier JSONL"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def parse_score(score_str):
    """
    Parse un score au format "X-Y" en tuple (X, Y)
    Gère aussi les formats alternatifs: "X:Y", "X Y"
    """
    if isinstance(score_str, (list, tuple)) and len(score_str) == 2:
        return tuple(score_str)
    
    if isinstance(score_str, str):
        # Remplacer les séparateurs possibles
        score_str = score_str.replace(':', '-').replace(' ', '-')
        parts = score_str.split('-')
        if len(parts) == 2:
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                pass
    
    logger.warning(f"Format de score invalide: {score_str}")
    return None

def calculate_metrics(predictions, results_dict):
    """
    Calcule les métriques de validation
    
    Args:
        predictions: Liste des prédictions
        results_dict: Dictionnaire des résultats réels {match_id: result}
    
    Returns:
        dict: Métriques calculées
    """
    correct = 0
    total = 0
    diffs = []
    exact_matches = []
    goal_diff_matches = []
    outcome_matches = []  # 1X2 (victoire domicile, nul, victoire extérieur)
    
    for pred in predictions:
        match_id = pred.get("match_id")
        if not match_id or match_id not in results_dict:
            continue
        
        total += 1
        
        # Parser les scores
        pred_score = parse_score(pred.get("predicted_score", "0-0"))
        real_score = parse_score(results_dict[match_id].get("final_score", "0-0"))
        
        if not pred_score or not real_score:
            continue
        
        # Score exact
        if pred_score == real_score:
            correct += 1
            exact_matches.append(match_id)
        
        # Différence de buts
        pred_diff = pred_score[0] - pred_score[1]
        real_diff = real_score[0] - real_score[1]
        if pred_diff == real_diff:
            goal_diff_matches.append(match_id)
        
        # Résultat (1X2)
        pred_outcome = "1" if pred_diff > 0 else ("X" if pred_diff == 0 else "2")
        real_outcome = "1" if real_diff > 0 else ("X" if real_diff == 0 else "2")
        if pred_outcome == real_outcome:
            outcome_matches.append(match_id)
        
        # Différence absolue (pour MAE et RMSE)
        diff = abs(pred_score[0] - real_score[0]) + abs(pred_score[1] - real_score[1])
        diffs.append(diff)
    
    if total == 0:
        return {
            "status": "no_matches",
            "matches_tested": 0,
            "correct_predictions": 0,
            "accuracy": 0.0,
            "outcome_accuracy": 0.0,
            "goal_diff_accuracy": 0.0,
            "mae": 0.0,
            "rmse": 0.0
        }
    
    accuracy = round(correct / total, 3)
    outcome_accuracy = round(len(outcome_matches) / total, 3)
    goal_diff_accuracy = round(len(goal_diff_matches) / total, 3)
    mae = round(statistics.mean(diffs), 3) if diffs else 0.0
    rmse = round(math.sqrt(statistics.mean([d**2 for d in diffs])), 3) if diffs else 0.0
    
    return {
        "status": "success",
        "matches_tested": total,
        "correct_predictions": correct,
        "accuracy": accuracy,
        "outcome_accuracy": outcome_accuracy,
        "goal_diff_accuracy": goal_diff_accuracy,
        "mae": mae,
        "rmse": rmse,
        "exact_matches": len(exact_matches),
        "outcome_matches": len(outcome_matches),
        "goal_diff_matches": len(goal_diff_matches)
    }

def validate_predictions(days_back=7, save_report=True):
    """
    Valide les prédictions sur une période donnée
    
    Args:
        days_back: Nombre de jours à analyser
        save_report: Si True, sauvegarde le rapport
    
    Returns:
        dict: Rapport de validation
    """
    logger.info(f"🔍 Début de la validation des prédictions (derniers {days_back} jours)")
    
    # Charger les données
    predictions = load_jsonl(PREDICTIONS_FILE)
    results = load_jsonl(RESULTS_FILE)
    
    if not predictions:
        logger.warning("⚠️ Aucune prédiction trouvée")
        return {
            "status": "no_data",
            "message": "Aucune prédiction enregistrée",
            "accuracy": 0.0
        }
    
    if not results:
        logger.warning("⚠️ Aucun résultat réel trouvé")
        return {
            "status": "no_data",
            "message": "Aucun résultat réel enregistré",
            "accuracy": 0.0
        }
    
    # Filtrer sur les derniers jours
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days_back)
    
    filtered_predictions = []
    for p in predictions:
        try:
            timestamp = datetime.datetime.fromisoformat(p.get("timestamp", ""))
            if timestamp >= cutoff:
                filtered_predictions.append(p)
        except (ValueError, TypeError):
            continue
    
    logger.info(f"📊 {len(filtered_predictions)} prédictions dans la période")
    
    # Créer un dictionnaire des résultats
    results_dict = {r.get("match_id"): r for r in results if r.get("match_id")}
    logger.info(f"📊 {len(results_dict)} résultats réels disponibles")
    
    # Calculer les métriques
    metrics = calculate_metrics(filtered_predictions, results_dict)
    
    # Ajouter des métadonnées
    report = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "period_days": days_back,
        "predictions_total": len(predictions),
        "predictions_period": len(filtered_predictions),
        "results_available": len(results_dict),
        **metrics
    }
    
    # Sauvegarder le rapport
    if save_report:
        save_json(REPORT_FILE, report)
        append_jsonl(HISTORY_FILE, report)
        logger.info(f"✅ Rapport de validation généré: accuracy={metrics.get('accuracy', 0):.1%}")
    
    return report

def get_latest_report():
    """Récupère le dernier rapport de validation"""
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "no_report", "message": "Aucun rapport de validation disponible"}

def get_validation_history(limit=30):
    """
    Récupère l'historique des validations
    
    Args:
        limit: Nombre maximum d'entrées à retourner
    
    Returns:
        list: Historique des validations
    """
    history = load_jsonl(HISTORY_FILE)
    # Trier par date décroissante et limiter
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return history[:limit]

def add_prediction(match_id, home_team, away_team, predicted_score, confidence=None, league=None):
    """
    Enregistre une nouvelle prédiction
    
    Args:
        match_id: ID unique du match
        home_team: Équipe domicile
        away_team: Équipe extérieur
        predicted_score: Score prédit (tuple ou string "X-Y")
        confidence: Confiance de la prédiction (optionnel)
        league: Ligue du match (optionnel)
    """
    prediction = {
        "match_id": match_id,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "home_team": home_team,
        "away_team": away_team,
        "predicted_score": predicted_score if isinstance(predicted_score, str) else f"{predicted_score[0]}-{predicted_score[1]}",
        "confidence": confidence,
        "league": league
    }
    
    append_jsonl(PREDICTIONS_FILE, prediction)
    logger.info(f"✅ Prédiction enregistrée: {match_id} → {predicted_score}")

def add_result(match_id, final_score, home_team=None, away_team=None, league=None):
    """
    Enregistre le résultat réel d'un match
    
    Args:
        match_id: ID unique du match
        final_score: Score final (tuple ou string "X-Y")
        home_team: Équipe domicile (optionnel)
        away_team: Équipe extérieur (optionnel)
        league: Ligue du match (optionnel)
    """
    result = {
        "match_id": match_id,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "final_score": final_score if isinstance(final_score, str) else f"{final_score[0]}-{final_score[1]}",
        "home_team": home_team,
        "away_team": away_team,
        "league": league
    }
    
    append_jsonl(RESULTS_FILE, result)
    logger.info(f"✅ Résultat enregistré: {match_id} → {final_score}")

def cleanup_old_data(days_to_keep=30):
    """
    Nettoie les anciennes données (> days_to_keep jours)
    
    Args:
        days_to_keep: Nombre de jours à conserver
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days_to_keep)
    
    for file_path in [PREDICTIONS_FILE, RESULTS_FILE, HISTORY_FILE]:
        if not os.path.exists(file_path):
            continue
        
        data = load_jsonl(file_path)
        filtered = []
        
        for entry in data:
            try:
                timestamp = datetime.datetime.fromisoformat(entry.get("timestamp", ""))
                if timestamp >= cutoff:
                    filtered.append(entry)
            except (ValueError, TypeError):
                # Garder les entrées sans timestamp valide
                filtered.append(entry)
        
        # Réécrire le fichier
        with open(file_path, "w", encoding="utf-8") as f:
            for entry in filtered:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        logger.info(f"🧹 Nettoyage {file_path}: {len(data)} → {len(filtered)} entrées")

if __name__ == "__main__":
    # Test du module
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🔍 Test du module de validation")
    
    # Créer des données de test si les fichiers n'existent pas
    if not os.path.exists(PREDICTIONS_FILE):
        print("📝 Création de prédictions de test...")
        for i in range(5):
            add_prediction(
                match_id=f"test_match_{i}",
                home_team=f"Team A{i}",
                away_team=f"Team B{i}",
                predicted_score=f"{i}-{i%2}",
                confidence=0.7 + (i * 0.05),
                league="TestLeague"
            )
    
    if not os.path.exists(RESULTS_FILE):
        print("📝 Création de résultats de test...")
        for i in range(5):
            add_result(
                match_id=f"test_match_{i}",
                final_score=f"{i}-{(i+1)%3}",
                home_team=f"Team A{i}",
                away_team=f"Team B{i}",
                league="TestLeague"
            )
    
    # Exécuter la validation
    print("\n🔄 Exécution de la validation...")
    report = validate_predictions(days_back=30)
    
    print("\n📊 RAPPORT DE VALIDATION:")
    print(json.dumps(report, indent=2))
    
    print("\n✅ Test terminé")

"""
Performance Logger
Utilitaire pour enregistrer les performances du modèle UFAv3
"""
import json
import datetime
import os

PERF_HISTORY = "/app/logs/performance_history.jsonl"
PERF_SUMMARY = "/app/logs/performance_summary.json"


def log_performance(accuracy: float, matches: int = 0, mode: str = "train"):
    """
    Enregistre une performance dans l'historique et met à jour le résumé.
    
    Args:
        accuracy: Précision du modèle (0-100)
        matches: Nombre de matchs analysés
        mode: Mode d'entraînement ('train', 'incremental', 'eval')
    """
    try:
        # Enregistrer dans l'historique
        perf_record = {
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "accuracy": round(accuracy, 2),
            "matches": matches,
            "mode": mode
        }
        
        with open(PERF_HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(perf_record, ensure_ascii=False) + "\n")
        
        # Mettre à jour le résumé
        update_summary(accuracy, matches)
        
        print(f"✅ Performance enregistrée: {accuracy}% (mode: {mode})")
        
    except Exception as e:
        print(f"❌ Erreur enregistrement performance: {e}")


def update_summary(accuracy: float, matches: int):
    """
    Met à jour le fichier de résumé de performance.
    
    Args:
        accuracy: Précision du modèle
        matches: Nombre de matchs
    """
    try:
        # Charger le résumé existant
        if os.path.exists(PERF_SUMMARY):
            with open(PERF_SUMMARY, "r", encoding="utf-8") as f:
                summary = json.load(f)
        else:
            summary = {
                "avg_accuracy": 0.0,
                "matches": 0,
                "last_update": None,
                "history_count": 0
            }
        
        # Calculer la moyenne mobile (avec poids sur les dernières valeurs)
        if summary["avg_accuracy"] > 0:
            # Moyenne pondérée : 70% ancienne valeur, 30% nouvelle
            summary["avg_accuracy"] = round(
                summary["avg_accuracy"] * 0.7 + accuracy * 0.3, 
                2
            )
        else:
            summary["avg_accuracy"] = accuracy
        
        summary["matches"] = matches
        summary["last_update"] = datetime.datetime.utcnow().isoformat()
        summary["history_count"] = summary.get("history_count", 0) + 1
        
        # Sauvegarder
        with open(PERF_SUMMARY, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
    except Exception as e:
        print(f"⚠️  Erreur mise à jour résumé: {e}")


def get_recent_performance(count: int = 10):
    """
    Récupère les N dernières performances.
    
    Args:
        count: Nombre de performances à récupérer
    
    Returns:
        list: Liste des performances récentes
    """
    if not os.path.exists(PERF_HISTORY):
        return []
    
    try:
        with open(PERF_HISTORY, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        performances = []
        for line in lines[-count:]:
            try:
                performances.append(json.loads(line))
            except Exception:
                continue
        
        return performances
        
    except Exception as e:
        print(f"❌ Erreur lecture performances: {e}")
        return []


def get_performance_stats():
    """
    Calcule les statistiques de performance.
    
    Returns:
        dict: Statistiques (min, max, avg, trend)
    """
    performances = get_recent_performance(30)
    
    if not performances:
        return {
            "min": 0.0,
            "max": 0.0,
            "avg": 0.0,
            "trend": "unknown",
            "count": 0
        }
    
    accuracies = [p["accuracy"] for p in performances]
    
    # Calculer le trend (dernières 5 vs 5 précédentes)
    trend = "stable"
    if len(accuracies) >= 10:
        recent_avg = sum(accuracies[-5:]) / 5
        previous_avg = sum(accuracies[-10:-5]) / 5
        if recent_avg > previous_avg + 1:
            trend = "improving"
        elif recent_avg < previous_avg - 1:
            trend = "declining"
    
    return {
        "min": round(min(accuracies), 2),
        "max": round(max(accuracies), 2),
        "avg": round(sum(accuracies) / len(accuracies), 2),
        "trend": trend,
        "count": len(performances)
    }


if __name__ == "__main__":
    # Test
    log_performance(75.5, matches=100, mode="test")
    stats = get_performance_stats()
    print(f"Stats: {stats}")

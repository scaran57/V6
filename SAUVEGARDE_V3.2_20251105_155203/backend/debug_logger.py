"""
Module de débogage pour surveiller l'OCR et les calculs de prédiction
"""
import datetime
import logging

logger = logging.getLogger(__name__)

# Active ou désactive la surveillance
DEBUG_MODE = True  # False pour production

def log_debug(stage, data):
    """
    Logger lisible pour suivre l'évolution OCR + Calcul
    Affiche dans les logs backend de manière structurée
    """
    if not DEBUG_MODE:
        return
    
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    separator = "=" * 60
    
    logger.info(f"\n{separator}")
    logger.info(f"🔍 [DEBUG - {stage}] {timestamp}")
    logger.info(separator)
    
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, float):
                logger.info(f"  {k}: {v:.4f}")
            else:
                logger.info(f"  {k}: {v}")
    elif isinstance(data, list):
        for idx, x in enumerate(data):
            if isinstance(x, dict):
                logger.info(f"  [{idx}] {x}")
            else:
                logger.info(f"  [{idx}] {x}")
    else:
        logger.info(f"  {data}")
    
    logger.info(separator)


def log_ocr_step(step_name, scores_count, sample_scores=None):
    """
    Log spécifique pour les étapes OCR
    """
    if not DEBUG_MODE:
        return
    
    data = {
        "Étape": step_name,
        "Scores détectés": scores_count
    }
    
    if sample_scores and len(sample_scores) > 0:
        data["Échantillon (3 premiers)"] = sample_scores[:3]
    
    log_debug("OCR", data)


def log_prediction_step(step_name, probabilities, top_n=5):
    """
    Log spécifique pour les étapes de prédiction
    """
    if not DEBUG_MODE:
        return
    
    sorted_probs = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
    top_probs = dict(sorted_probs[:top_n])
    
    data = {
        "Étape": step_name,
        "Scores analysés": len(probabilities),
        f"Top {top_n}": top_probs
    }
    
    log_debug("PRÉDICTION", data)


def log_balance_analysis(win_sum, lose_sum, draw_sum, balance_factor, draw_penalty):
    """
    Log spécifique pour l'analyse d'équilibre (nouveau calcul)
    """
    if not DEBUG_MODE:
        return
    
    data = {
        "Somme Victoires": f"{win_sum:.4f}",
        "Somme Défaites": f"{lose_sum:.4f}",
        "Somme Nuls": f"{draw_sum:.4f}",
        "Balance Factor": f"{balance_factor:.4f}",
        "Draw Penalty": f"{draw_penalty:.4f}",
        "Réduction nuls": f"{(1-draw_penalty)*100:.1f}%"
    }
    
    log_debug("ANALYSE ÉQUILIBRE", data)


def log_final_prediction(most_probable, probability, all_probabilities):
    """
    Log final avec le résultat de prédiction
    """
    if not DEBUG_MODE:
        return
    
    sorted_all = sorted(all_probabilities.items(), key=lambda x: x[1], reverse=True)
    top_5 = dict(sorted_all[:5])
    
    data = {
        "🏆 Score le plus probable": most_probable,
        "Probabilité": f"{probability:.2f}%",
        "Top 5 complet": top_5
    }
    
    log_debug("RÉSULTAT FINAL", data)

from math import exp
from learning import get_diff_expected
import logging

logger = logging.getLogger(__name__)

def predict_score(scores):
    """
    Prédit le score le plus probable basé sur les cotes extraites.
    Utilise un algorithme de pondération basé sur la différence de buts attendue.
    """
    if not scores:
        logger.warning("Aucune donnée pour la prédiction")
        return {"mostProbableScore": "Aucune donnée", "probabilities": {}}

    diffExpected = get_diff_expected()
    logger.info(f"Différence de buts attendue: {diffExpected}")
    
    # Calcul des probabilités brutes (inverse des cotes)
    raw_probs = {s["score"]: 1 / s["odds"] for s in scores}
    total_raw = sum(raw_probs.values())
    
    # Normalisation
    normalized = {k: v / total_raw for k, v in raw_probs.items()}
    logger.info(f"Probabilités normalisées: {normalized}")
    
    # Pondération basée sur la différence de buts attendue
    weighted = {}
    for score, p in normalized.items():
        parts = score.split("-")
        if len(parts) == 2 and all(x.isdigit() for x in parts):
            home, away = map(int, parts)
            diff = abs(away - home)
            
            # Ajustement de la différence attendue
            adjusted = diffExpected + 1 if diffExpected > 2 else diffExpected
            
            # Fonction de pondération gaussienne
            weight = exp(-0.4 * (diff - adjusted) ** 2)
            weighted[score] = p * weight
            logger.info(f"Score {score}: diff={diff}, weight={weight:.3f}, weighted_prob={p * weight:.3f}")
        else:
            # Pour "Autre" ou scores non reconnus
            weighted[score] = p
    
    # Normalisation finale
    total = sum(weighted.values())
    final_probs = {k: (v / total) * 100 for k, v in weighted.items()}
    
    # Score le plus probable
    most = max(final_probs, key=final_probs.get)
    
    logger.info(f"Score le plus probable: {most} ({final_probs[most]:.2f}%)")
    
    return {
        "mostProbableScore": most,
        "probabilities": {k: round(v, 2) for k, v in final_probs.items()}
    }
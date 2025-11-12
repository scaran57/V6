from math import exp
import math
from learning import get_diff_expected
import logging
from debug_logger import log_debug, log_prediction_step, log_balance_analysis, log_final_prediction

logger = logging.getLogger(__name__)

# === NOUVEAU: Import gestionnaire coefficients FIFA ===
try:
    from tools.fifa_ranking_manager import get_match_coefficients
    FIFA_COEFFICIENTS_ENABLED = True
    logger.info("✅ Coefficients FIFA activés")
except ImportError:
    FIFA_COEFFICIENTS_ENABLED = False
    logger.warning("⚠️ Coefficients FIFA désactivés (module non trouvé)")

def predict_score(scores, home_team=None, away_team=None, enable_fifa_coeffs=True):
    """
    Prédit le score le plus probable basé sur les cotes extraites.
    Algorithme amélioré avec ajustement dynamique du poids des scores nuls.
    """
    if not scores:
        logger.warning("Aucune donnée pour la prédiction")
        return {"mostProbableScore": "Aucune donnée", "probabilities": {}}

    diffExpected = get_diff_expected()
    logger.info(f"Différence de buts attendue: {diffExpected}")
    
    # Conversion des cotes -> probabilités brutes
    raw_probs = {}
    for entry in scores:
        try:
            score = entry["score"]
            odds = float(entry["odds"])
            if odds > 0:
                raw_probs[score] = 1.0 / odds
        except Exception as e:
            logger.warning(f"Erreur conversion score {entry}: {e}")
            continue

    if not raw_probs:
        return {"mostProbableScore": "Aucune donnée", "probabilities": {}}

    total_raw = sum(raw_probs.values()) or 1e-9
    norm_probs = {k: v / total_raw for k, v in raw_probs.items()}
    
    logger.info(f"Probabilités normalisées: {norm_probs}")
    
    # DEBUG: Log probabilités initiales
    log_prediction_step("Probabilités brutes (1/cotes)", norm_probs)

    # --- NOUVEAU: Analyse de l'équilibre global entre victoires et défaites ---
    win_sum = 0
    lose_sum = 0
    draw_sum = 0
    
    for k, v in norm_probs.items():
        if "-" in k and k != "Autre":
            try:
                parts = k.split("-")
                home = int(parts[0])
                away = int(parts[1])
                
                if home > away:
                    win_sum += v
                elif home < away:
                    lose_sum += v
                else:
                    draw_sum += v
            except:
                continue
    
    # Balance factor : mesure du déséquilibre des cotes (entre 0 et 1)
    balanceFactor = abs(win_sum - lose_sum) / (win_sum + lose_sum + 1e-9)
    logger.info(f"⚖️ Balance Factor: {balanceFactor:.3f} (win: {win_sum:.3f}, lose: {lose_sum:.3f}, draw: {draw_sum:.3f})")
    
    # Si très déséquilibré => on réduit le poids des scores nuls
    drawPenalty = 1.0 - (0.6 * balanceFactor)  # max réduction 60%
    if drawPenalty < 0.5:
        drawPenalty = 0.5  # jamais moins que 50% de leur poids initial
    
    logger.info(f"🎯 Draw Penalty: {drawPenalty:.3f} (réduction: {(1-drawPenalty)*100:.1f}%)")
    
    # DEBUG: Log analyse d'équilibre
    log_balance_analysis(win_sum, lose_sum, draw_sum, balanceFactor, drawPenalty)

    # --- Pondération selon diffExpected (système amélioré) ---
    weighted = {}
    for score, p in norm_probs.items():
        if "-" not in score or score == "Autre":
            weighted[score] = p
            continue
            
        try:
            parts = score.split("-")
            h = int(parts[0])
            a = int(parts[1])
        except (ValueError, IndexError):
            weighted[score] = p
            continue

        diff = abs(h - a)
        # Poids basé sur la courbe gaussienne centrée sur diffExpected
        weight = math.exp(-0.4 * (diff - diffExpected) ** 2)

        # Ajustement dynamique du nul
        if h == a:
            weighted[score] = p * weight * drawPenalty
            logger.info(f"Score {score}: diff={diff}, weight={weight:.3f}, drawPenalty={drawPenalty:.3f}, final={p * weight * drawPenalty:.4f}")
        else:
            weighted[score] = p * weight
            logger.info(f"Score {score}: diff={diff}, weight={weight:.3f}, final={p * weight:.4f}")

    # Normalisation finale
    total_weighted = sum(weighted.values()) or 1e-9
    final_probs = {k: (v / total_weighted) * 100.0 for k, v in weighted.items()}
    
    # DEBUG: Log probabilités après pondération
    log_prediction_step("Probabilités pondérées finales", final_probs)
    
    # Score le plus probable
    most = max(final_probs, key=final_probs.get) if final_probs else "Aucune donnée"
    
    logger.info(f"Score le plus probable: {most} ({final_probs.get(most, 0):.2f}%)")
    
    # DEBUG: Log résultat final
    log_final_prediction(most, final_probs.get(most, 0), final_probs)
    
    return {
        "mostProbableScore": most,
        "probabilities": {k: round(v, 2) for k, v in final_probs.items()}
    }
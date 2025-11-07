"""
Module de calcul des probabilités de scores
Basé sur l'algorithme original avec pondération Poisson et correction adaptative des nuls
+ Apprentissage par équipe avec historique des 5 derniers matchs
+ NOUVEAU: Algorithme combiné Poisson + ImpliedOdds avec smoothing de voisinage
+ NOUVEAU: Intégration coefficient de classement de ligue
"""
import math
import logging
import json
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

# Import du système de coefficient de ligue
try:
    import league_coeff
    LEAGUE_COEFF_AVAILABLE = True
except ImportError:
    LEAGUE_COEFF_AVAILABLE = False
    logger.warning("⚠️ Module league_coeff non disponible")

# ====== Paramètres calibrables pour l'algorithme combiné ======
MAX_GOALS = 5            # clamp goals per side (0..5)
ALPHA = 1.0              # force de la gaussienne sur diff (avant: 0.4) -> augmenter pour +discrimination
BLEND_BETA = 0.7         # poids Poisson vs ImpliedOdds (0..1). 0.7 = 70% Poisson, 30% odds
EPS = 1e-9               # lissage pour éviter 0
# ===============================================================


# ============================================================================
# 🎯 MODULE : PONDÉRATION PAR COTE BOOKMAKER (AJOUT OFFICIEL)
# ============================================================================

def adjust_score_weight_by_odds(odds: float, base_weight: float = 1.0) -> float:
    """
    Ajuste le poids d'un score selon la cote bookmaker.
    Cette fonction est appelée après OCR et avant le calcul principal.
    
    Logique:
    - Cotes très basses (≤ 1.8): trop évidentes → réduction 15%
    - Cotes moyennes (1.8-4.0): zone neutre → pas d'ajustement
    - Cotes intéressantes (4.0-8.0): value bet → augmentation 10%
    - Cotes élevées (8.0-15.0): peu probable → réduction 10%
    - Cotes extrêmes (> 15.0): très peu probable → réduction 20%
    
    Args:
        odds: Cote du bookmaker
        base_weight: Poids de base (défaut: 1.0)
        
    Returns:
        float: Poids ajusté
    """
    if odds <= 1.8:
        return base_weight * 0.85   # Trop évident → -15%
    elif 1.8 < odds <= 4.0:
        return base_weight          # Zone neutre
    elif 4.0 < odds <= 8.0:
        return base_weight * 1.10   # Légère value → +10%
    elif 8.0 < odds <= 15.0:
        return base_weight * 0.90   # Peu probable → -10%
    else:
        return base_weight * 0.80   # Score extrême → -20%


def process_scores_with_odds(extracted_scores: dict, enable_odds_weighting: bool = True) -> dict:
    """
    Transforme les scores extraits (OCR) en pondérations probabilistes ajustées.
    
    Cette fonction peut être utilisée AVANT calculate_probabilities pour
    préajuster les probabilités selon la confiance du bookmaker.
    
    Args:
        extracted_scores: dict {"score": odds} ou list [{"score": "X-Y", "odds": Z}]
        enable_odds_weighting: Activer/désactiver la pondération (défaut: True)
        
    Returns:
        dict: Probabilités normalisées à 100% {score: probability}
    """
    # Conversion si format liste
    if isinstance(extracted_scores, list):
        scores_dict = {item["score"]: item["odds"] for item in extracted_scores}
    else:
        scores_dict = extracted_scores
    
    weighted_scores = {}
    
    for score, odds in scores_dict.items():
        try:
            odds_val = float(odds)
        except (ValueError, TypeError):
            logger.warning(f"Cote invalide pour {score}: {odds}")
            continue
        
        # Application de la pondération si activée
        if enable_odds_weighting:
            weight = adjust_score_weight_by_odds(odds_val)
            logger.debug(f"Score {score}: cote={odds_val:.2f}, poids ajusté={weight:.3f}")
        else:
            weight = 1.0
        
        weighted_scores[score] = weight
    
    # Normalisation à 100%
    total_weight = sum(weighted_scores.values())
    if total_weight == 0:
        logger.warning("Poids total = 0, impossible de normaliser")
        return {s: 0 for s in weighted_scores}
    
    probabilities = {s: (w / total_weight) * 100 for s, w in weighted_scores.items()}
    
    # Tri par probabilité décroissante
    sorted_probs = dict(sorted(probabilities.items(), key=lambda x: x[1], reverse=True))
    
    logger.info(f"🎯 Pondération par cotes: {len(sorted_probs)} scores traités")
    if sorted_probs:
        top_score = list(sorted_probs.items())[0]
        logger.info(f"   Top score après pondération: {top_score[0]} ({top_score[1]:.2f}%)")
    
    return sorted_probs


# ============================================================================
# 🧩 EXEMPLE D'UTILISATION (COMPATIBILITÉ TOTALE)
# ============================================================================
# 
# Après l'OCR, vous pouvez:
#
# Option 1: Utiliser directement process_scores_with_odds (pondération uniquement)
# extracted_scores = {"2-4": 5.5, "4-2": 7.6, "2-0": 3.2, "2-3": 6.8, "1-0": 2.1}
# probabilities = process_scores_with_odds(extracted_scores)
# 
# Option 2: Utiliser calculate_probabilities (algorithme complet avec Poisson)
# result = calculate_probabilities(extracted_scores, diff_expected=2)
#
# Option 3: Combiner les deux (recommandé pour meilleure précision)
# pre_weighted = process_scores_with_odds(extracted_scores)
# result = calculate_probabilities(extracted_scores, diff_expected=2)
#
# ============================================================================


def calculate_confidence(probabilities: dict, best_score: str) -> float:
    """
    Calcule un indicateur de confiance global de la prédiction.
    
    La confiance est basée sur:
    - La probabilité du meilleur score
    - L'écart avec le 2ème score
    - La distribution globale des probabilités
    
    Args:
        probabilities: Dict des probabilités calculées
        best_score: Score le plus probable
        
    Returns:
        float: Score de confiance entre 0.0 et 1.0
        
    Exemples:
        - Confiance élevée (0.8-1.0): Un score domine clairement
        - Confiance moyenne (0.5-0.8): Plusieurs scores possibles
        - Confiance faible (0.0-0.5): Distribution très éparse
    """
    if not probabilities or best_score not in probabilities:
        return 0.0
    
    sorted_probs = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
    
    # Probabilité du meilleur score (normalisée sur 100)
    best_prob = sorted_probs[0][1] / 100.0
    
    # Écart avec le 2ème score
    if len(sorted_probs) > 1:
        second_prob = sorted_probs[1][1] / 100.0
        gap = best_prob - second_prob
    else:
        gap = best_prob
    
    # Formule de confiance combinée (inspirée du vFinal avec ajustements)
    # Facteur 1: Probabilité du meilleur (poids 60%)
    # Facteur 2: Écart avec le 2ème (poids 40%)
    confidence = (best_prob * 0.6) + (gap * 0.4)
    
    # Facteur d'ajustement si la proba du meilleur est très élevée
    if best_prob > 0.25:  # Plus de 25%
        confidence *= 1.2
    
    # Limitation entre 0 et 1
    confidence = min(1.0, max(0.0, confidence))
    
    return confidence


def calculate_probabilities(scores, diff_expected=2, use_odds_weighting=False):
    """
    Calcule les probabilités corrigées de chaque score selon l'algorithme original
    avec pondération Poisson simplifiée et ajustement adaptatif des matchs nuls.
    
    Args:
        scores: dict {score: odds} ou list [{"score": "X-Y", "odds": Z}]
        diff_expected: différence de buts attendue (défaut: 2)
        use_odds_weighting: Appliquer la pondération par cote AVANT le calcul (défaut: False)
    
    Returns:
        dict avec mostProbableScore et probabilities
        
    Note:
        Si use_odds_weighting=True, les scores seront prépondérés selon les cotes
        bookmaker avant d'appliquer l'algorithme Poisson et la correction des nuls.
    """
    
    # 🧩 Étape 1 : Vérification et normalisation des données
    if not scores:
        logger.warning("Aucune donnée pour la prédiction")
        return {"mostProbableScore": "Aucune donnée", "probabilities": {}}
    
    # Conversion si format liste (venant de l'OCR)
    if isinstance(scores, list):
        scores_dict = {item["score"]: item["odds"] for item in scores}
    else:
        scores_dict = scores
    
    logger.info(f"Calcul probabilités pour {len(scores_dict)} scores, diffExpected={diff_expected}, odds_weighting={use_odds_weighting}")
    
    # 🎯 Pondération par cotes si activée
    if use_odds_weighting:
        logger.info("⚙️ Application de la pondération par cote bookmaker...")
        odds_weights = {}
        for score, odds in scores_dict.items():
            try:
                odds_val = float(odds)
                odds_weights[score] = adjust_score_weight_by_odds(odds_val)
            except (ValueError, TypeError):
                odds_weights[score] = 1.0
    else:
        odds_weights = {score: 1.0 for score in scores_dict.keys()}
    
    # Normalisation de base (1 / cote) × poids cote
    raw_probs = {}
    for score, odds in scores_dict.items():
        try:
            if float(odds) > 0:
                base_prob = 1.0 / float(odds)
                # Appliquer le poids de la cote si activé
                raw_probs[score] = base_prob * odds_weights.get(score, 1.0)
        except (ValueError, TypeError):
            logger.warning(f"Cote invalide pour {score}: {odds}")
            continue
    
    if not raw_probs:
        return {"mostProbableScore": "Aucune donnée", "probabilities": {}}
    
    sum_raw = sum(raw_probs.values())
    normalized = {k: v / sum_raw for k, v in raw_probs.items()}
    
    logger.info(f"Probabilités normalisées: {normalized}")

    # 🧠 Étape 2 : Pondération Poisson (comme code Kotlin original)
    weighted = {}
    for score, p in normalized.items():
        if score == "Autre" or "-" not in score:
            weighted[score] = p
            continue
            
        parts = score.split("-")
        if len(parts) == 2:
            try:
                home = int(parts[0])
                away = int(parts[1])
                diff = abs(away - home)
                adjusted_diff = diff_expected + 1 if diff_expected > 2 else diff_expected
                weight = math.exp(-0.4 * (diff - adjusted_diff) ** 2)
                weighted[score] = p * weight
                logger.info(f"Score {score}: diff={diff}, weight={weight:.3f}, weighted={p * weight:.4f}")
            except ValueError:
                weighted[score] = p
                continue
        else:
            weighted[score] = p

    # Normalisation finale
    total = sum(weighted.values())
    final_probabilities = {k: (v / total) * 100 for k, v in weighted.items()}

    # 🎯 Étape 3 : Correction adaptative des nuls extrêmes
    logger.info("🔧 Application correction adaptative des nuls...")
    for score, p in list(final_probabilities.items()):
        if score == "Autre" or "-" not in score:
            continue
            
        try:
            home, away = map(int, score.split("-"))
            if home == away:  # Score nul
                if home >= 3:
                    # Réduction forte pour 3-3, 4-4, etc.
                    final_probabilities[score] *= 0.75
                    logger.info(f"  {score}: réduit de 25% (nul élevé)")
                elif home == 2:
                    # Légère réduction pour 2-2
                    final_probabilities[score] *= 0.95
                    logger.info(f"  {score}: réduit de 5% (2-2)")
                # 0-0 et 1-1 pas touchés
        except ValueError:
            continue

    # Recalcule après correction
    total_adj = sum(final_probabilities.values())
    final_probabilities = {k: (v / total_adj) * 100 for k, v in final_probabilities.items()}

    # 🔍 Étape 4 : Score le plus probable
    most_probable = max(final_probabilities, key=final_probabilities.get, default="Inconnu")
    
    logger.info(f"🏆 Score le plus probable: {most_probable} ({final_probabilities.get(most_probable, 0):.2f}%)")

    # 🎯 Étape 5 : Calcul de la confiance globale
    confidence = calculate_confidence(final_probabilities, most_probable)
    logger.info(f"💯 Confiance globale: {confidence:.2%}")

    # 🔁 Étape 6 : Retour formaté
    return {
        "mostProbableScore": most_probable,
        "probabilities": {k: round(v, 2) for k, v in final_probabilities.items()},
        "confidence": round(confidence, 3)
    }


# ============================================================================
# === Module Local Learning Compact - Apprentissage par Équipe ===
# ============================================================================
json_path = "/app/data/teams_data.json"

def _load_data():
    """Charge les données des équipes"""
    if not os.path.exists(json_path):
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w") as f: 
            json.dump({}, f)
    with open(json_path, "r") as f: 
        return json.load(f)

def _save_data(d): 
    """Sauvegarde les données des équipes"""
    with open(json_path, "w") as f: 
        json.dump(d, f, indent=2)

def update_team_results(team, gf, ga):
    """
    Enregistre le résultat d'un match pour une équipe.
    Garde les 5 derniers matchs seulement.
    
    Args:
        team: Nom de l'équipe
        gf: Goals For (buts marqués)
        ga: Goals Against (buts encaissés)
    """
    d = _load_data()
    d.setdefault(team, []).append([gf, ga])
    d[team] = d[team][-5:]  # garde les 5 derniers matchs
    _save_data(d)
    logger.info(f"📝 Stats mises à jour pour {team}: {gf}-{ga}")

def get_team_stats(team):
    """
    Récupère les statistiques moyennes d'une équipe.
    
    Args:
        team: Nom de l'équipe
        
    Returns:
        tuple: (moyenne buts marqués, moyenne buts encaissés)
    """
    d = _load_data()
    if team not in d or not d[team]: 
        return (1.5, 1.5)  # Valeurs par défaut
    
    gf = sum(x[0] for x in d[team]) / len(d[team])
    ga = sum(x[1] for x in d[team]) / len(d[team])
    return round(gf, 2), round(ga, 2)

def adjust_diff_expected(diff, home, away):
    """
    Ajuste le diffExpected en fonction des statistiques des équipes.
    
    Args:
        diff: diffExpected actuel
        home: Nom de l'équipe domicile
        away: Nom de l'équipe extérieur
        
    Returns:
        float: diffExpected ajusté entre 0 et 3
    """
    h_for, h_against = get_team_stats(home)
    a_for, a_against = get_team_stats(away)
    
    # Calcul de l'ajustement basé sur la force offensive et défensive
    adj = ((h_for - a_against) - (a_for - h_against)) / 2
    
    # Ajuster et limiter entre 0 et 3
    new_diff = max(0, min(3, round(diff + adj, 2)))
    
    logger.info(f"⚙️ Ajustement diffExpected: {diff} → {new_diff} (home: {home}, away: {away})")
    logger.info(f"   {home}: {h_for} buts/match, {h_against} encaissés/match")
    logger.info(f"   {away}: {a_for} buts/match, {a_against} encaissés/match")
    
    return new_diff

def get_all_teams_stats():
    """Récupère les statistiques de toutes les équipes"""
    return _load_data()


# ============================================================================
# === NOUVEL ALGORITHME COMBINÉ - predict_combined ===
# ============================================================================

def implied_prob_from_odds(odds):
    """
    Convertit une cote (ex: 5.5) en probabilité implicite (non normalisée).
    On laisse 1/odds ; la normalisation se fait après.
    """
    try:
        o = float(odds)
        if o <= 0:
            return 0.0
        return 1.0 / o
    except:
        return 0.0

def poisson_pmf(k, lam):
    """PMF de Poisson"""
    # limiter overflow
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    try:
        return (lam**k) * math.exp(-lam) / math.factorial(k)
    except OverflowError:
        return 0.0

def compute_team_lambdas(teamA_stats, teamB_stats, global_scale=1.0):
    """
    Calcule lambda_home, lambda_away à partir des stats (avg scored/conceded).
    teamX_stats: dict {'avg_goals_scored':float, 'avg_goals_conceded':float}
    global_scale: multiplicateur si tu veux augmenter tendance aux buts
    """
    # estimation simple : moyenne entre attaque locale et défense adverse
    lam_home = (teamA_stats.get('avg_goals_scored', 1.5) + teamB_stats.get('avg_goals_conceded', 1.5)) / 2.0
    lam_away = (teamB_stats.get('avg_goals_scored', 1.5) + teamA_stats.get('avg_goals_conceded', 1.5)) / 2.0
    return lam_home * global_scale, lam_away * global_scale

def predict_combined(score_odds_map, teamA_stats=None, teamB_stats=None, diffExpected=2):
    """
    Algorithme combiné utilisant Poisson + ImpliedOdds avec smoothing de voisinage.
    
    Args:
        score_odds_map: dict like {"2-4": 5.5, "3-1": 2.1, ...} ou list [{"score": "X-Y", "odds": Z}]
        teamA_stats: optional dict for lambdas calculation (see compute_team_lambdas)
        teamB_stats: optional dict for lambdas calculation (see compute_team_lambdas)
        diffExpected: valeur issue du learning_meta
        
    Returns:
        dict: {"mostProbableScore": str, "probabilities": dict, "confidence": float}
    """
    logger.info(f"🔬 NOUVEL ALGORITHME COMBINÉ - diffExpected={diffExpected}, ALPHA={ALPHA}, BLEND_BETA={BLEND_BETA}")
    
    # Conversion si format liste
    if isinstance(score_odds_map, list):
        score_odds_map = {item["score"]: item["odds"] for item in score_odds_map}
    
    # 1) build implied probabilities from odds
    implied_raw = {}
    for s, o in score_odds_map.items():
        implied_raw[s] = implied_prob_from_odds(o)

    # 2) compute lambdas (Poisson) from team stats if provided, else neutral
    if teamA_stats and teamB_stats:
        lam_home, lam_away = compute_team_lambdas(teamA_stats, teamB_stats)
        logger.info(f"📊 Lambdas calculés depuis stats équipes: λ_home={lam_home:.2f}, λ_away={lam_away:.2f}")
    else:
        lam_home, lam_away = 1.5, 1.5
        logger.info(f"📊 Lambdas par défaut: λ_home={lam_home:.2f}, λ_away={lam_away:.2f}")

    # 3) compute Poisson joint probs for all score pairs within clamp
    poisson_raw = {}
    for s in score_odds_map.keys():
        parts = s.replace(":", "-").split("-")
        if len(parts) != 2:
            continue
        try:
            h = int(parts[0]); a = int(parts[1])
        except ValueError:
            continue
            
        # clamp
        if h < 0 or a < 0 or h > MAX_GOALS or a > MAX_GOALS:
            # give tiny probability to extreme (or skip)
            poisson_raw[s] = EPS
            continue
        # joint prob = P(home goals = h) * P(away goals = a)
        p_h = poisson_pmf(h, lam_home)
        p_a = poisson_pmf(a, lam_away)
        poisson_raw[s] = max(EPS, p_h * p_a)

    # 4) apply diffExpected gaussian penalty/bonus to poisson_raw (make it stronger)
    adjusted_poisson = {}
    for s, p in poisson_raw.items():
        parts = s.split("-")
        try:
            h = int(parts[0]); a = int(parts[1])
        except ValueError:
            adjusted_poisson[s] = p
            continue
            
        diff = abs(a - h)
        # alpha is stronger than before to increase discrimination
        weight_diff = math.exp(-ALPHA * (diff - diffExpected)**2)
        adjusted_poisson[s] = p * weight_diff + EPS
        
        if p * weight_diff > 0.01:  # Log seulement les scores significatifs
            logger.debug(f"  {s}: Poisson={p:.4f}, diff={diff}, weight={weight_diff:.3f}, final={adjusted_poisson[s]:.4f}")

    # 5) normalize both distributions
    sum_pois = sum(adjusted_poisson.values()) or EPS
    pois_norm = {s: v / sum_pois for s, v in adjusted_poisson.items()}

    sum_impl = sum(implied_raw.values()) or EPS
    impl_norm = {s: implied_raw.get(s, 0.0) / sum_impl for s in adjusted_poisson.keys()}

    # 6) blend Poisson and ImpliedOdds with BLEND_BETA
    blended = {}
    for s in adjusted_poisson.keys():
        blended[s] = BLEND_BETA * pois_norm.get(s, 0.0) + (1 - BLEND_BETA) * impl_norm.get(s, 0.0) + EPS

    # 7) final normalization and convert to percentages
    total = sum(blended.values()) or EPS
    final_probs = {s: (v / total) * 100 for s, v in blended.items()}

    # 8) optional smoothing: boost nearby scores (small neighborhood smoothing)
    # (helps move mass from impossible isolated spikes)
    smoothed = defaultdict(float)
    for s, p in final_probs.items():
        try:
            h, a = map(int, s.split("-"))
        except ValueError:
            smoothed[s] = p
            continue
            
        # distribute 80% to self, 20% to neighbors (up/down by 1 goal)
        smoothed[s] += p * 0.80
        for dh, da in ((1,0),(-1,0),(0,1),(0,-1)):
            nh, na = h+dh, a+da
            key = f"{nh}-{na}"
            if 0 <= nh <= MAX_GOALS and 0 <= na <= MAX_GOALS:
                smoothed[key] += p * 0.05

    # normalize smoothed
    total_sm = sum(smoothed.values()) or EPS
    final_smoothed = {s: (v/total_sm) * 100 for s, v in smoothed.items() if s in final_probs}

    # pick top
    if not final_smoothed:
        return {"mostProbableScore": "Aucune donnée", "probabilities": {}, "confidence": 0.0}
    
    top_score = max(final_smoothed.items(), key=lambda x: x[1])[0]
    
    # Calculer la confiance
    confidence = calculate_confidence(final_smoothed, top_score)
    
    logger.info(f"🏆 Score le plus probable (combiné): {top_score} ({final_smoothed[top_score]:.2f}%)")
    logger.info(f"💯 Confiance: {confidence:.2%}")
    
    return {
        "mostProbableScore": top_score,
        "probabilities": {k: round(v, 2) for k, v in final_smoothed.items()},
        "confidence": round(confidence, 3)
    }


# ============================================================================
# === FONCTION WRAPPER POUR COMPATIBILITÉ ===
# ============================================================================

def calculate_probabilities_v2(scores, diff_expected=2, use_combined=True, teamA_name=None, teamB_name=None):
    """
    Nouvelle interface unifiée pour le calcul de probabilités.
    
    Args:
        scores: dict {score: odds} ou list [{"score": "X-Y", "odds": Z}]
        diff_expected: différence de buts attendue (défaut: 2)
        use_combined: Utiliser le nouvel algorithme combiné (défaut: True)
        teamA_name: Nom équipe A (optionnel, pour stats)
        teamB_name: Nom équipe B (optionnel, pour stats)
    
    Returns:
        dict avec mostProbableScore, probabilities et confidence
    """
    if not scores:
        logger.warning("Aucune donnée pour la prédiction")
        return {"mostProbableScore": "Aucune donnée", "probabilities": {}, "confidence": 0.0}
    
    if use_combined:
        logger.info("🆕 Utilisation de l'algorithme COMBINÉ (Poisson + ImpliedOdds + Smoothing)")
        
        # Récupérer les stats des équipes si disponibles
        teamA_stats = None
        teamB_stats = None
        if teamA_name and teamB_name:
            gf_a, ga_a = get_team_stats(teamA_name)
            gf_b, ga_b = get_team_stats(teamB_name)
            teamA_stats = {'avg_goals_scored': gf_a, 'avg_goals_conceded': ga_a}
            teamB_stats = {'avg_goals_scored': gf_b, 'avg_goals_conceded': ga_b}
            logger.info(f"📊 Stats équipes chargées - {teamA_name}: {gf_a}G/{ga_a}C, {teamB_name}: {gf_b}G/{ga_b}C")
        
        return predict_combined(scores, teamA_stats, teamB_stats, diff_expected)
    else:
        logger.info("📌 Utilisation de l'algorithme CLASSIQUE (compatibilité)")
        return calculate_probabilities(scores, diff_expected)

"""
Module de calcul des probabilités de scores
Basé sur l'algorithme original avec pondération Poisson et correction adaptative des nuls
"""
import math
import logging

logger = logging.getLogger(__name__)

def calculate_probabilities(scores, diff_expected=2):
    """
    Calcule les probabilités corrigées de chaque score selon l'algorithme original
    avec pondération Poisson simplifiée et ajustement adaptatif des matchs nuls.
    
    Args:
        scores: dict {score: odds} ou list [{"score": "X-Y", "odds": Z}]
        diff_expected: différence de buts attendue (défaut: 2)
    
    Returns:
        dict avec mostProbableScore et probabilities
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
    
    logger.info(f"Calcul probabilités pour {len(scores_dict)} scores, diffExpected={diff_expected}")
    
    # Normalisation de base (1 / cote)
    raw_probs = {}
    for score, odds in scores_dict.items():
        try:
            if float(odds) > 0:
                raw_probs[score] = 1.0 / float(odds)
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

    # 🔁 Étape 5 : Retour formaté
    return {
        "mostProbableScore": most_probable,
        "probabilities": {k: round(v, 2) for k, v in final_probabilities.items()}
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

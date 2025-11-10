# /app/backend/league_coeff.py
"""
Calcule les coefficients d'équipe basés sur leur position dans le classement.
Plus l'équipe est haute dans le classement, plus son coefficient est élevé.
"""
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Importer les fonctions de league_fetcher
import sys
sys.path.insert(0, '/app/backend')
from league_fetcher import load_positions, get_team_position

# Coefficients min/max
MIN_COEF = 0.85  # Équipe dernière
MAX_COEF = 1.30  # Équipe première
FALLBACK_COEF = 1.0  # Si équipe non trouvée

# Cache des coefficients
DATA_DIR = "/app/data/leagues"
COEFF_CACHE_FILE = os.path.join(DATA_DIR, "coeff_cache.json")

def _load_cache():
    """Charge le cache des coefficients"""
    if not os.path.exists(COEFF_CACHE_FILE):
        return {}
    try:
        with open(COEFF_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_cache(cache):
    """Sauvegarde le cache des coefficients"""
    try:
        with open(COEFF_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erreur sauvegarde cache coeff: {e}")

def team_coef_from_position_linear(team_name, league_name="LaLiga", min_coef=MIN_COEF, max_coef=MAX_COEF):
    """
    Calcule le coefficient d'une équipe selon sa position (formule LINÉAIRE).
    
    Formule : coeff = min_coef + ((N - pos) / (N - 1)) * (max_coef - min_coef)
    
    Exemples (avec 20 équipes, min=0.85, max=1.30) :
    - Position 1 (1er)  : coeff = 1.30
    - Position 10 (mid): coeff ≈ 1.07
    - Position 20 (dernier): coeff = 0.85
    
    Args:
        team_name: Nom de l'équipe
        league_name: Nom de la ligue (LaLiga, PremierLeague, etc.)
        min_coef: Coefficient minimum (équipe dernière)
        max_coef: Coefficient maximum (équipe première)
    
    Returns:
        float: Coefficient entre min_coef et max_coef
    """
    # Vérifier le cache
    cache_key = f"{league_name}:{team_name}"
    cache = _load_cache()
    if cache_key in cache:
        return cache[cache_key]
    
    pos_map = load_positions().get(league_name, {})
    
    if not pos_map:
        logger.warning(f"⚠️ Aucun classement pour {league_name}")
        return FALLBACK_COEF
    
    # Obtenir la position (avec fuzzy matching)
    pos = get_team_position(team_name, league_name)
    
    if not pos:
        logger.warning(f"⚠️ Équipe '{team_name}' non trouvée dans {league_name}")
        return FALLBACK_COEF
    
    try:
        pos_int = int(pos)
    except:
        return FALLBACK_COEF
    
    # Calculer le nombre total d'équipes
    positions = list(pos_map.values())
    try:
        max_pos = max(int(p) for p in positions if isinstance(p, (int, float, str)))
    except:
        max_pos = len(positions)
    
    N = max_pos if max_pos > 1 else len(positions)
    
    if N <= 1:
        return FALLBACK_COEF
    
    # Formule linéaire : plus l'équipe est haute, plus le coeff est élevé
    raw = (N - pos_int) / float(N - 1)
    coef = min_coef + raw * (max_coef - min_coef)
    coef = round(coef, 4)
    
    # Sauvegarder dans le cache
    cache[cache_key] = coef
    _save_cache(cache)
    
    logger.info(f"📊 {team_name} ({league_name}) : Position {pos_int}/{N} → Coeff {coef}")
    
    return coef

def team_coef_from_position_exponential(team_name, league_name="LaLiga", min_coef=MIN_COEF, max_coef=MAX_COEF, exp=2.0):
    """
    Calcule le coefficient d'une équipe selon sa position (formule EXPONENTIELLE).
    
    Formule : coeff = min_coef + ((N - pos) / (N - 1))^exp * (max_coef - min_coef)
    
    Avec exp=2, les équipes du top sont TRÈS favorisées :
    - Position 1 (1er)  : coeff = 1.30
    - Position 5       : coeff ≈ 1.20 (encore très haut)
    - Position 10 (mid): coeff ≈ 0.95 (baisse significative)
    - Position 20 (dernier): coeff = 0.85
    
    Args:
        team_name: Nom de l'équipe
        league_name: Nom de la ligue
        min_coef: Coefficient minimum
        max_coef: Coefficient maximum
        exp: Exposant (2.0 par défaut, plus c'est élevé plus la courbe est agressive)
    
    Returns:
        float: Coefficient entre min_coef et max_coef
    """
    pos_map = load_positions().get(league_name, {})
    
    if not pos_map:
        return FALLBACK_COEF
    
    pos = get_team_position(team_name, league_name)
    
    if not pos:
        return FALLBACK_COEF
    
    try:
        pos_int = int(pos)
    except:
        return FALLBACK_COEF
    
    positions = list(pos_map.values())
    try:
        max_pos = max(int(p) for p in positions if isinstance(p, (int, float, str)))
    except:
        max_pos = len(positions)
    
    N = max_pos if max_pos > 1 else len(positions)
    
    if N <= 1:
        return FALLBACK_COEF
    
    # Formule exponentielle
    raw = ((N - pos_int) / float(N - 1)) ** exp
    coef = min_coef + raw * (max_coef - min_coef)
    coef = round(coef, 4)
    
    logger.info(f"📊 {team_name} ({league_name}) : Position {pos_int}/{N} → Coeff {coef} (exp={exp})")
    
    return coef

# Alias pour la fonction par défaut (linéaire)
team_coef_from_position = team_coef_from_position_linear

def get_both_team_coeffs(home_team, away_team, league="LaLiga", mode="linear"):
    """
    Récupère les coefficients pour les deux équipes.
    
    Args:
        home_team: Nom équipe domicile
        away_team: Nom équipe extérieur
        league: Ligue
        mode: "linear" ou "exponential"
    
    Returns:
        tuple: (coef_home, coef_away)
    """
    if mode == "exponential":
        func = team_coef_from_position_exponential
    else:
        func = team_coef_from_position_linear
    
    try:
        home_coef = func(home_team, league)
    except Exception as e:
        logger.error(f"Erreur coeff home: {e}")
        home_coef = FALLBACK_COEF
    
    try:
        away_coef = func(away_team, league)
    except Exception as e:
        logger.error(f"Erreur coeff away: {e}")
        away_coef = FALLBACK_COEF
    
    return home_coef, away_coef

def clear_cache():
    """Vide le cache des coefficients"""
    try:
        if os.path.exists(COEFF_CACHE_FILE):
            os.remove(COEFF_CACHE_FILE)
        logger.info("✅ Cache des coefficients vidé")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur vidage cache: {e}")
        return False

def lookup_in_all_leagues(team_name):
    """
    Recherche une équipe dans toutes les ligues nationales disponibles.
    Retourne le coefficient trouvé dans la première ligue où l'équipe existe.
    
    Args:
        team_name: Nom de l'équipe
    
    Returns:
        tuple: (coefficient, source_league) ou (None, None) si non trouvé
    """
    # Ligues nationales prioritaires (ordre de recherche)
    national_leagues = ["LaLiga", "PremierLeague", "SerieA", "Ligue1", "Bundesliga", "PrimeiraLiga"]
    
    for league in national_leagues:
        try:
            pos = get_team_position(team_name, league)
            if pos:
                coef = team_coef_from_position_linear(team_name, league)
                logger.info(f"🔍 {team_name} trouvée dans {league} → coeff={coef:.3f}")
                return coef, league
        except Exception as e:
            continue
    
    return None, None

def get_team_coeff(team_name, league_name=None):
    """
    Fonction utilitaire pour récupérer le coefficient d'une équipe avec système de fallback intelligent.
    
    Logique de recherche:
    1. Si ligue spécifiée et équipe trouvée → utiliser ce coefficient
    2. Si ligue = ChampionsLeague/EuropaLeague et équipe non trouvée:
       a. Chercher dans toutes les ligues nationales
       b. Si trouvée → utiliser le coefficient de la ligue nationale
       c. Si non trouvée → appliquer bonus européen (1.05)
    3. Sinon → fallback standard (1.0)
    
    Args:
        team_name: Nom de l'équipe
        league_name: Nom de la ligue (optionnel)
    
    Returns:
        dict: {"coefficient": float, "source": str}
    """
    if not team_name:
        return {"coefficient": FALLBACK_COEF, "source": "fallback_no_team"}
    
    # Si pas de ligue spécifiée, on retourne le fallback
    if not league_name:
        logger.debug(f"⚠️ Pas de ligue spécifiée pour {team_name}, coefficient = {FALLBACK_COEF}")
        return {"coefficient": FALLBACK_COEF, "source": "fallback_no_league"}
    
    # Cas 1: Ligue spécifiée (non européenne), recherche directe
    if league_name not in ["ChampionsLeague", "EuropaLeague"]:
        try:
            coef = team_coef_from_position_linear(team_name, league_name)
            return {"coefficient": coef, "source": league_name}
        except Exception as e:
            logger.warning(f"⚠️ Erreur calcul coeff {team_name} dans {league_name}: {e}")
            return {"coefficient": FALLBACK_COEF, "source": "fallback_error"}
    
    # Cas 2: Compétition européenne - Recherche prioritaire dans ligues nationales
    logger.info(f"🏆 Recherche {team_name} pour {league_name}...")
    
    # PRIORITÉ 1: Chercher dans toutes les ligues nationales
    coef, source_league = lookup_in_all_leagues(team_name)
    
    if coef is not None:
        logger.info(f"✅ {team_name} trouvée dans {source_league} → coeff={coef:.3f}")
        return {"coefficient": coef, "source": source_league}
    
    # PRIORITÉ 2: Bonus européen pour clubs non répertoriés dans ligues nationales
    european_bonus = 1.05
    logger.info(f"🌍 {team_name} non trouvée dans les ligues nationales → bonus européen={european_bonus}")
    return {"coefficient": european_bonus, "source": "european_fallback"}


# =============================================================================
# COEFFICIENTS FIFA POUR MATCHS INTERNATIONAUX
# =============================================================================

def get_coeffs_for_match(home_team, away_team, league):
    """
    Retourne les coefficients pour un match, en détectant automatiquement
    s'il s'agit d'un match international (FIFA) ou d'un match de clubs.
    
    Si la ligue est internationale (WorldCup, Qualification, NationsLeague), 
    on utilise les coefficients FIFA mondiaux.
    Sinon on utilise les coefficients de ligue existants.
    
    Args:
        home_team: Nom équipe domicile
        away_team: Nom équipe extérieur
        league: Nom de la ligue/compétition
    
    Returns:
        tuple: (home_coeff, away_coeff)
    
    Examples:
        >>> get_coeffs_for_match("France", "Portugal", "WorldCup")
        (1.28, 1.25)  # Coefficients FIFA
        
        >>> get_coeffs_for_match("Real Madrid", "Barcelona", "LaLiga")
        (1.30, 1.28)  # Coefficients de ligue
    """
    # Marqueurs pour détecter les compétitions internationales
    international_markers = {
        "world", "worldcup", "qualification", "fifa", 
        "international", "nations", "euro", "copa america"
    }
    
    # Vérifier si c'est une compétition internationale
    is_international = False
    if league:
        league_lower = league.lower()
        is_international = any(marker in league_lower for marker in international_markers)
    
    if is_international:
        # Utiliser les coefficients FIFA
        try:
            from ufa.world_coeffs import get_world_coeff
            home_coeff = get_world_coeff(home_team)
            away_coeff = get_world_coeff(away_team)
            logger.info(f"🌍 Match international: {home_team} ({home_coeff}) vs {away_team} ({away_coeff})")
            return home_coeff, away_coeff
        except Exception as e:
            logger.error(f"Erreur coefficients FIFA: {e}, utilisation fallback")
            return FALLBACK_COEF, FALLBACK_COEF
    
    # Sinon, utiliser les coefficients de ligue classiques
    try:
        home_result = get_team_coeff(home_team, league)
        away_result = get_team_coeff(away_team, league)
        
        home_coeff = home_result.get("coefficient", FALLBACK_COEF)
        away_coeff = away_result.get("coefficient", FALLBACK_COEF)
        
        logger.info(f"🏆 Match de clubs: {home_team} ({home_coeff}) vs {away_team} ({away_coeff})")
        return home_coeff, away_coeff
    except Exception as e:
        logger.error(f"Erreur coefficients de ligue: {e}")
        return FALLBACK_COEF, FALLBACK_COEF



# =============================================================================
# AJUSTEMENT AUTOMATIQUE DES COEFFICIENTS SELON PERFORMANCES
# =============================================================================

COEFF_PATH = "/app/data/league_coefficients.json"
LOG_COEFF = "/app/logs/coeff_adjustment.log"

def load_league_coeffs():
    """
    Charge les coefficients de ligue depuis le fichier JSON.
    
    Returns:
        dict: Coefficients par ligue
    """
    if not os.path.exists(COEFF_PATH):
        # Créer fichier initial si n'existe pas
        initial_coeffs = {
            "Ligue1": 1.0,
            "LaLiga": 1.0,
            "PremierLeague": 1.0,
            "Bundesliga": 1.0,
            "SerieA": 1.0,
            "Championship": 0.95,
            "Eredivisie": 0.97,
            "PrimeiraLiga": 0.96,
            "WorldCup": 1.1,
            "Euro": 1.08,
            "NationsLeague": 1.05
        }
        save_league_coeffs(initial_coeffs)
        return initial_coeffs
    
    with open(COEFF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_league_coeffs(coeffs):
    """
    Sauvegarde les coefficients de ligue dans le fichier JSON.
    
    Args:
        coeffs: Dictionnaire des coefficients
    """
    Path(COEFF_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(COEFF_PATH, "w", encoding="utf-8") as f:
        json.dump(coeffs, f, indent=2, ensure_ascii=False)

def log_coeff(msg):
    """Log un message d'ajustement de coefficient."""
    from datetime import datetime
    Path(LOG_COEFF).parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    with open(LOG_COEFF, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")
    print(log_msg)

def update_league_coefficients(perf_file):
    """
    Met à jour les coefficients de ligue selon les performances du modèle.
    
    Logique:
    - Compare la performance de chaque ligue à la moyenne globale
    - Si ligue > moyenne → augmente légèrement le coefficient
    - Si ligue < moyenne → diminue légèrement le coefficient
    - Ajustement progressif: ±0.002 par point de pourcentage
    
    Args:
        perf_file: Chemin vers performance_summary.json
    
    Returns:
        dict: Nouveaux coefficients
    """
    log_coeff("=" * 70)
    log_coeff("⚙️  AJUSTEMENT AUTOMATIQUE DES COEFFICIENTS")
    log_coeff("=" * 70)
    
    if not os.path.exists(perf_file):
        log_coeff("❌ Aucun rapport de performance trouvé.")
        return {}
    
    # Charger les performances
    with open(perf_file, "r", encoding="utf-8") as f:
        perf_data = json.load(f)
    
    if not perf_data:
        log_coeff("❌ Rapport de performance vide.")
        return {}
    
    # Charger les coefficients actuels
    coeffs = load_league_coeffs()
    
    # Calculer la moyenne globale des performances
    accuracies = [v["accuracy"] for v in perf_data.values()]
    avg_accuracy = sum(accuracies) / len(accuracies)
    
    log_coeff(f"📊 Moyenne globale des performances: {avg_accuracy:.1f}%")
    log_coeff(f"📥 {len(perf_data)} ligues à ajuster")
    
    updated = 0
    
    for league, stats in perf_data.items():
        accuracy = stats["accuracy"]
        matches = stats["matches"]
        
        # Calculer l'écart par rapport à la moyenne
        diff = accuracy - avg_accuracy
        
        # Ajustement progressif: ±0.002 par point de pourcentage
        # (ex: si +5% au-dessus de la moyenne → +0.01)
        adjust = round(diff * 0.002, 3)
        
        # Obtenir le coefficient actuel (ou 1.0 par défaut)
        current_coeff = coeffs.get(league, 1.0)
        
        # Calculer le nouveau coefficient
        new_coeff = round(current_coeff + adjust, 3)
        
        # Limiter les coefficients entre 0.80 et 1.35
        new_coeff = max(0.80, min(1.35, new_coeff))
        
        # Sauvegarder
        coeffs[league] = new_coeff
        updated += 1
        
        # Log l'ajustement
        log_coeff(f"⚙️  {league}: {accuracy:.1f}% ({matches} matchs) → {current_coeff:.3f} → {new_coeff:.3f} ({adjust:+.3f})")
    
    # Sauvegarder les nouveaux coefficients
    save_league_coeffs(coeffs)
    
    log_coeff("=" * 70)
    log_coeff(f"✅ {updated} ligues ajustées selon performances.")
    log_coeff(f"💾 Coefficients sauvegardés: {COEFF_PATH}")
    log_coeff("=" * 70)
    
    return coeffs

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

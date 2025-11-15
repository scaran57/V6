#!/usr/bin/env python3
# /app/backend/tools/api_sports_fetcher.py
"""
API-Sports Integration
----------------------
Source secondaire pour les classements de ligues.
⚠️ Limitation : Plan gratuit limité aux saisons 2021-2023 (pas les données actuelles)

Documentation: https://v3.football.api-sports.io
"""

import os
import requests
import logging
import time

logger = logging.getLogger(__name__)

# =========================================
# ⚙️ CONFIGURATION
# =========================================

API_KEY = os.getenv("API_SPORTS_KEY", "cf100c6f299725637181d7cabfccf3d1")
API_BASE_URL = "https://v3.football.api-sports.io"

# Mapping des ligues vers les IDs API-Sports
LEAGUE_IDS = {
    "LaLiga": 140,  # La Liga (Spain)
    "PremierLeague": 39,  # Premier League (England)
    "SerieA": 135,  # Serie A (Italy)
    "Ligue1": 61,  # Ligue 1 (France)
    "Bundesliga": 78,  # Bundesliga (Germany)
    "PrimeiraLiga": 94,  # Primeira Liga (Portugal)
    "Ligue2": 62,  # Ligue 2 (France)
    "ChampionsLeague": 2,  # UEFA Champions League
    "EuropaLeague": 3,  # UEFA Europa League
}

# Plan gratuit : saisons 2021-2023 uniquement
AVAILABLE_SEASONS = [2021, 2022, 2023]
DEFAULT_SEASON = 2023  # Utiliser la plus récente disponible

# =========================================
# 🌐 API REQUESTS
# =========================================

def get_standings_api_sports(league_name, season=None):
    """
    Récupère le classement d'une ligue depuis API-Sports
    
    Args:
        league_name: Nom de la ligue (ex: "LaLiga")
        season: Année de la saison (ex: 2023). Si None, utilise DEFAULT_SEASON
    
    Returns:
        list: Données du classement ou None en cas d'erreur
    """
    if league_name not in LEAGUE_IDS:
        logger.error(f"❌ [API-Sports] Ligue inconnue: {league_name}")
        return None
    
    if season is None:
        season = DEFAULT_SEASON
    
    if season not in AVAILABLE_SEASONS:
        logger.warning(f"⚠️ [API-Sports] Saison {season} non disponible (plan gratuit: 2021-2023)")
        return None
    
    league_id = LEAGUE_IDS[league_name]
    
    headers = {
        "x-apisports-key": API_KEY
    }
    
    url = f"{API_BASE_URL}/standings"
    params = {
        "league": league_id,
        "season": season
    }
    
    try:
        logger.info(f"🌐 [API-Sports] Fetching {league_name} (season {season})")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 429:
            logger.warning("[API-Sports] Rate limit atteint — pause 6 secondes")
            time.sleep(6)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"❌ [API-Sports] HTTP {response.status_code}")
            return None
        
        data = response.json()
        
        # Vérifier les erreurs
        if data.get("errors"):
            errors = data["errors"]
            logger.error(f"❌ [API-Sports] Erreur API: {errors}")
            return None
        
        if data.get("results", 0) == 0:
            logger.warning(f"⚠️ [API-Sports] Aucun résultat pour {league_name}")
            return None
        
        # Extraire les standings
        standings_data = data["response"][0]["league"]["standings"][0]
        
        final_table = []
        for entry in standings_data:
            final_table.append({
                "team": entry["team"]["name"],
                "position": entry["rank"],
                "points": entry["points"],
                "played": entry["all"]["played"]
            })
        
        logger.info(f"✅ [API-Sports] {len(final_table)} équipes récupérées")
        return final_table
        
    except Exception as e:
        logger.error(f"❌ [API-Sports] Exception: {e}")
        return None

# =========================================
# 🧪 TESTS
# =========================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("🧪 Test: API-Sports avec saison 2023 (disponible)")
    result = get_standings_api_sports("LaLiga", season=2023)
    
    if result:
        print(f"✅ Succès! {len(result)} équipes")
        print("Top 3:")
        for team in result[:3]:
            print(f"  {team['position']}. {team['team']} - {team['points']} pts")
    else:
        print("❌ Échec")
    
    print("\n🧪 Test: API-Sports avec saison 2024 (non disponible)")
    result = get_standings_api_sports("LaLiga", season=2024)
    
    if result:
        print("✅ Succès (inattendu)")
    else:
        print("❌ Échec (attendu - plan gratuit)")

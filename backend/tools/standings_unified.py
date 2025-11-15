import json
import time
import os
import logging
import sys

sys.path.insert(0, '/app/backend')

from tools.football_data_api import get_standings_football_data
from tools.api_sports_fetcher import get_standings_api_sports
from tools.soccerdata_scraper import get_standings_soccerdata

logger = logging.getLogger(__name__)

CACHE_PATH = "/app/data/leagues/standings_cache.json"


def load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def calculate_coefficient(position, total_teams):
    """Calcule le coefficient selon la position (0.85 - 1.30)"""
    if position == 1:
        return 1.30
    if position == total_teams:
        return 0.85
    
    coeff = 0.85 + ((total_teams - position) / (total_teams - 1)) * 0.45
    return round(coeff, 4)


def standings_unified(league_name, league_code_api, league_code_soccerdata, season="2425", api_sports_season=2023):
    """
    Stratégie de fallback intelligent :
    1) Essaye Football-Data (API officielle - données actuelles)
    2) Si échec → API-Sports (données historiques 2021-2023)
    3) Si échec → SoccerData (scraping FBRef)
    4) Si échec → Retourne cache local
    
    Args:
        league_name: Nom interne (ex: "LaLiga")
        league_code_api: Code Football-Data (ex: "PD")
        league_code_soccerdata: Code SoccerData (ex: "ESP-La Liga")
        season: Saison SoccerData (format "2425" pour 2024-2025)
        api_sports_season: Saison API-Sports (2021, 2022 ou 2023 - plan gratuit)
    
    Returns:
        dict: Données formatées ou None
    """
    cache = load_cache()

    logger.info(f"\n[Mise à jour] {league_name} (API: {league_code_api})")

    # --- 1. Football-Data PRIORITÉ 1 (données actuelles) ---
    data = get_standings_football_data(league_code_api)

    if data:
        logger.info(f"✅ {league_name}: Football-Data OK ({len(data)} équipes)")
        
        # Calculer les coefficients
        total_teams = len(data)
        for team in data:
            team["coefficient"] = calculate_coefficient(team["position"], total_teams)
        
        # Formater pour notre système
        formatted_data = {
            "league": league_name,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "football-data.org",
            "teams": [
                {
                    "rank": t["position"],
                    "name": t["team"],
                    "points": t["points"],
                    "coefficient": t["coefficient"]
                }
                for t in data
            ]
        }
        
        cache[league_name] = {
            "timestamp": time.time(),
            "data": formatted_data
        }
        save_cache(cache)
        return formatted_data

    logger.warning(f"⚠️ {league_name}: Football-Data KO — tentative API-Sports…")

    # --- 2. API-Sports PRIORITÉ 2 (données historiques) ---
    data = get_standings_api_sports(league_name, season=api_sports_season)

    if data:
        logger.info(f"✅ {league_name}: API-Sports OK ({len(data)} équipes - saison {api_sports_season})")
        
        # Calculer les coefficients
        total_teams = len(data)
        for team in data:
            team["coefficient"] = calculate_coefficient(team["position"], total_teams)
        
        # Formater pour notre système
        formatted_data = {
            "league": league_name,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": f"api-sports (season {api_sports_season})",
            "teams": [
                {
                    "rank": t["position"],
                    "name": t["team"],
                    "points": t["points"],
                    "coefficient": t["coefficient"]
                }
                for t in data
            ]
        }
        
        cache[league_name] = {
            "timestamp": time.time(),
            "data": formatted_data
        }
        save_cache(cache)
        return formatted_data

    logger.warning(f"⚠️ {league_name}: API-Sports KO — tentative SoccerData…")

    # --- 2. SoccerData FALLBACK ---
    data = get_standings_soccerdata(league_code_soccerdata, season)

    if data:
        logger.info(f"✅ {league_name}: SoccerData OK ({len(data)} équipes)")
        
        # Calculer les coefficients
        total_teams = len(data)
        for team in data:
            team["coefficient"] = calculate_coefficient(team["position"], total_teams)
        
        # Formater pour notre système
        formatted_data = {
            "league": league_name,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "soccerdata-fbref",
            "teams": [
                {
                    "rank": t["position"],
                    "name": t["team"],
                    "points": t["points"],
                    "coefficient": t["coefficient"]
                }
                for t in data
            ]
        }
        
        cache[league_name] = {
            "timestamp": time.time(),
            "data": formatted_data
        }
        save_cache(cache)
        return formatted_data

    logger.warning(f"❌ {league_name}: Aucune source active — utilisation cache local")

    # --- 3. CACHE FALLBACK FINAL ---
    if league_name in cache:
        age_hours = (time.time() - cache[league_name]["timestamp"]) / 3600
        logger.info(f"ℹ️ {league_name}: Cache utilisé (âge: {age_hours:.1f}h)")
        return cache[league_name]["data"]

    logger.error(f"❌ {league_name}: Aucun cache disponible")
    return None


# =========================================
# 🧪 TESTS
# =========================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🧪 Test: Récupération LaLiga avec fallback")
    result = standings_unified(
        league_name="LaLiga",
        league_code_api="PD",
        league_code_soccerdata="ESP-La Liga",
        season="2425"
    )
    
    if result:
        print(f"\n✅ Succès!")
        print(f"Source: {result['source']}")
        print(f"Équipes: {len(result['teams'])}")
        print(f"Top 3:")
        for team in result['teams'][:3]:
            print(f"  {team['rank']}. {team['name']} - {team['points']} pts - coeff {team['coefficient']}")
    else:
        print("\n❌ Échec de récupération")

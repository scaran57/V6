import os
import time
import requests
import logging

logger = logging.getLogger(__name__)

API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "ad9959577fd349ba99b299612668a5cb")
BASE_URL = "https://api.football-data.org/v4"


def get_standings_football_data(league_code: str):
    """
    Récupère les classements via Football-Data.org (source principale)
    """
    url = f"{BASE_URL}/competitions/{league_code}/standings"
    headers = {"X-Auth-Token": API_KEY}

    try:
        logger.info(f"[FootballData] Fetching {league_code}")
        res = requests.get(url, headers=headers, timeout=10)

        if res.status_code == 429:
            logger.warning("[FootballData] RATE LIMIT atteint — pause 6 secondes…")
            time.sleep(6)
            res = requests.get(url, headers=headers, timeout=10)

        if res.status_code != 200:
            logger.error(f"[FootballData] Erreur HTTP {res.status_code}")
            return None

        data = res.json()
        standings = data["standings"][0]["table"]

        final_table = []

        for entry in standings:
            final_table.append({
                "team": entry["team"]["name"],
                "position": entry["position"],
                "points": entry["points"],
                "played": entry["playedGames"]
            })

        logger.info(f"[FootballData] ✅ {len(final_table)} équipes récupérées")
        return final_table

    except Exception as e:
        logger.error(f"[FootballData] Exception : {e}")
        return None

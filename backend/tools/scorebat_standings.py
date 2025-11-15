# /app/backend/tools/scorebat_standings.py

import requests
import time
import logging

logger = logging.getLogger(__name__)

SCOREBAT_STANDINGS_URL = "https://www.scorebat.com/video-api/v3/"

class ScoreBatStandings:
    def __init__(self):
        self.session = requests.Session()

    def get_standings(self, league_name: str):
        """
        Récupère le classement d'une ligue via ScoreBat.
        """
        try:
            logger.info(f"🌐 Fetching {league_name} from ScoreBat API")
            response = self.session.get(SCOREBAT_STANDINGS_URL, timeout=10)
            if response.status_code != 200:
                logger.error(f"❌ ScoreBat HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

            data = response.json()

            competitions = data.get("response", [])

            # Recherche interne
            for comp in competitions:
                comp_title = comp.get("title", "").lower()

                if league_name.lower() in comp_title:

                    table = comp.get("leagueTable", [])
                    standings = []

                    for team in table:
                        standings.append({
                            "team": team.get("team"),
                            "position": team.get("position"),
                            "played": team.get("played"),
                            "won": team.get("won"),
                            "drawn": team.get("drawn"),
                            "lost": team.get("lost"),
                            "points": team.get("points")
                        })

                    logger.info(f"✅ Found {len(standings)} teams for {comp.get('title')}")
                    return {
                        "success": True,
                        "league": comp.get("title"),
                        "standings": standings,
                        "source": "scorebat"
                    }

            logger.warning(f"⚠️ League {league_name} not found in ScoreBat")
            return {"success": False, "error": "League not found"}

        except Exception as e:
            logger.error(f"❌ ScoreBat error: {e}")
            return {"success": False, "error": str(e)}

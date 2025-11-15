import soccerdata as sd
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def get_standings_soccerdata(league_code: str, season: str = "2425"):
    """
    Scrape les classements via SoccerData (FBRef principalement)
    League codes acceptés : 'ENG-Premier League', 'ESP-La Liga', etc.
    Season format: '2425' pour saison 2024-2025
    """
    try:
        logger.info(f"[SoccerData] Scraping {league_code} season {season}")
        
        # Créer l'instance FBref
        fbref = sd.FBref(leagues=[league_code], seasons=[season])

        # Récupérer le classement
        standings = fbref.read_league_table()

        # Convertir en format utilisable
        table = standings.reset_index()
        
        # Les colonnes peuvent varier, essayons différentes possibilités
        results = []
        
        for idx, row in table.iterrows():
            try:
                team_name = row.get("team", row.get("Squad", "Unknown"))
                position = idx + 1  # Position basée sur l'index
                points = int(row.get("points", row.get("Pts", 0)))
                played = int(row.get("games", row.get("MP", 0)))
                
                results.append({
                    "team": str(team_name),
                    "position": position,
                    "points": points,
                    "played": played
                })
            except Exception as e:
                logger.warning(f"[SoccerData] Erreur parsing ligne {idx}: {e}")
                continue

        logger.info(f"[SoccerData] ✅ {len(results)} équipes récupérées")
        return results

    except Exception as e:
        logger.error(f"[SoccerData] Erreur : {e}")
        return None

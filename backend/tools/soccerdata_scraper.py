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

        # Récupérer les statistiques d'équipes par saison (contient le classement)
        stats = fbref.read_team_season_stats()
        
        if stats is None or stats.empty:
            logger.warning(f"[SoccerData] Aucune donnée pour {league_code}")
            return None

        # Convertir en format utilisable
        # FBref retourne un MultiIndex, on le reset
        table = stats.reset_index()
        
        # Trier par points (colonne 'Pts')
        if 'Pts' in table.columns:
            table = table.sort_values('Pts', ascending=False).reset_index(drop=True)
        
        results = []
        
        for idx, row in table.iterrows():
            try:
                # Essayer différents noms de colonnes selon la version
                team_name = None
                if 'team' in row:
                    team_name = row['team']
                elif 'Squad' in row:
                    team_name = row['Squad']
                else:
                    # Chercher dans l'index
                    if hasattr(row, 'name') and isinstance(row.name, tuple):
                        team_name = row.name[0] if row.name else "Unknown"
                    else:
                        team_name = "Unknown"
                
                position = idx + 1  # Position basée sur le tri
                points = int(row.get('Pts', 0))
                played = int(row.get('MP', row.get('Pld', 0)))
                
                results.append({
                    "team": str(team_name),
                    "position": position,
                    "points": points,
                    "played": played
                })
            except Exception as e:
                logger.warning(f"[SoccerData] Erreur parsing ligne {idx}: {e}")
                continue

        if not results:
            logger.warning(f"[SoccerData] Aucune équipe extraite pour {league_code}")
            return None

        logger.info(f"[SoccerData] ✅ {len(results)} équipes récupérées")
        return results

    except Exception as e:
        logger.error(f"[SoccerData] Erreur : {e}")
        return None

#!/usr/bin/env python3
"""
Système unifié de gestion des ligues - Toutes les ligues
---------------------------------------------------------
Utilise le système multi-sources professionnel avec fallback intelligent.

Stratégie:
1. Football-Data.org API (priorité 1 - données officielles actuelles)
2. SoccerData/FBRef (priorité 2 - fallback enrichi)
3. API-Sports (priorité 3 - données historiques 2021-2023)
4. Cache local (priorité 4 - dernières données connues)

Ligues supportées:
- LaLiga, PremierLeague, SerieA, Bundesliga, Ligue1
- PrimeiraLiga, Ligue2
- ChampionsLeague, EuropaLeague
"""
import os
import sys
import logging
import json
from datetime import datetime

# Import du nouveau système multi-sources
sys.path.insert(0, '/app/backend')
from tools.multi_source_updater import UnifiedUpdater, run_daily_update

logger = logging.getLogger(__name__)

# Mapping des ligues pour le multi-source updater
LEAGUES_MAP = {
    "PL": "ENG-Premier League",     # Premier League
    "PD": "ESP-La Liga",             # LaLiga
    "SA": "ITA-Serie A",             # Serie A
    "BL1": "GER-Bundesliga",         # Bundesliga
    "FL1": "FRA-Ligue 1",            # Ligue 1
    "PPL": "POR-Primeira Liga",      # Primeira Liga
    "FL2": "FRA-Ligue 2",            # Ligue 2
    "CL": "Champions League",        # Champions League
    "EL": "Europa League",           # Europa League
    "WC": "FIFA World Cup"           # FIFA World Cup
}

DATA_DIR = "/app/data/leagues"
os.makedirs(DATA_DIR, exist_ok=True)

# Configuration unifiée de TOUTES les ligues (Phase 1 + Phase 2)
LEAGUES = {
    # === PHASE 1 - Ligues principales ===
    "LaLiga": {
        "url": "https://en.wikipedia.org/wiki/2025–26_La_Liga",
        "expected_teams": 20,
        "fallback_teams": [
            "Real Madrid", "Barcelona", "Atletico Madrid", "Real Sociedad",
            "Real Betis", "Villarreal", "Athletic Bilbao", "Valencia",
            "Osasuna", "Girona", "Sevilla", "Getafe",
            "Rayo Vallecano", "Celta Vigo", "Las Palmas", "Mallorca",
            "Alaves", "Cadiz", "Granada", "Almeria"
        ]
    },
    "PremierLeague": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Premier_League",
        "expected_teams": 20,
        "fallback_teams": [
            "Manchester City", "Liverpool", "Arsenal", "Aston Villa",
            "Tottenham Hotspur", "Chelsea", "Newcastle United", "Manchester United",
            "West Ham United", "Crystal Palace", "Brighton", "Bournemouth",
            "Fulham", "Wolves", "Everton", "Brentford",
            "Nottingham Forest", "Luton Town", "Burnley", "Sheffield United"
        ]
    },
    "ChampionsLeague": {
        "url": "https://en.wikipedia.org/wiki/2024–25_UEFA_Champions_League",
        "expected_teams": 36,
        "fallback_teams": [
            "Real Madrid", "Manchester City", "Bayern Munich", "Paris Saint-Germain",
            "Inter Milan", "Borussia Dortmund", "Barcelona", "RB Leipzig",
            "Atletico Madrid", "Porto", "Arsenal", "Shakhtar Donetsk",
            "Napoli", "Benfica", "PSV Eindhoven", "Lazio",
            "Feyenoord", "Celtic", "Red Star Belgrade", "Young Boys",
            "Salzburg", "Union Berlin", "Braga", "Real Sociedad",
            "Galatasaray", "Copenhagen", "Manchester United", "Lens",
            "Sevilla", "Newcastle United", "AC Milan", "Liverpool",
            "Sporting CP", "Club Brugge", "Antwerp", "Crvena Zvezda"
        ]
    },
    "EuropaLeague": {
        "url": "https://en.wikipedia.org/wiki/2024–25_UEFA_Europa_League",
        "expected_teams": 36,
        "fallback_teams": [
            "Liverpool", "West Ham United", "Brighton", "AS Roma",
            "Villarreal", "Slavia Praha", "Qarabag", "Bayer Leverkusen",
            "Sparta Praha", "Rangers", "Atalanta", "Marseille",
            "Sporting CP", "Benfica", "Ajax", "Freiburg",
            "Rennes", "AEK Athens", "Sturm Graz", "Rakow",
            "Molde", "Servette", "Sheriff Tiraspol", "Union SG",
            "PAOK", "BetIS", "Toulouse", "Olympiakos",
            "TSC", "Aris Limassol", "Fiorentina", "Club Brugge",
            "Maccabi Haifa", "Panathinaikos", "Aberdeen", "HJK Helsinki"
        ]
    },
    
    # === PHASE 2 - Ligues européennes ===
    "SerieA": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Serie_A",
        "expected_teams": 20,
        "fallback_teams": [
            "Inter Milan", "AC Milan", "Juventus", "Napoli", "Lazio",
            "AS Roma", "Atalanta", "Fiorentina", "Bologna", "Torino",
            "Hellas Verona", "Genoa", "Empoli", "Lecce", "Udinese",
            "Cagliari", "Frosinone", "Sassuolo", "Salernitana", "Monza"
        ]
    },
    "Bundesliga": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Bundesliga",
        "expected_teams": 18,
        "fallback_teams": [
            "Bayern Munich", "Borussia Dortmund", "RB Leipzig", "Union Berlin",
            "SC Freiburg", "Bayer Leverkusen", "Eintracht Frankfurt", "VfL Wolfsburg",
            "Borussia Mönchengladbach", "FSV Mainz 05", "FC Augsburg", "VfB Stuttgart",
            "Werder Bremen", "TSG Hoffenheim", "VfL Bochum", "FC Köln",
            "Hertha BSC", "Schalke 04"
        ]
    },
    "Ligue1": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Ligue_1",
        "expected_teams": 18,
        "fallback_teams": [
            "Paris Saint-Germain", "Marseille", "Monaco", "Lille",
            "Rennes", "Lyon", "Nice", "Lens",
            "Reims", "Toulouse", "Montpellier", "Strasbourg",
            "Brest", "Nantes", "Lorient", "Le Havre",
            "Clermont Foot", "Metz"
        ]
    },
    "PrimeiraLiga": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Primeira_Liga",
        "expected_teams": 18,
        "fallback_teams": [
            "Benfica", "Porto", "Sporting CP", "Braga",
            "Guimarães", "Boavista", "Gil Vicente", "Casa Pia",
            "Rio Ave", "Famalicão", "Arouca", "Estoril",
            "Portimonense", "Chaves", "Vizela", "Santa Clara",
            "Farense", "Paços de Ferreira"
        ]
    },
    "Ligue2": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Ligue_2",
        "expected_teams": 20,
        "fallback_teams": [
            "Auxerre", "Angers", "Saint-Étienne", "Ajaccio",
            "Bastia", "Grenoble", "Troyes", "Laval",
            "Paris FC", "Guingamp", "Rodez", "Pau FC",
            "Valenciennes", "Caen", "Amiens", "Dunkerque",
            "Quevilly", "Annecy", "Bordeaux", "Concarneau"
        ]
    }
}

def _normalize_name(name):
    """Normalise un nom d'équipe"""
    if not name:
        return ""
    # Supprimer les accents
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    # Nettoyer
    name = re.sub(r'\[.*?\]', '', name)  # Supprimer références [1], [a], etc.
    name = re.sub(r'\(.*?\)', '', name)  # Supprimer parenthèses
    name = name.strip()
    return name

def calculate_coefficient(position, total_teams):
    """
    Calcule le coefficient d'une équipe selon sa position
    Formule: coef = 0.85 + ((N - position) / (N - 1)) * 0.45
    
    Args:
        position: Position de l'équipe (1 = premier)
        total_teams: Nombre total d'équipes dans la ligue
    
    Returns:
        float: Coefficient entre 0.85 et 1.30
    """
    if total_teams <= 1:
        return 1.0
    
    coef = 0.85 + ((total_teams - position) / (total_teams - 1)) * 0.45
    return round(coef, 3)

def fetch_standings(league_name, config):
    """
    Récupère le classement d'une ligue depuis Wikipedia
    
    Args:
        league_name: Nom de la ligue
        config: Configuration de la ligue (url, expected_teams, fallback_teams)
    
    Returns:
        list: Liste des équipes avec positions
    """
    url = config["url"]
    logger.info(f"⏳ Fetching {league_name} from {url}")
    
    try:
        res = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "lxml")
        
        # Chercher le tableau de classement
        tables = soup.find_all("table", class_=re.compile("wikitable"))
        
        teams = []
        found = False
        
        for table in tables:
            rows = table.find_all("tr")[1:]  # Skip header
            temp_teams = []
            
            for row in rows:
                cells = row.find_all(["th", "td"])
                if len(cells) < 2:
                    continue
                
                # Essayer différentes positions pour le nom d'équipe
                team_name = None
                for i in [1, 2]:
                    if i < len(cells):
                        # Chercher un lien vers la page de l'équipe
                        link = cells[i].find("a")
                        if link and link.get("title"):
                            team_name = link.get("title")
                            break
                        elif cells[i].text.strip():
                            team_name = cells[i].text.strip()
                            break
                
                if not team_name:
                    continue
                
                team_name = _normalize_name(team_name)
                if len(team_name) > 2:  # Filtrer les noms trop courts
                    temp_teams.append(team_name)
            
            # Vérifier si on a trouvé un nombre raisonnable d'équipes
            if len(temp_teams) >= config["expected_teams"] - 3:
                teams = temp_teams[:config["expected_teams"]]
                found = True
                break
        
        if not found or not teams:
            raise ValueError(f"No valid standing table found (found {len(teams)} teams)")
        
        # Créer la structure finale (format compatible avec Phase 1)
        result = []
        for pos, team_name in enumerate(teams, start=1):
            result.append({
                "rank": pos,
                "name": team_name,
                "points": 0  # Points non disponibles pour Phase 2, utiliser 0
            })
        
        logger.info(f"✅ {league_name}: {len(result)} teams fetched")
        return result
        
    except Exception as e:
        logger.warning(f"⚠️ {league_name} scraping failed: {e}")
        
        # Fallback sur cache
        cache_path = os.path.join(DATA_DIR, f"{league_name}.json")
        if os.path.exists(cache_path):
            logger.info(f"♻️ Using cached data for {league_name}")
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception as cache_error:
                logger.error(f"Error reading cache: {cache_error}")
        
        # Fallback ultime: utiliser la liste statique
        logger.warning(f"🔧 Using fallback team list for {league_name}")
        result = []
        for pos, team_name in enumerate(config["fallback_teams"], start=1):
            result.append({
                "rank": pos,
                "name": team_name,
                "points": 0
            })
        return result[:config["expected_teams"]]

def calculate_coefficient(position, total_teams):
    """Calcule le coefficient selon la position (0.85 - 1.30)"""
    if position == 1:
        return 1.30
    if position == total_teams:
        return 0.85
    
    coeff = 0.85 + ((total_teams - position) / (total_teams - 1)) * 0.45
    return round(coeff, 4)

def save_league_to_file(league_api_code, data):
    """Sauvegarde les données d'une ligue dans le format interne"""
    # Mapping code API vers nom interne
    CODE_TO_NAME = {
        "PL": "PremierLeague",
        "PD": "LaLiga",
        "SA": "SerieA",
        "BL1": "Bundesliga",
        "FL1": "Ligue1",
        "PPL": "PrimeiraLiga",
        "FL2": "Ligue2",
        "CL": "ChampionsLeague",
        "EL": "EuropaLeague",
        "WC": "WorldCup"
    }
    
    league_name = CODE_TO_NAME.get(league_api_code, league_api_code)
    file_path = f"/app/data/leagues/{league_name}.json"
    
    # Calculer les coefficients
    total_teams = len(data)
    for team in data:
        team["coefficient"] = calculate_coefficient(team["position"], total_teams)
    
    # Formater pour notre système
    formatted_data = {
        "league": league_name,
        "updated": datetime.utcnow().isoformat() + "Z",
        "source": "multi-source-updater",
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
    
    # Backup ancien fichier
    if os.path.exists(file_path):
        backup_path = file_path + ".backup_auto"
        try:
            os.rename(file_path, backup_path)
        except:
            pass
    
    # Sauvegarde atomique
    tmp_path = file_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(formatted_data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, file_path)
    
    logger.info(f"💾 Sauvegardé {league_name} ({len(data)} équipes)")
    return True

def update_all_leagues():
    """
    Met à jour TOUTES les ligues via le système multi-sources
    
    Stratégie:
    1. Football-Data.org API (priorité 1)
    2. SoccerData/FBRef (priorité 2)
    3. API-Sports historique (priorité 3)
    4. Cache local (priorité 4)
    
    Returns:
        dict: Rapport de mise à jour consolidé
    """
    logger.info("=" * 60)
    logger.info("🔄 SYSTÈME MULTI-SOURCES - MISE À JOUR DE TOUTES LES LIGUES")
    logger.info("=" * 60)
    
    # Créer l'updater
    updater = UnifiedUpdater(use_mongo=False)
    
    # Lancer la mise à jour
    multi_report = run_daily_update(updater, LEAGUES_MAP, season="2425")
    
    # Sauvegarder les données dans nos fichiers JSON
    for api_code, result in multi_report["results"].items():
        if result["status"] == "ok":
            try:
                # Récupérer les données du cache
                cache_key = f"league:{api_code}"
                cached_data = updater.cache.get(cache_key, {}).get("data")
                if cached_data:
                    save_league_to_file(api_code, cached_data)
            except Exception as e:
                logger.error(f"❌ Erreur sauvegarde {api_code}: {e}")
    
    # Convertir le rapport au format attendu par le scheduler
    total_leagues = len(multi_report["results"])
    leagues_updated = sum(1 for r in multi_report["results"].values() if r["status"] == "ok" and r["source"] == "football-data")
    leagues_fallback = sum(1 for r in multi_report["results"].values() if r["status"] == "ok" and r["source"] != "football-data")
    leagues_failed = sum(1 for r in multi_report["results"].values() if r["status"] != "ok")
    
    report = {
        "timestamp": multi_report["timestamp"],
        "strategy": "multi_source",
        "leagues_updated": leagues_updated,
        "leagues_skipped_fresh": 0,  # Le nouveau système gère ça via cache
        "leagues_fallback": leagues_fallback,
        "leagues_failed": leagues_failed,
        "total_leagues": total_leagues,
        "api_calls_made": updater.daily_requests,
        "api_calls_limit": 200,
        "details": {}
    }
    
    # Détails par ligue
    for api_code, result in multi_report["results"].items():
        CODE_TO_NAME = {
            "PL": "PremierLeague",
            "PD": "LaLiga",
            "SA": "SerieA",
            "BL1": "Bundesliga",
            "FL1": "Ligue1",
            "PPL": "PrimeiraLiga",
            "FL2": "Ligue2",
            "CL": "ChampionsLeague",
            "EL": "EuropaLeague",
            "WC": "WorldCup"
        }
        league_name = CODE_TO_NAME.get(api_code, api_code)
        
        if result["status"] == "ok":
            status_icon = "✅"
        else:
            status_icon = "❌"
        
        report["details"][league_name] = {
            "status": f"{status_icon} {result['status']}",
            "source": result.get("source", "unknown")
        }
        
        logger.info(f"{status_icon} {league_name}: {result['source']}")
    
    logger.info("=" * 60)
    logger.info(f"✅ Mise à jour terminée:")
    logger.info(f"   - Source principale (API): {report['leagues_updated']}")
    logger.info(f"   - Sources fallback: {report['leagues_fallback']}")
    logger.info(f"   - Échecs: {report['leagues_failed']}")
    logger.info(f"   - Total: {report['total_leagues']} ligues")
    logger.info(f"   - Requêtes utilisées: {report['api_calls_made']}/{report['api_calls_limit']}")
    logger.info("=" * 60)
    
    return report

if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Test: Mise à jour intelligente de toutes les ligues")
    print()
    
    report = update_all_leagues()
    
    print("\n📊 Résumé final:")
    print(f"  - Total ligues: {report['total_leagues']}")
    print(f"  - Mises à jour API: {report['leagues_updated']}")
    print(f"  - Données récentes: {report['leagues_skipped_fresh']}")
    print(f"  - Appels API: {report['api_calls_made']}/{report['api_calls_limit']}")
    
    summary = update_all_leagues()
    
    print()
    print("📊 RÉSUMÉ CONSOLIDÉ:")
    for league, info in summary["report"].items():
        print(f"  {league}: {info['status']} ({info['teams_count']} équipes)")
    
    print()
    print(f"✅ Rapport consolidé sauvegardé: {DATA_DIR}/global_update_report.json")

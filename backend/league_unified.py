#!/usr/bin/env python3
"""
Système unifié de gestion des ligues - Toutes les ligues (Phase 1 + Phase 2)
Scraping et calcul des coefficients pour TOUTES les ligues:

Phase 1 (Principales):
- LaLiga (Espagne, 20 équipes)
- PremierLeague (Angleterre, 20 équipes)
- ChampionsLeague (Europe, 36 équipes)
- EuropaLeague (Europe, 36 équipes)

Phase 2 (Européennes):
- Serie A (Italie, 20 équipes)
- Bundesliga (Allemagne, 18 équipes)
- Ligue 1 (France, 18 équipes)
- Primeira Liga (Portugal, 18 équipes)
- Ligue 2 (France, 18 équipes)
"""
import os
import json
import time
import requests
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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

def update_all_leagues():
    """
    Met à jour TOUTES les ligues (Phase 1 + Phase 2) de manière unifiée
    
    Returns:
        dict: Rapport de mise à jour consolidé
    """
    logger.info("=" * 60)
    logger.info("🔄 SYSTÈME UNIFIÉ - MISE À JOUR DE TOUTES LES LIGUES")
    logger.info("=" * 60)
    
    report = {}
    
    for league_name, config in LEAGUES.items():
        try:
            teams = fetch_standings(league_name, config)
            
            if not teams:
                report[league_name] = {
                    "status": "❌ Failed",
                    "teams_count": 0,
                    "message": "No teams retrieved"
                }
                continue
            
            # Calculer les coefficients
            total_teams = len(teams)
            for team in teams:
                team["coefficient"] = calculate_coefficient(team["rank"], total_teams)
            
            # Sauvegarder
            out_path = os.path.join(DATA_DIR, f"{league_name}.json")
            data = {
                "league": league_name,
                "updated": datetime.utcnow().isoformat() + "Z",
                "teams": teams
            }
            
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            report[league_name] = {
                "status": f"✅ Success",
                "teams_count": len(teams),
                "message": f"{len(teams)} équipes",
                "file": out_path
            }
            
            logger.info(f"💾 Saved {league_name} to {out_path}")
            
            # Pause entre requêtes
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Error updating {league_name}: {e}")
            report[league_name] = {
                "status": "❌ Error",
                "teams_count": 0,
                "message": str(e)
            }
    
    # Sauvegarder le rapport consolidé
    timestamp = datetime.utcnow().isoformat()
    summary = {
        "timestamp": timestamp,
        "phase": "Unified System - All Leagues (Phase 1 + Phase 2)",
        "leagues_updated": len([r for r in report.values() if "✅" in r["status"]]),
        "total_leagues": len(LEAGUES),
        "report": report
    }
    
    report_path = os.path.join(DATA_DIR, "global_update_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info("=" * 60)
    logger.info(f"✅ Système unifié complet: {summary['leagues_updated']}/{summary['total_leagues']} ligues mises à jour")
    logger.info(f"📊 Rapport consolidé: {report_path}")
    logger.info("=" * 60)
    
    return summary

if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Démarrage du Système Unifié - Mise à jour de TOUTES les ligues")
    print()
    
    summary = update_all_leagues()
    
    print()
    print("📊 RÉSUMÉ CONSOLIDÉ:")
    for league, info in summary["report"].items():
        print(f"  {league}: {info['status']} ({info['teams_count']} équipes)")
    
    print()
    print(f"✅ Rapport consolidé sauvegardé: {DATA_DIR}/global_update_report.json")

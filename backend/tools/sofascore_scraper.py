#!/usr/bin/env python3
# /app/backend/tools/sofascore_scraper.py
"""
SofaScore Scraper - Classements, Résultats et Fixtures
-------------------------------------------------------
Scraping des données depuis SofaScore.com (gratuit, pas d'API key nécessaire)

⚠️ AVERTISSEMENT:
- Le scraping peut être bloqué si trop de requêtes
- Structure HTML peut changer sans préavis
- Utilisez avec modération (rate limiting intégré)
- Football-Data.org reste le backup officiel

Documentation: https://www.sofascore.com
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
import os

logger = logging.getLogger(__name__)

# =========================================
# ⚙️ CONFIGURATION
# =========================================

SOFA_BASE = "https://www.sofascore.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

DATA_DIR = "/app/data/leagues"
REQUEST_LOG_FILE = "/app/logs/sofascore_requests.log"

# Limite de sécurité: max 300 requêtes/jour
MAX_REQUESTS_PER_DAY = 300
REQUEST_DELAY = 1.2  # secondes entre chaque requête

# Mapping des ligues vers les URLs SofaScore
LEAGUE_URLS = {
    "LaLiga": "/tournament/laliga/8",
    "PremierLeague": "/tournament/premier-league/17",
    "SerieA": "/tournament/serie-a/23",
    "Ligue1": "/tournament/ligue-1/34",
    "Bundesliga": "/tournament/bundesliga/35",
    "PrimeiraLiga": "/tournament/liga-portugal/238",
    "Ligue2": "/tournament/ligue-2/182",
    "ChampionsLeague": "/tournament/uefa-champions-league/7",
    "EuropaLeague": "/tournament/uefa-europa-league/679",
}

# =========================================
# 📊 GESTION DES REQUÊTES
# =========================================

def get_request_count_today():
    """Compte le nombre de requêtes effectuées aujourd'hui"""
    if not os.path.exists(REQUEST_LOG_FILE):
        return 0
    
    today = datetime.now(timezone.utc).date()
    count = 0
    
    try:
        with open(REQUEST_LOG_FILE, 'r') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    log_date = datetime.fromisoformat(log['timestamp']).date()
                    if log_date == today:
                        count += 1
                except:
                    continue
    except:
        return 0
    
    return count

def log_request(league, url, status):
    """Enregistre une requête dans le log"""
    os.makedirs(os.path.dirname(REQUEST_LOG_FILE), exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "league": league,
        "url": url,
        "status": status
    }
    
    with open(REQUEST_LOG_FILE, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

def can_make_request():
    """Vérifie si on peut faire une requête (limite quotidienne)"""
    count = get_request_count_today()
    if count >= MAX_REQUESTS_PER_DAY:
        logger.warning(f"⚠️ Limite quotidienne SofaScore atteinte ({MAX_REQUESTS_PER_DAY})")
        return False
    return True

def rate_limit_pause():
    """Pause entre les requêtes pour éviter le bannissement"""
    time.sleep(REQUEST_DELAY)

# =========================================
# 🌐 SCRAPER - CLASSEMENTS
# =========================================

def get_league_standings(league_name):
    """
    Récupère le classement d'une ligue depuis SofaScore
    
    Args:
        league_name: Nom de la ligue (ex: "LaLiga")
    
    Returns:
        dict: Données du classement ou None en cas d'erreur
    """
    if not can_make_request():
        return None
    
    if league_name not in LEAGUE_URLS:
        logger.error(f"❌ Ligue inconnue: {league_name}")
        return None
    
    league_url = LEAGUE_URLS[league_name]
    url = f"{SOFA_BASE}{league_url}/standings"
    
    try:
        logger.info(f"🌐 Scraping {league_name} standings from SofaScore")
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        log_request(league_name, url, response.status_code)
        rate_limit_pause()
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP {response.status_code} for {league_name}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Chercher le tableau de classement
        # SofaScore utilise des classes dynamiques, on cherche les patterns
        teams_data = []
        
        # Méthode 1: Chercher les éléments de classement
        standings_rows = soup.find_all("div", class_=re.compile("standings"))
        
        if not standings_rows:
            # Méthode 2: Chercher dans les scripts JSON (SofaScore charge souvent les données en JSON)
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "standings" in script.string:
                    # Extraire le JSON des standings
                    try:
                        # Parser le JSON embarqué
                        json_match = re.search(r'standings":\s*(\[.*?\])', script.string)
                        if json_match:
                            standings_json = json.loads(json_match.group(1))
                            for team in standings_json:
                                teams_data.append({
                                    "rank": team.get("position", 0),
                                    "name": team.get("team", {}).get("name", "Unknown"),
                                    "points": team.get("points", 0)
                                })
                            break
                    except:
                        continue
        
        if not teams_data:
            logger.warning(f"⚠️ No standings data found for {league_name}")
            return None
        
        logger.info(f"✅ Scraped {len(teams_data)} teams from {league_name}")
        
        return {
            "league": league_name,
            "standings": teams_data,
            "source": "sofascore"
        }
        
    except Exception as e:
        logger.error(f"❌ Error scraping {league_name}: {e}")
        log_request(league_name, url, "error")
        return None

# =========================================
# 📝 CONVERSION AU FORMAT INTERNE
# =========================================

def calculate_coefficient(position, total_teams):
    """Calcule le coefficient selon la position (0.85 - 1.30)"""
    if position == 1:
        return 1.30
    if position == total_teams:
        return 0.85
    
    coeff = 0.85 + ((total_teams - position) / (total_teams - 1)) * 0.45
    return round(coeff, 4)

def convert_to_internal_format(scraped_data):
    """
    Convertit les données scrapées au format interne
    
    Args:
        scraped_data: Données brutes du scraper
    
    Returns:
        dict: Format interne standardisé
    """
    if not scraped_data or not scraped_data.get("standings"):
        return None
    
    league_name = scraped_data["league"]
    standings = scraped_data["standings"]
    
    teams = []
    total_teams = len(standings)
    
    for team_data in standings:
        rank = team_data.get("rank", 0)
        name = team_data.get("name", "Unknown")
        points = team_data.get("points", 0)
        
        coefficient = calculate_coefficient(rank, total_teams)
        
        teams.append({
            "rank": rank,
            "name": name,
            "points": points,
            "coefficient": coefficient
        })
    
    return {
        "league": league_name,
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "sofascore",
        "teams": teams
    }

def save_league_standings(league_name, data):
    """Sauvegarde les classements dans un fichier JSON"""
    if not data:
        return False
    
    os.makedirs(DATA_DIR, exist_ok=True)
    file_path = os.path.join(DATA_DIR, f"{league_name}.json")
    
    # Backup de l'ancien fichier
    if os.path.exists(file_path):
        backup_path = file_path + ".backup_sofascore"
        try:
            with open(file_path, 'r') as f:
                old_data = json.load(f)
            with open(backup_path, 'w') as f:
                json.dump(old_data, f, indent=2)
            logger.info(f"💾 Backup créé: {backup_path}")
        except:
            pass
    
    # Sauvegarde atomique
    tmp_path = file_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    os.replace(tmp_path, file_path)
    logger.info(f"💾 Saved {league_name} standings to {file_path}")
    return True

# =========================================
# 🔄 MISE À JOUR COMPLÈTE
# =========================================

def update_all_leagues(leagues_to_update=None):
    """
    Met à jour les ligues spécifiées ou toutes si None
    
    Args:
        leagues_to_update: Liste des noms de ligues à mettre à jour
    
    Returns:
        dict: Rapport de mise à jour
    """
    if leagues_to_update is None:
        leagues_to_update = list(LEAGUE_URLS.keys())
    
    logger.info(f"🔄 Starting SofaScore scraping")
    logger.info(f"📋 Ligues à scraper: {', '.join(leagues_to_update)}")
    
    requests_before = get_request_count_today()
    logger.info(f"📊 Requêtes déjà effectuées aujourd'hui: {requests_before}/{MAX_REQUESTS_PER_DAY}")
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "leagues_updated": [],
        "leagues_failed": [],
        "requests_made": 0,
        "source": "sofascore"
    }
    
    for league_name in leagues_to_update:
        if not can_make_request():
            logger.warning(f"⚠️ Limite quotidienne atteinte, arrêt du scraping")
            break
        
        # Scraper les données
        scraped_data = get_league_standings(league_name)
        
        if scraped_data:
            # Convertir au format interne
            internal_data = convert_to_internal_format(scraped_data)
            
            if internal_data:
                # Sauvegarder
                if save_league_standings(league_name, internal_data):
                    report["leagues_updated"].append(league_name)
                    logger.info(f"✅ {league_name} scraped successfully ({len(internal_data['teams'])} teams)")
                else:
                    report["leagues_failed"].append(league_name)
                    logger.error(f"❌ Failed to save {league_name}")
            else:
                report["leagues_failed"].append(league_name)
                logger.error(f"❌ Failed to convert {league_name} data")
        else:
            report["leagues_failed"].append(league_name)
            logger.error(f"❌ Failed to scrape {league_name}")
        
        report["requests_made"] += 1
    
    logger.info(f"✅ Scraping complete: {len(report['leagues_updated'])} updated, {len(report['leagues_failed'])} failed")
    logger.info(f"📊 Total requêtes aujourd'hui: {get_request_count_today()}/{MAX_REQUESTS_PER_DAY}")
    
    return report

# =========================================
# 🧪 TESTS
# =========================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🧪 Test: Scraping LaLiga depuis SofaScore")
    data = get_league_standings("LaLiga")
    if data:
        internal = convert_to_internal_format(data)
        if internal:
            print(f"✅ {len(internal['teams'])} équipes scrapées")
            print(f"Top 5:")
            for team in internal['teams'][:5]:
                print(f"  {team['rank']}. {team['name']} - {team['points']} pts - coeff {team['coefficient']}")
    
    print(f"\n📊 Requêtes effectuées aujourd'hui: {get_request_count_today()}/{MAX_REQUESTS_PER_DAY}")

#!/usr/bin/env python3
# /app/backend/tools/football_data_standings.py
"""
Football-Data.org Integration pour les classements de ligues
-------------------------------------------------------------
Récupère les classements depuis Football-Data.org API.
IMPORTANT: Limite de 10 requêtes/minute, donc on optimise les appels.

Documentation: https://www.football-data.org/documentation/quickstart
"""

import os
import json
import requests
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# =========================================
# ⚙️ CONFIGURATION
# =========================================

API_KEY = "ad9959577fd349ba99b299612668a5cb"
API_BASE_URL = "https://api.football-data.org/v4"
DATA_DIR = "/app/data/leagues"
REQUEST_LOG_FILE = "/app/logs/football_data_standings_requests.log"

# Limite: 10 requêtes/minute
REQUEST_DELAY = 7  # 7 secondes entre chaque requête pour rester sous la limite

# Mapping des ligues vers les IDs Football-Data.org
LEAGUE_IDS = {
    "LaLiga": "PD",  # Primera Division (Spain)
    "PremierLeague": "PL",  # Premier League (England)
    "SerieA": "SA",  # Serie A (Italy)
    "Ligue1": "FL1",  # Ligue 1 (France)
    "Bundesliga": "BL1",  # Bundesliga (Germany)
    "PrimeiraLiga": "PPL",  # Primeira Liga (Portugal)
    "ChampionsLeague": "CL",  # UEFA Champions League
    "EuropaLeague": "EL",  # UEFA Europa League
}

# =========================================
# 📊 GESTION DES REQUÊTES
# =========================================

def log_request(league, status):
    """Enregistre une requête dans le log"""
    os.makedirs(os.path.dirname(REQUEST_LOG_FILE), exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "league": league,
        "status": status
    }
    
    with open(REQUEST_LOG_FILE, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

def get_requests_count_today():
    """Compte les requêtes effectuées aujourd'hui"""
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

# =========================================
# 🌐 API REQUESTS
# =========================================

def fetch_league_standings(league_name):
    """
    Récupère le classement d'une ligue depuis Football-Data.org
    
    Args:
        league_name: Nom de la ligue (ex: "LaLiga", "PremierLeague")
    
    Returns:
        dict: Données du classement ou None en cas d'erreur
    """
    if league_name not in LEAGUE_IDS:
        logger.error(f"❌ Ligue inconnue: {league_name}")
        return None
    
    league_code = LEAGUE_IDS[league_name]
    
    headers = {
        "X-Auth-Token": API_KEY
    }
    
    url = f"{API_BASE_URL}/competitions/{league_code}/standings"
    
    try:
        logger.info(f"🌐 Fetching {league_name} standings from Football-Data.org (code: {league_code})")
        response = requests.get(url, headers=headers, timeout=30)
        
        log_request(league_name, response.status_code)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Successfully fetched {league_name} standings")
            return data
        elif response.status_code == 429:
            logger.warning(f"⚠️ Rate limit atteinte, attendez un moment")
            return None
        else:
            logger.error(f"❌ API error {response.status_code}: {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error fetching {league_name}: {e}")
        log_request(league_name, "error")
        return None

# =========================================
# 📝 CONVERSION ET SAUVEGARDE
# =========================================

def calculate_coefficient(position, total_teams):
    """Calcule le coefficient selon la position (0.85 - 1.30)"""
    if position == 1:
        return 1.30
    if position == total_teams:
        return 0.85
    
    # Formule linéaire
    coeff = 0.85 + ((total_teams - position) / (total_teams - 1)) * 0.45
    return round(coeff, 4)

def convert_to_internal_format(api_data, league_name):
    """
    Convertit les données Football-Data.org au format interne
    
    Args:
        api_data: Données brutes de l'API
        league_name: Nom de la ligue
    
    Returns:
        dict: Format interne standardisé
    """
    if not api_data or not api_data.get("standings"):
        return None
    
    # Football-Data.org retourne les standings dans standings[0].table
    try:
        standings_data = api_data["standings"][0]["table"]
    except (KeyError, IndexError):
        logger.error(f"❌ Invalid API response structure for {league_name}")
        return None
    
    teams = []
    total_teams = len(standings_data)
    
    for team_data in standings_data:
        rank = team_data["position"]
        team_name = team_data["team"]["name"]
        points = team_data["points"]
        
        coefficient = calculate_coefficient(rank, total_teams)
        
        teams.append({
            "rank": rank,
            "name": team_name,
            "points": points,
            "coefficient": coefficient
        })
    
    return {
        "league": league_name,
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "football-data.org",
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
        backup_path = file_path + ".backup_auto"
        os.rename(file_path, backup_path)
        logger.info(f"💾 Backup créé: {backup_path}")
    
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
        leagues_to_update: Liste des noms de ligues à mettre à jour, ou None pour toutes
    
    Returns:
        dict: Rapport de mise à jour
    """
    if leagues_to_update is None:
        leagues_to_update = list(LEAGUE_IDS.keys())
    
    logger.info(f"🔄 Starting league update from Football-Data.org")
    logger.info(f"📋 Ligues à mettre à jour: {', '.join(leagues_to_update)}")
    
    requests_before = get_requests_count_today()
    logger.info(f"📊 Requêtes déjà effectuées aujourd'hui: {requests_before}")
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "leagues_updated": [],
        "leagues_failed": [],
        "requests_made": 0
    }
    
    for i, league_name in enumerate(leagues_to_update):
        if league_name not in LEAGUE_IDS:
            logger.warning(f"⚠️ Ligue inconnue ignorée: {league_name}")
            continue
        
        # Attendre entre les requêtes (sauf pour la première)
        if i > 0:
            logger.info(f"⏳ Attente de {REQUEST_DELAY} secondes...")
            time.sleep(REQUEST_DELAY)
        
        # Récupérer les données
        api_data = fetch_league_standings(league_name)
        
        if api_data:
            # Convertir au format interne
            internal_data = convert_to_internal_format(api_data, league_name)
            
            if internal_data:
                # Sauvegarder
                if save_league_standings(league_name, internal_data):
                    report["leagues_updated"].append(league_name)
                    logger.info(f"✅ {league_name} updated successfully ({len(internal_data['teams'])} teams)")
                else:
                    report["leagues_failed"].append(league_name)
                    logger.error(f"❌ Failed to save {league_name}")
            else:
                report["leagues_failed"].append(league_name)
                logger.error(f"❌ Failed to convert {league_name} data")
        else:
            report["leagues_failed"].append(league_name)
            logger.error(f"❌ Failed to fetch {league_name}")
        
        report["requests_made"] += 1
    
    logger.info(f"✅ League update complete: {len(report['leagues_updated'])} updated, {len(report['leagues_failed'])} failed")
    logger.info(f"📊 Total requêtes aujourd'hui: {get_requests_count_today()}")
    
    # Sauvegarder le rapport
    report_path = os.path.join(DATA_DIR, "auto_update_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report

# =========================================
# 🧪 TESTS
# =========================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test: récupérer une ligue
    print("🧪 Test: Récupération LaLiga")
    data = fetch_league_standings("LaLiga")
    if data:
        internal = convert_to_internal_format(data, "LaLiga")
        if internal:
            print(f"✅ {len(internal['teams'])} équipes récupérées")
            print(f"Top 5:")
            for team in internal['teams'][:5]:
                print(f"  {team['rank']}. {team['name']} - {team['points']} pts - coeff {team['coefficient']}")
    
    print(f"\n📊 Requêtes effectuées aujourd'hui: {get_requests_count_today()}")

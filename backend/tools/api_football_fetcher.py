#!/usr/bin/env python3
# /app/backend/tools/api_football_fetcher.py
"""
API-Football Integration pour les classements de ligues
--------------------------------------------------------
Récupère les classements depuis API-Football avec gestion des limites de requêtes.
Limite: 100 requêtes/jour sur le plan gratuit.

Documentation: https://www.api-football.com/documentation-v3
"""

import os
import json
import requests
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# =========================================
# ⚙️ CONFIGURATION
# =========================================

API_KEY = "3e36c6fa41308b964597a6d5e8d97d35"
API_BASE_URL = "https://v3.football.api-sports.io"
DATA_DIR = "/app/data/leagues"
REQUEST_LOG_FILE = "/app/logs/api_football_requests.log"

# Limite de requêtes: 100/jour
MAX_REQUESTS_PER_DAY = 100

# Mapping des ligues vers les IDs API-Football
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

# Saison actuelle
CURRENT_SEASON = 2024  # Format API-Football utilise l'année de début

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

def can_make_request():
    """Vérifie si on peut faire une requête (limite quotidienne)"""
    count = get_request_count_today()
    return count < MAX_REQUESTS_PER_DAY

# =========================================
# 🌐 API REQUESTS
# =========================================

def fetch_league_standings(league_name):
    """
    Récupère le classement d'une ligue depuis API-Football
    
    Args:
        league_name: Nom de la ligue (ex: "LaLiga", "PremierLeague")
    
    Returns:
        dict: Données du classement ou None en cas d'erreur
    """
    if not can_make_request():
        logger.warning(f"⚠️ Limite quotidienne de requêtes atteinte ({MAX_REQUESTS_PER_DAY})")
        return None
    
    if league_name not in LEAGUE_IDS:
        logger.error(f"❌ Ligue inconnue: {league_name}")
        return None
    
    league_id = LEAGUE_IDS[league_name]
    
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }
    
    url = f"{API_BASE_URL}/standings"
    params = {
        "league": league_id,
        "season": CURRENT_SEASON
    }
    
    try:
        logger.info(f"🌐 Fetching {league_name} standings from API-Football (ID: {league_id})")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        log_request(league_name, response.status_code)
        
        if response.status_code == 200:
            data = response.json()
            
            # Vérifier la structure de la réponse
            if data.get("results", 0) > 0 and data.get("response"):
                logger.info(f"✅ Successfully fetched {league_name} standings")
                return data
            else:
                logger.warning(f"⚠️ No standings data for {league_name}")
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
    Convertit les données API-Football au format interne
    
    Args:
        api_data: Données brutes de l'API
        league_name: Nom de la ligue
    
    Returns:
        dict: Format interne standardisé
    """
    if not api_data or not api_data.get("response"):
        return None
    
    # API-Football retourne les standings dans response[0].league.standings[0]
    try:
        standings_data = api_data["response"][0]["league"]["standings"][0]
    except (KeyError, IndexError):
        logger.error(f"❌ Invalid API response structure for {league_name}")
        return None
    
    teams = []
    total_teams = len(standings_data)
    
    for team_data in standings_data:
        rank = team_data["rank"]
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
        "source": "api-football",
        "teams": teams
    }

def save_league_standings(league_name, data):
    """Sauvegarde les classements dans un fichier JSON"""
    if not data:
        return False
    
    os.makedirs(DATA_DIR, exist_ok=True)
    file_path = os.path.join(DATA_DIR, f"{league_name}.json")
    
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

def update_all_leagues():
    """
    Met à jour toutes les ligues disponibles
    
    Returns:
        dict: Rapport de mise à jour
    """
    logger.info("🔄 Starting full league update from API-Football")
    
    request_count_before = get_request_count_today()
    remaining = MAX_REQUESTS_PER_DAY - request_count_before
    
    logger.info(f"📊 Requêtes restantes aujourd'hui: {remaining}/{MAX_REQUESTS_PER_DAY}")
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "leagues_updated": [],
        "leagues_failed": [],
        "requests_made": 0,
        "requests_remaining": remaining
    }
    
    for league_name in LEAGUE_IDS.keys():
        if not can_make_request():
            logger.warning(f"⚠️ Limite quotidienne atteinte, arrêt de la mise à jour")
            break
        
        # Récupérer les données
        api_data = fetch_league_standings(league_name)
        
        if api_data:
            # Convertir au format interne
            internal_data = convert_to_internal_format(api_data, league_name)
            
            if internal_data:
                # Sauvegarder
                if save_league_standings(league_name, internal_data):
                    report["leagues_updated"].append(league_name)
                    logger.info(f"✅ {league_name} updated successfully")
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
    
    request_count_after = get_request_count_today()
    report["requests_remaining"] = MAX_REQUESTS_PER_DAY - request_count_after
    
    logger.info(f"✅ League update complete: {len(report['leagues_updated'])} updated, {len(report['leagues_failed'])} failed")
    logger.info(f"📊 Requêtes utilisées: {report['requests_made']}, restantes: {report['requests_remaining']}")
    
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
            print(f"Top 3: {internal['teams'][:3]}")
    
    print("\n📊 Requêtes utilisées aujourd'hui:", get_request_count_today())

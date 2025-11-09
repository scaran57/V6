#!/usr/bin/env python3
# /app/backend/ufa/ufa_auto_validate.py
"""
UFA Auto-Validate & Auto-Train
--------------------------------
Vérifie automatiquement les nouveaux scores réels depuis l'API Football-Data.org,
compare avec les matchs OCR avant-match, valide les correspondances,
et déclenche l'apprentissage UFA.

Intègre la clé API et un délai automatique entre chaque requête pour rester
dans les limites du forfait gratuit.

Usage:
    python /app/backend/ufa/ufa_auto_validate.py
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz, process
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# =========================================
# ⚙️ CONFIGURATION GÉNÉRALE
# =========================================

API_KEY = "ad9959577fd349ba99b299612668a5cb"
API_URL = "https://api.football-data.org/v4/matches"
DATA_FILE = "/app/data/real_scores.jsonl"
TEAM_MAP_FILE = "/app/data/team_map.json"
LOG_FILE = "/app/logs/ufa_auto_train.log"

# Délai entre requêtes (6 sec minimum pour plan gratuit)
REQUEST_DELAY = 6

# Thresholds
FUZZY_THRESHOLD = 80
DUPLICATE_WINDOW_DAYS = 7

# =========================================
# 🧠 INITIALISATION LOGGING
# =========================================
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [AUTO-VALIDATE] %(message)s",
)

# =========================================
# 🧩 OUTILS
# =========================================
def load_jsonl(path):
    """Charge un fichier JSONL"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def save_jsonl(path, data):
    """Sauvegarde un fichier JSONL"""
    with open(path, "w", encoding="utf-8") as f:
        for d in data:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

def fuzzy_match_team(name, team_map):
    """Trouve la meilleure correspondance d'équipe avec fuzzy matching"""
    best_match = process.extractOne(name, team_map.keys(), scorer=fuzz.token_sort_ratio)
    if best_match and best_match[1] >= FUZZY_THRESHOLD:
        return best_match[0], team_map[best_match[0]]
    return None, "Unknown"

# =========================================
# ⚽ RÉCUPÉRATION SCORES API
# =========================================
def fetch_real_scores():
    """Récupère les matchs terminés des 2 derniers jours depuis Football-Data.org"""
    headers = {"X-Auth-Token": API_KEY}
    today = datetime.utcnow().date()
    from_date = today - timedelta(days=2)
    to_date = today
    url = f"{API_URL}?dateFrom={from_date}&dateTo={to_date}"

    logging.info(f"Fetching results from {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            logging.error(f"API error: {resp.status_code} {resp.text[:200]}")
            return []

        matches = resp.json().get("matches", [])
        logging.info(f"{len(matches)} matches fetched from API")
        return matches
    except Exception as e:
        logging.error(f"Error fetching from API: {e}")
        return []

# =========================================
# 🔍 VALIDATION AUTOMATIQUE
# =========================================
def auto_validate_scores():
    """
    Fonction principale : récupère les scores réels depuis l'API Football-Data.org,
    les valide et les ajoute à real_scores.jsonl, puis déclenche le training UFA.
    """
    logging.info("Starting UFA Auto-Validate process...")

    # Charger base locale
    data = load_jsonl(DATA_FILE)
    team_map = {}
    if os.path.exists(TEAM_MAP_FILE):
        with open(TEAM_MAP_FILE, "r", encoding="utf-8") as f:
            team_map = json.load(f)
        logging.info(f"Loaded team_map with {len(team_map)} teams")

    # Récupérer les scores réels depuis l'API
    api_matches = fetch_real_scores()
    if not api_matches:
        logging.info("No matches fetched from API")
        return

    validated = 0
    duplicates = 0
    new_entries = []

    for match in api_matches:
        if match["status"] != "FINISHED":
            continue

        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]
        home_score = match["score"]["fullTime"]["home"]
        away_score = match["score"]["fullTime"]["away"]
        utc_date = match["utcDate"]
        league = match["competition"]["name"]

        # Skip if scores are None (some finished matches may not have scores yet)
        if home_score is None or away_score is None:
            continue

        # Normalisation fuzzy
        home_norm, league_home = fuzzy_match_team(home, team_map)
        away_norm, league_away = fuzzy_match_team(away, team_map)
        final_league = league_home if league_home != "Unknown" else league_away

        # Éviter doublons (fenêtre 7 jours)
        exists = any(
            d for d in data
            if d.get("home_team") == (home_norm or home) 
            and d.get("away_team") == (away_norm or away)
            and abs((datetime.utcnow() - datetime.fromisoformat(d.get("date", d.get("timestamp", "2000-01-01T00:00:00")))).days) <= DUPLICATE_WINDOW_DAYS
        )
        if exists:
            duplicates += 1
            continue

        entry = {
            "league": final_league if final_league != "Unknown" else league,
            "home_team": home_norm or home,
            "away_team": away_norm or away,
            "home_goals": home_score,
            "away_goals": away_score,
            "date": utc_date,
            "timestamp": utc_date,
            "source": "auto-validate",
            "validated": True,
            "validated_at": datetime.utcnow().isoformat()
        }
        data.append(entry)
        new_entries.append(entry)
        validated += 1

        logging.info(f"✅ Added {home_norm or home} vs {away_norm or away} ({home_score}-{away_score}) [{final_league if final_league != 'Unknown' else league}]")
        
        # Respecter la limite API (6 secondes entre requêtes)
        time.sleep(REQUEST_DELAY)

    if validated > 0:
        save_jsonl(DATA_FILE, data)
        logging.info(f"Auto-validation terminée : {validated} nouveaux matchs ajoutés, {duplicates} doublons ignorés.")
        
        # Entraînement auto
        try:
            from ufa.training.trainer import train_from_real_matches
            logging.info("📈 Triggering UFA retraining...")
            result = train_from_real_matches()
            logging.info(f"UFA training result: {result.get('status', 'unknown')}")
        except Exception as e:
            logging.error(f"Error triggering UFA training: {e}")
    else:
        logging.info(f"Aucun nouveau match validé. {duplicates} doublons ignorés.")

# =========================================
# 🚀 EXECUTION DIRECTE
# =========================================
if __name__ == "__main__":
    try:
        auto_validate_scores()
    except Exception as e:
        logging.error(f"Fatal error in auto-validate: {e}", exc_info=True)

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

# ---------- Entrypoint ----------
if __name__ == "__main__":
    _log("ufa_auto_validate started")
    try:
        process_pending_entries()
    except Exception as e:
        _log(f"Fatal error in ufa_auto_validate: {e}")
    _log("ufa_auto_validate finished")

# /app/backend/tools/odds_api_integration.py
"""
The Odds API Integration
Récupère les cotes sportives en temps réel et les stocke pour comparaison avec UFAv3
"""
import os
import time
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict
import requests

# Configuration
DATA_DIR = "/app/data"
ODDS_JSONL = os.path.join(DATA_DIR, "odds_data.jsonl")
LOG_PATH = "/app/logs/odds_integration.log"
DEFAULT_REGION = os.getenv("ODDS_API_REGION", "eu")

# Lecture de la clé API depuis l'environnement (recommandé)
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "d6dc490f5f50e3b13a61a301840ed336")

BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Ligues à surveiller (sport_key selon The Odds API)
LEAGUE_MAPPING = {
    "soccer_epl": "Premier League",
    "soccer_spain_la_liga": "La Liga",
    "soccer_france_ligue_one": "Ligue 1",
    "soccer_italy_serie_a": "Serie A",
    "soccer_germany_bundesliga": "Bundesliga"
}

# Configuration du logging
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


def write_jsonl(path: str, obj: dict):
    """Écrit un objet JSON en mode append dans un fichier JSONL"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def fetch_odds_for_sport(sport_key: str, region: str = DEFAULT_REGION, markets: List[str] = None) -> Optional[List[dict]]:
    """
    Récupère les cotes pour un sport donné depuis The Odds API.
    
    Args:
        sport_key: Identifiant du sport (ex: 'soccer_epl')
        region: Région des bookmakers ('eu', 'uk', 'us')
        markets: Types de marchés à récupérer
    
    Returns:
        Liste des matchs avec leurs cotes, ou None en cas d'erreur
    """
    if markets is None:
        markets = ["h2h"]  # Head-to-head (résultat du match)
    
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": region,
        "markets": ",".join(markets),
        "oddsFormat": "decimal"
    }
    
    url = f"{BASE_URL}/{sport_key}/odds"
    
    try:
        r = requests.get(url, params=params, timeout=20)
        
        if r.status_code != 200:
            logging.error(f"Odds API error {r.status_code}: {r.text}")
            return None
        
        logging.info(f"Fetched odds for {sport_key}: {len(r.json())} matches")
        return r.json()
        
    except Exception as e:
        logging.exception(f"Exception fetching odds for {sport_key}")
        return None


def normalize_team_name(name: str) -> str:
    """Normalise le nom d'une équipe pour faciliter le matching"""
    return name.strip()


def ingest_odds_once():
    """
    Récupère les cotes pour toutes les ligues configurées et les stocke dans odds_data.jsonl.
    Cette fonction est appelée périodiquement par le scheduler.
    
    Returns:
        int: Nombre de matchs récupérés
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    count = 0
    fetched_at = datetime.utcnow().isoformat()
    
    logging.info("=== Starting odds ingestion ===")
    
    for sport_key, league_name in LEAGUE_MAPPING.items():
        logging.info(f"Fetching odds for {league_name} ({sport_key})")
        data = fetch_odds_for_sport(sport_key)
        
        if not data:
            logging.warning(f"No data for {sport_key}")
            continue
        
        for item in data:
            try:
                record = {
                    "fetched_at": fetched_at,
                    "sport_key": item.get("sport_key"),
                    "league_name": league_name,
                    "commence_time": item.get("commence_time"),
                    "home_team": normalize_team_name(item.get("home_team", "")),
                    "away_team": normalize_team_name(item.get("away_team", "")),
                    "bookmakers": item.get("bookmakers", []),
                    "raw": item
                }
                write_jsonl(ODDS_JSONL, record)
                count += 1
            except Exception as e:
                logging.exception(f"Failed to write odds record: {e}")
    
    logging.info(f"=== Ingested {count} odds records at {fetched_at} ===")
    return count


def load_latest_odds() -> List[dict]:
    """
    Charge les cotes depuis odds_data.jsonl (les plus récentes en premier).
    
    Returns:
        Liste des enregistrements de cotes
    """
    if not os.path.exists(ODDS_JSONL):
        return []
    
    out = []
    with open(ODDS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    
    return out[::-1]  # Plus récent en premier


def find_best_market(bookmakers: List[dict], market="h2h") -> Optional[dict]:
    """
    Trouve le meilleur bookmaker/marché avec le plus d'outcomes disponibles.
    
    Args:
        bookmakers: Liste des bookmakers
        market: Type de marché à chercher
    
    Returns:
        Dict avec bookmaker et market, ou None
    """
    best = None
    
    for bm in bookmakers:
        for m in bm.get("markets", []):
            if m.get("key") == market:
                outcomes = m.get("outcomes", [])
                if best is None or len(outcomes) > len(best.get("outcomes", [])):
                    best = {
                        "bookmaker": bm.get("key"),
                        "market": m,
                        "bookmaker_title": bm.get("title")
                    }
    
    return best


def implied_prob_from_decimal(odds: float) -> float:
    """
    Calcule la probabilité implicite à partir d'une cote décimale.
    
    Args:
        odds: Cote décimale
    
    Returns:
        Probabilité (0-1)
    """
    try:
        return round(1.0 / float(odds), 6)
    except Exception:
        return 0.0


def get_latest_odds_for_match(home: str, away: str, league: Optional[str] = None) -> Optional[dict]:
    """
    Recherche les cotes les plus récentes pour un match donné.
    Utilise un matching partiel (substring) pour la robustesse.
    
    Args:
        home: Nom de l'équipe à domicile
        away: Nom de l'équipe à l'extérieur
        league: Ligue (optionnel)
    
    Returns:
        Dict avec bookmaker, markets (h2h avec home_odds, away_odds, draw_odds), fetched_at
    """
    latest = load_latest_odds()
    home_l = home.lower().strip()
    away_l = away.lower().strip()
    
    for rec in latest:
        h = rec.get("home_team", "").lower()
        a = rec.get("away_team", "").lower()
        
        # Matching partiel pour robustesse
        if home_l in h and away_l in a:
            bookmakers = rec.get("bookmakers", [])
            best = find_best_market(bookmakers, market="h2h")
            
            out = {
                "fetched_at": rec.get("fetched_at"),
                "commence_time": rec.get("commence_time"),
                "league_name": rec.get("league_name"),
                "bookmaker": None,
                "markets": {}
            }
            
            if best:
                out["bookmaker"] = best.get("bookmaker_title") or best.get("bookmaker")
                outcomes = best.get("market", {}).get("outcomes", [])
                
                # Mapper les outcomes
                m = {}
                for o in outcomes:
                    name = o.get("name", "").lower()
                    odd = o.get("price")
                    
                    if home_l in name:
                        m["home_odds"] = odd
                        m["home_prob"] = implied_prob_from_decimal(odd)
                    elif away_l in name:
                        m["away_odds"] = odd
                        m["away_prob"] = implied_prob_from_decimal(odd)
                    elif "draw" in name or name in ["draw", "tie", "x"]:
                        m["draw_odds"] = odd
                        m["draw_prob"] = implied_prob_from_decimal(odd)
                
                out["markets"]["h2h"] = m
            
            return out
    
    return None


def get_ingestion_stats() -> dict:
    """
    Retourne des statistiques sur les cotes récupérées.
    
    Returns:
        Dict avec nombre total, dernière mise à jour, ligues couvertes
    """
    if not os.path.exists(ODDS_JSONL):
        return {
            "total_records": 0,
            "last_update": None,
            "leagues": []
        }
    
    records = load_latest_odds()
    
    if not records:
        return {
            "total_records": 0,
            "last_update": None,
            "leagues": []
        }
    
    leagues = set(r.get("league_name") for r in records if r.get("league_name"))
    
    return {
        "total_records": len(records),
        "last_update": records[0].get("fetched_at") if records else None,
        "leagues": list(leagues)
    }


if __name__ == "__main__":
    # CLI simple : ingestion unique
    print("🔍 Récupération des cotes depuis The Odds API...")
    count = ingest_odds_once()
    print(f"✅ {count} matchs récupérés et stockés dans {ODDS_JSONL}")
    
    # Afficher statistiques
    stats = get_ingestion_stats()
    print(f"\n📊 Statistiques :")
    print(f"  - Total records : {stats['total_records']}")
    print(f"  - Dernière màj : {stats['last_update']}")
    print(f"  - Ligues : {', '.join(stats['leagues'])}")

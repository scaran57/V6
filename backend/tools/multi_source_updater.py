"""
multi_source_updater.py
Module unifié pour récupérer standings / results / FIFA ranking / enrichissements
Sources:
 - Football-Data.org (API) --> primaire
 - soccerdata (FBRef, via package) --> fallback riche
 - DBfoot (scraping HTML) --> fallback secondaire
 - SoccerWiki (scraping HTML) --> enrichissement méta joueurs / clubs
 - FIFA.com (scraping ranking) --> ranking nations
Fonctionnalités:
 - cache local (JSON)
 - retry + backoff
 - anti-ban (rotation UA, pauses aléatoires)
 - option MongoDB ingestion
 - scheduler simple (run once / daily)
Usage:
 - importer UnifiedUpdater et appeler update_league(...) ou run_daily_update()
"""

import os
import time
import json
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import requests
from bs4 import BeautifulSoup

# optional imports (installer dans requirements)
try:
    import soccerdata as sd
except Exception:
    sd = None

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

# -----------------------
# CONFIG
# -----------------------
LOG_FILE = "/app/logs/multi_source_updater.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

CACHE_PATH = "/app/data/leagues/multi_source_cache.json"
os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "ad9959577fd349ba99b299612668a5cb")
FOOTBALL_DATA_API_KEY_2 = os.getenv("FOOTBALL_DATA_API_KEY_2", "cdd478991a6842cb904e0ed8fa3c8807")  # Backup key
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
USE_MONGO = MongoClient is not None and os.getenv("USE_MONGO", "false").lower() == "true"

# Anti-ban / rate limit
DAILY_MAX_REQUESTS = int(os.getenv("DAILY_MAX_REQUESTS", "200"))
MIN_SLEEP = float(os.getenv("ANTI_BAN_MIN_SLEEP", "1.0"))
MAX_SLEEP = float(os.getenv("ANTI_BAN_MAX_SLEEP", "2.5"))

# retry config
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 5  # seconds * attempt

# user agents rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/114.0",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 Chrome/116.0"
]

# -----------------------
# UTIL: cache, sleep, headers
# -----------------------
def load_cache() -> Dict[str, Any]:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Load cache failed: {e}")
        return {}

def save_cache(cache: Dict[str, Any]):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Save cache failed: {e}")

def random_sleep():
    s = random.uniform(MIN_SLEEP, MAX_SLEEP)
    logging.debug(f"anti-ban sleep {s:.2f}s")
    time.sleep(s)

def headers():
    return {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html,application/json"}

# -----------------------
# Optional MongoDB connector
# -----------------------
mongo_client = None
if USE_MONGO and MongoClient:
    try:
        mongo_client = MongoClient(MONGO_URL)
        logging.info("MongoDB client initialized")
    except Exception as e:
        mongo_client = None
        logging.error(f"MongoDB init failed: {e}")

# -----------------------
# Football-Data API wrapper
# -----------------------
def get_standings_football_data(league_code: str) -> Optional[List[Dict[str, Any]]]:
    """
    league_code: ex. 'PL' (Premier League), 'FL1' (Ligue 1), 'BL1' (Bundesliga)...
    Utilise 2 clés en rotation pour doubler la capacité
    """
    if not FOOTBALL_DATA_API_KEY:
        logging.warning("Football-Data API key not set")
        return None

    url = f"{FOOTBALL_DATA_BASE}/competitions/{league_code}/standings"
    
    # Essayer avec la clé principale d'abord, puis la backup
    keys_to_try = [FOOTBALL_DATA_API_KEY]
    if FOOTBALL_DATA_API_KEY_2:
        keys_to_try.append(FOOTBALL_DATA_API_KEY_2)
    
    for key_idx, api_key in enumerate(keys_to_try):
        hdr = {"X-Auth-Token": api_key}
        attempt = 0
        while attempt < RETRY_ATTEMPTS:
            try:
                resp = requests.get(url, headers=hdr, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    # standardize
                    table = data.get("standings", [])
                    if not table:
                        return None
                    # take first group (usually TOTAL)
                    rows = table[0].get("table", [])
                    result = []
                    for r in rows:
                        team = r.get("team", {})
                        result.append({
                            "team": team.get("name"),
                            "position": r.get("position"),
                            "points": r.get("points"),
                            "played": r.get("playedGames"),
                            "won": r.get("won"),
                            "draw": r.get("draw"),
                            "lost": r.get("lost"),
                            "for": r.get("goalsFor"),
                            "against": r.get("goalsAgainst")
                        })
                    return result
                elif resp.status_code == 429:
                    # rate limit, try next key
                    logging.warning(f"Football-Data rate limit reached on key {key_idx+1}, trying next...")
                    break  # Sortir de la boucle retry, essayer la clé suivante
                else:
                    logging.warning(f"Football-Data HTTP {resp.status_code}")
                    break  # Sortir et essayer la clé suivante
            except Exception as e:
                logging.warning(f"Football-Data exception with key {key_idx+1}: {e}")
                time.sleep(RETRY_BACKOFF * (attempt + 1))
            attempt += 1
    
    return None

# -----------------------
# SoccerData (FBRef via package) fallback
# -----------------------
def get_standings_soccerdata(league_slug: str, season: str = "2425") -> Optional[List[Dict[str, Any]]]:
    """
    league_slug examples: 'ENG-Premier League' or 'FRA-Ligue 1' for soccerdata/FBref wrapper.
    Requires `soccerdata` package installed.
    """
    if sd is None:
        logging.warning("soccerdata package not available")
        return None
    try:
        # using FBref wrapper if available
        fb = sd.FBref(leagues=[league_slug], seasons=[season])
        stats = fb.read_team_season_stats()
        
        if stats is None or stats.empty:
            logging.warning(f"No data from SoccerData for {league_slug}")
            return None
        
        # Reset index and sort by points
        df = stats.reset_index()
        if 'Pts' in df.columns:
            df = df.sort_values('Pts', ascending=False).reset_index(drop=True)
        
        results = []
        for idx, row in df.iterrows():
            team_name = None
            if 'team' in row:
                team_name = row['team']
            elif 'Squad' in row:
                team_name = row['Squad']
            else:
                if hasattr(row, 'name') and isinstance(row.name, tuple):
                    team_name = row.name[0] if row.name else "Unknown"
                else:
                    team_name = "Unknown"
            
            results.append({
                "team": str(team_name),
                "position": idx + 1,
                "points": int(row.get('Pts', 0)),
                "played": int(row.get('MP', row.get('Pld', 0)))
            })
        return results
    except Exception as e:
        logging.warning(f"SoccerData FBref error: {e}")
        return None

# -----------------------
# Ligue 2 scraper (ligue1.com)
# -----------------------
def get_standings_ligue2() -> Optional[List[Dict[str, Any]]]:
    """
    Scrape le classement de Ligue 2 depuis ligue1.com
    
    Returns:
        list: Liste des équipes avec position, nom et points
    """
    url = "https://www.ligue1.com/classement/ligue2"
    
    try:
        logging.info(f"🌐 Scraping Ligue 2 depuis {url}")
        random_sleep()
        
        response = requests.get(url, headers=headers(), timeout=15)
        
        if response.status_code != 200:
            logging.error(f"❌ Ligue 2 HTTP {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        standings = []

        # Méthode 1 : table.standings-table
        rows = soup.select("table.standings-table tbody tr")
        
        if not rows:
            # Méthode 2 : Essayer d'autres sélecteurs
            rows = soup.select("table tbody tr")
        
        if not rows:
            # Méthode 3 : Chercher toutes les tables
            tables = soup.find_all("table")
            for table in tables:
                rows = table.select("tbody tr")
                if rows and len(rows) > 10:  # Au moins 10 équipes
                    break
        
        if not rows:
            logging.warning(f"⚠️ Aucune ligne trouvée pour Ligue 2")
            return None

        for row in rows:
            try:
                # Essayer plusieurs sélecteurs
                pos_elem = row.select_one(".position") or row.select_one("td:nth-child(1)")
                team_elem = row.select_one(".club-name") or row.select_one(".team-name") or row.select_one("td:nth-child(2)")
                pts_elem = row.select_one(".points") or row.select_one("td:nth-last-child(1)")
                
                if not (pos_elem and team_elem and pts_elem):
                    continue
                
                pos = pos_elem.get_text(strip=True)
                team = team_elem.get_text(strip=True)
                pts = pts_elem.get_text(strip=True)
                
                # Nettoyer et convertir
                try:
                    position = int(pos.replace('.', '').replace('#', '').strip())
                    points = int(pts.strip())
                except:
                    continue
                
                standings.append({
                    "team": team,
                    "position": position,
                    "points": points,
                    "played": None  # Pas toujours disponible
                })
            except Exception as e:
                logging.debug(f"Erreur parsing ligne Ligue 2: {e}")
                continue

        if standings:
            logging.info(f"✅ Ligue 2 : {len(standings)} équipes scrapées")
            return standings
        else:
            logging.warning(f"⚠️ Aucune donnée extraite pour Ligue 2")
            return None
            
    except Exception as e:
        logging.error(f"❌ Erreur scraping Ligue 2: {e}")
        return None

# -----------------------
# Europa League scraper (uefa.com)
# -----------------------
def get_standings_europa_league() -> Optional[List[Dict[str, Any]]]:
    """
    Scrape le classement de l'Europa League depuis uefa.com
    
    Returns:
        list: Liste des équipes avec position, nom et points (tous groupes combinés)
    """
    url = "https://fr.uefa.com/uefaeuropaleague/standings/"
    
    try:
        logging.info(f"🌐 Scraping Europa League depuis {url}")
        random_sleep()
        
        response = requests.get(url, headers=headers(), timeout=15)
        
        if response.status_code != 200:
            logging.error(f"❌ Europa League HTTP {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        all_standings = []
        position_counter = 1

        # Chercher les groupes
        groups = soup.select("section.standings-group") or soup.select("div.standings-group")
        
        if not groups:
            # Fallback : chercher toutes les tables
            groups = soup.find_all("table")
        
        if not groups:
            logging.warning(f"⚠️ Aucun groupe trouvé pour Europa League")
            return None

        for group in groups:
            try:
                # Lignes du tableau
                rows = group.select("table.standings-table tbody tr") or group.select("tbody tr")
                
                if not rows:
                    continue

                for row in rows:
                    try:
                        # Essayer plusieurs sélecteurs
                        team_elem = (row.select_one(".team-name") or 
                                   row.select_one(".club-name") or 
                                   row.select_one("td:nth-child(2)") or
                                   row.select_one("td.team"))
                        
                        pts_elem = (row.select_one(".points") or 
                                  row.select_one("td:nth-last-child(1)") or
                                  row.select_one("td.pts"))
                        
                        if not (team_elem and pts_elem):
                            continue
                        
                        team = team_elem.get_text(strip=True)
                        pts = pts_elem.get_text(strip=True)
                        
                        # Convertir
                        try:
                            points = int(pts.strip())
                        except:
                            continue
                        
                        all_standings.append({
                            "team": team,
                            "position": position_counter,
                            "points": points,
                            "played": None
                        })
                        
                        position_counter += 1
                        
                    except Exception as e:
                        logging.debug(f"Erreur parsing ligne Europa League: {e}")
                        continue
                        
            except Exception as e:
                logging.debug(f"Erreur parsing groupe Europa League: {e}")
                continue

        if all_standings:
            logging.info(f"✅ Europa League : {len(all_standings)} équipes scrapées")
            return all_standings
        else:
            logging.warning(f"⚠️ Aucune donnée extraite pour Europa League")
            return None
            
    except Exception as e:
        logging.error(f"❌ Erreur scraping Europa League: {e}")
        return None

# -----------------------
# DBfoot scraper fallback (simple)
# -----------------------
def get_standings_dbfoot(league_url: str) -> Optional[List[Dict[str, Any]]]:
    """
    league_url: full URL to DBfoot league page that contains standings table.
    Example: 'https://db-foot.com/en/competition/england/premier-league/standings'
    This is a light-weight parser; adapt selectors to actual page structure.
    """
    try:
        random_sleep()
        resp = requests.get(league_url, headers=headers(), timeout=12)
        if resp.status_code != 200:
            logging.warning(f"DBfoot HTTP {resp.status_code} for {league_url}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            logging.warning("DBfoot table not found")
            return None
        rows = table.find_all("tr")
        results = []
        for r in rows[1:]:
            cols = [c.get_text(strip=True) for c in r.find_all("td")]
            if len(cols) < 2:
                continue
            # heuristique: position, team, played, points typical
            try:
                position = int(cols[0])
                team = cols[1]
                played = int(cols[2]) if len(cols) > 2 and cols[2].isdigit() else None
                points = int(cols[-1]) if cols[-1].isdigit() else None
            except Exception:
                position = None
                team = cols[1] if len(cols) > 1 else cols[0]
                played = None
                points = None
            results.append({
                "team": team,
                "position": position,
                "played": played,
                "points": points
            })
        return results
    except Exception as e:
        logging.warning(f"DBfoot exception: {e}")
        return None

# -----------------------
# SoccerWiki scraper (enrichment: club/player metadata)
# -----------------------
def get_club_info_soccerwiki(club_slug_url: str) -> Optional[Dict[str, Any]]:
    """
    club_slug_url: full URL to club page on soccerwiki.org
    Example: 'https://www.soccerwiki.org/team.php?teamID=1234'
    This function scrapes basic metadata like founded, stadium, market value etc.
    """
    try:
        random_sleep()
        r = requests.get(club_slug_url, headers=headers(), timeout=10)
        if r.status_code != 200:
            logging.warning(f"SoccerWiki HTTP {r.status_code} for {club_slug_url}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        info = {}
        # heuristic: find table with class or dt/dd pairs
        # This is generic; adapt if needed.
        for tr in soup.select("table tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
            if len(tds) >= 2:
                key = tds[0].strip(": ")
                val = tds[1]
                info[key] = val
        return info
    except Exception as e:
        logging.warning(f"SoccerWiki exception: {e}")
        return None

# -----------------------
# FIFA ranking scraper (simple)
# -----------------------
def get_fifa_ranking() -> Optional[List[Dict[str, Any]]]:
    """
    Scrape FIFA ranking page for men's ranking table.
    Note: page structure may change; keep an eye.
    """
    url = "https://www.fifa.com/fifa-world-ranking/men"
    attempt = 0
    while attempt < RETRY_ATTEMPTS:
        try:
            random_sleep()
            r = requests.get(url, headers=headers(), timeout=12)
            if r.status_code != 200:
                logging.warning(f"FIFA ranking HTTP {r.status_code}")
                attempt += 1
                time.sleep(RETRY_BACKOFF * attempt)
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            # find ranking rows - heuristics
            rankings = []
            # search for tables or divs with ranking info
            for row in soup.select("tr"):
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue
                try:
                    rank = int(cols[0].get_text(strip=True))
                    country = cols[1].get_text(strip=True)
                    points_text = cols[2].get_text(strip=True).replace(",", "")
                    points = float(points_text)
                    rankings.append({"rank": rank, "country": country, "points": points})
                except Exception:
                    continue
            if rankings:
                return rankings
            # fallback: try find div-based listing (skipped for brevity)
            attempt += 1
            time.sleep(RETRY_BACKOFF * attempt)
        except Exception as e:
            logging.warning(f"FIFA scrape exception: {e}")
            attempt += 1
            time.sleep(RETRY_BACKOFF * attempt)
    return None

# -----------------------
# Unified Updater class
# -----------------------
class UnifiedUpdater:
    def __init__(self, use_mongo: bool = False):
        self.cache = load_cache()
        self.daily_requests = 0
        self.last_reset = datetime.utcnow().date()
        self.use_mongo = use_mongo and (mongo_client is not None)
        if self.use_mongo:
            self.db = mongo_client.get_database("ufa_data")
        else:
            self.db = None

    def reset_daily_if_needed(self):
        if datetime.utcnow().date() != self.last_reset:
            self.daily_requests = 0
            self.last_reset = datetime.utcnow().date()

    def increment_request(self):
        self.reset_daily_if_needed()
        self.daily_requests += 1
        if self.daily_requests > DAILY_MAX_REQUESTS:
            logging.warning("Daily request budget exceeded")
            raise RuntimeError("Daily request budget exceeded")

    def store_cache(self, key: str, data: Any):
        self.cache[key] = {"timestamp": time.time(), "data": data}
        save_cache(self.cache)

    def load_cache_for(self, key: str, max_age_hours: int = 24):
        v = self.cache.get(key)
        if not v:
            return None
        if (time.time() - v.get("timestamp", 0)) > max_age_hours * 3600:
            return None
        return v.get("data")

    def update_league(self, league_api_code: str, league_soccerdata_slug: str, season: str = "2425"):
        """
        Try Football-Data -> SoccerData -> Custom Scrapers -> DBfoot -> cache
        Returns dict with source & data
        """
        key = f"league:{league_api_code}"
        # 1) Cache check
        cached = self.load_cache_for(key, max_age_hours=24)
        if cached:
            logging.info(f"{league_api_code}: using fresh cache")
            return {"source": "cache", "data": cached}

        # 2) Football-Data
        try:
            self.increment_request()
            fd = get_standings_football_data(league_api_code)
            if fd:
                self.store_cache(key, fd)
                if self.use_mongo:
                    self.db.standings.update_one({"league": league_api_code}, {"$set": {"updated": datetime.utcnow(), "data": fd}}, upsert=True)
                logging.info(f"{league_api_code}: Football-Data OK")
                return {"source": "football-data", "data": fd}
        except Exception as e:
            logging.warning(f"Football-Data failed for {league_api_code}: {e}")

        # 3) SoccerData fallback
        try:
            self.increment_request()
            sd_data = get_standings_soccerdata(league_soccerdata_slug, season)
            if sd_data:
                self.store_cache(key, sd_data)
                if self.use_mongo:
                    self.db.standings.update_one({"league": league_api_code}, {"$set": {"updated": datetime.utcnow(), "data": sd_data}}, upsert=True)
                logging.info(f"{league_api_code}: SoccerData OK")
                return {"source": "soccerdata", "data": sd_data}
        except Exception as e:
            logging.warning(f"SoccerData failed for {league_api_code}: {e}")

        # 4) Custom scrapers fallback (Ligue 2 et Europa League)
        custom_scraper_data = None
        if league_api_code == "FL2":  # Ligue 2
            try:
                self.increment_request()
                custom_scraper_data = get_standings_ligue2()
                if custom_scraper_data:
                    self.store_cache(key, custom_scraper_data)
                    if self.use_mongo:
                        self.db.standings.update_one({"league": league_api_code}, {"$set": {"updated": datetime.utcnow(), "data": custom_scraper_data}}, upsert=True)
                    logging.info(f"{league_api_code}: Ligue2 custom scraper OK")
                    return {"source": "ligue2_scraper", "data": custom_scraper_data}
            except Exception as e:
                logging.warning(f"Ligue 2 scraper failed: {e}")
        
        elif league_api_code == "EL":  # Europa League
            try:
                self.increment_request()
                custom_scraper_data = get_standings_europa_league()
                if custom_scraper_data:
                    self.store_cache(key, custom_scraper_data)
                    if self.use_mongo:
                        self.db.standings.update_one({"league": league_api_code}, {"$set": {"updated": datetime.utcnow(), "data": custom_scraper_data}}, upsert=True)
                    logging.info(f"{league_api_code}: Europa League custom scraper OK")
                    return {"source": "europa_scraper", "data": custom_scraper_data}
            except Exception as e:
                logging.warning(f"Europa League scraper failed: {e}")

        # 5) DBfoot fallback - user must supply appropriate DBfoot URL map externally
        dbfoot_url = None  # placeholder - caller may extend to provide URLs map
        if dbfoot_url:
            try:
                self.increment_request()
                dbf = get_standings_dbfoot(dbfoot_url)
                if dbf:
                    self.store_cache(key, dbf)
                    if self.use_mongo:
                        self.db.standings.update_one({"league": league_api_code}, {"$set": {"updated": datetime.utcnow(), "data": dbf}}, upsert=True)
                    logging.info(f"{league_api_code}: DBfoot OK")
                    return {"source": "dbfoot", "data": dbf}
            except Exception as e:
                logging.warning(f"DBfoot failed for {league_api_code}: {e}")

        # 6) last resort cache (stale)
        if key in self.cache:
            logging.info(f"{league_api_code}: returning stale cache")
            return {"source": "cache_stale", "data": self.cache[key]["data"]}

        logging.error(f"{league_api_code}: no source available")
        return {"source": "none", "data": None}

    def get_fifa_ranking(self):
        key = "fifa:ranking"
        cached = self.load_cache_for(key, max_age_hours=24*7)  # weekly freshness
        if cached:
            return {"source": "cache", "data": cached}
        try:
            self.increment_request()
            ranking = get_fifa_ranking()
            if ranking:
                self.store_cache(key, ranking)
                if self.use_mongo:
                    self.db.fifa.update_one({"id": 1}, {"$set": {"updated": datetime.utcnow(), "data": ranking}}, upsert=True)
                return {"source": "fifa_scrape", "data": ranking}
        except Exception as e:
            logging.warning(f"FIFA ranking fetch failed: {e}")
        if key in self.cache:
            return {"source": "cache_stale", "data": self.cache[key]["data"]}
        return {"source": "none", "data": None}

    def enrich_club_from_soccerwiki(self, club_url):
        try:
            self.increment_request()
            info = get_club_info_soccerwiki(club_url)
            return {"source": "soccerwiki", "data": info}
        except Exception as e:
            logging.warning(f"SoccerWiki enrich failed: {e}")
            return {"source": "none", "data": None}

# -----------------------
# Simple runner / scheduler utility
# -----------------------
def run_daily_update(updater: UnifiedUpdater, leagues_map: Dict[str, str], season: str = "2425"):
    """
    leagues_map: dict mapping API league code -> soccerdata slug
      e.g. {"PL": "ENG-Premier League", "FL1": "FRA-Ligue 1"}
    """
    logging.info("Starting daily unified update")
    report = {"timestamp": datetime.utcnow().isoformat(), "results": {}}
    for api_code, sd_slug in leagues_map.items():
        try:
            random_sleep()
            res = updater.update_league(api_code, sd_slug, season)
            report["results"][api_code] = {"status": "ok" if res["data"] else "none", "source": res["source"]}
            logging.info(f"Updated {api_code} -> {res['source']}")
        except RuntimeError as re:
            logging.error(f"Daily budget exceeded: {re}")
            report["error"] = "budget_exceeded"
            break
        except Exception as e:
            logging.error(f"Error updating {api_code}: {e}")
            report["results"][api_code] = {"status": "error", "error": str(e)}
    # save local report
    try:
        rpt_path = "/app/data/leagues/last_unified_report.json"
        with open(rpt_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"Could not write report: {e}")
    logging.info("Daily unified update finished")
    return report

# -----------------------
# USAGE example (callable)
# -----------------------
if __name__ == "__main__":
    # Map of league codes -> soccerdata slugs
    LEAGUES = {
        "PL": "ENG-Premier League",
        "PD": "ESP-La Liga",
        "SA": "ITA-Serie A",
        "BL1": "GER-Bundesliga",
        "FL1": "FRA-Ligue 1"
    }
    updater = UnifiedUpdater(use_mongo=False)
    report = run_daily_update(updater, LEAGUES, season="2425")
    print(json.dumps(report, indent=2, ensure_ascii=False))

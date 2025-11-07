# /app/backend/league_fetcher.py
"""
Récupération automatique des classements de ligues depuis les sites officiels.
Système de cache avec TTL de 24h et fallback sur anciennes données si échec.
"""
import requests
from bs4 import BeautifulSoup
import json, os, time, unicodedata, re
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DATA_DIR = "/app/data/leagues"
os.makedirs(DATA_DIR, exist_ok=True)
DEFAULT_TTL = 24 * 3600  # 24 heures

# Configuration des ligues avec leurs sources officielles
LEAGUE_CONFIG = {
    "LaLiga": {
        "url": "https://www.laliga.com/en-GB/laliga-easports/standing",
        "method": "scrape_laliga",
        "fallback_file": os.path.join(DATA_DIR, "LaLiga.json")
    },
    "PremierLeague": {
        "url": "https://www.premierleague.com/tables",
        "method": "scrape_premier_league",
        "fallback_file": os.path.join(DATA_DIR, "PremierLeague.json")
    },
    "SerieA": {
        "url": "https://www.legaseriea.it/en/serie-a/standings",
        "method": "scrape_serie_a",
        "fallback_file": os.path.join(DATA_DIR, "SerieA.json")
    },
    "Ligue1": {
        "url": "https://www.ligue1.com/classement",
        "method": "scrape_ligue1",
        "fallback_file": os.path.join(DATA_DIR, "Ligue1.json")
    },
    "Bundesliga": {
        "url": "https://www.bundesliga.com/en/bundesliga/table",
        "method": "scrape_bundesliga",
        "fallback_file": os.path.join(DATA_DIR, "Bundesliga.json")
    },
    "PrimeiraLiga": {
        "url": "https://www.ligaportugal.pt/en/liga/classification/",
        "method": "scrape_primeira_liga",
        "fallback_file": os.path.join(DATA_DIR, "PrimeiraLiga.json")
    }
}

def _save_json(path, obj):
    """Sauvegarde atomique JSON"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def _load_json(path):
    """Charge JSON avec gestion d'erreur"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _normalize_name(name):
    """Normalise le nom d'équipe pour matching"""
    name = re.sub(r"\(.*?\)", "", name)
    name = name.strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in name if not unicodedata.combining(c)])
    name = re.sub(r"\s+", " ", name)
    return name.strip()

def _parse_wikipedia_table(html):
    """Parse le tableau de classement Wikipedia"""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", {"class": "wikitable"})
    
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        header_text = " ".join(headers)
        
        # Vérifier que c'est bien un tableau de classement
        if ("pos" in header_text or "position" in header_text) and ("team" in header_text or "club" in header_text):
            rows = table.find_all("tr")
            results = []
            
            for row in rows[1:]:
                cols = row.find_all(["th", "td"])
                if not cols:
                    continue
                
                texts = [c.get_text(" ", strip=True) for c in cols]
                
                # Trouver la position
                pos = None
                for t in texts:
                    t_clean = t.strip()
                    if re.match(r"^\d+$", t_clean):
                        pos = int(t_clean)
                        break
                
                # Trouver le nom d'équipe (chercher un lien)
                team_cell = None
                for c in cols:
                    a = c.find("a")
                    if a and a.get_text(strip=True):
                        team_cell = a.get_text(strip=True)
                        break
                
                if not team_cell:
                    if len(texts) >= 2:
                        team_cell = texts[1]
                    elif texts:
                        team_cell = texts[0]
                
                if team_cell:
                    team = _normalize_name(team_cell)
                else:
                    team = None
                
                if pos and team:
                    results.append((pos, team))
            
            if results:
                return results
    
    return []

def load_positions():
    """Charge tous les classements"""
    return _load_json(POSITIONS_FILE)

def load_meta():
    """Charge les métadonnées (dernière mise à jour, TTL)"""
    meta = _load_json(METADATA_FILE)
    if "fetched_at" not in meta:
        meta["fetched_at"] = {}
    if "ttl" not in meta:
        meta["ttl"] = DEFAULT_TTL
    return meta

def save_positions(obj):
    """Sauvegarde tous les classements"""
    _save_json(POSITIONS_FILE, obj)

def save_meta(meta):
    """Sauvegarde les métadonnées"""
    _save_json(METADATA_FILE, meta)

def update_league(league_name, force=False):
    """
    Met à jour le classement d'une ligue depuis Wikipedia.
    Utilise le cache si disponible et non expiré (sauf si force=True).
    """
    meta = load_meta()
    ttl = meta.get("ttl", DEFAULT_TTL)
    last = meta.get("fetched_at", {}).get(league_name)
    
    # Vérifier le cache
    if last and not force:
        try:
            last_ts = float(last)
            if time.time() - last_ts < ttl:
                logger.info(f"📊 Classement {league_name} en cache (âge: {int(time.time() - last_ts)}s)")
                data = load_positions()
                return data.get(league_name, {})
        except:
            pass
    
    url = WIKI_MAP.get(league_name)
    if not url:
        logger.warning(f"⚠️ Ligue inconnue: {league_name}")
        return {}
    
    headers = {"User-Agent": "EmergentScoreBot/1.0 (+https://emergentagent.com)"}
    
    try:
        logger.info(f"🌐 Récupération classement {league_name} depuis Wikipedia...")
        r = requests.get(url, headers=headers, timeout=15)
        
        if r.status_code == 200:
            parsed = _parse_wikipedia_table(r.text)
            
            if not parsed:
                logger.warning(f"⚠️ Aucun tableau de classement trouvé pour {league_name}")
                return {}
            
            league_map = {}
            for pos, team in parsed:
                league_map[team] = pos
            
            # Sauvegarder
            all_pos = load_positions()
            all_pos[league_name] = league_map
            save_positions(all_pos)
            
            meta = load_meta()
            meta.setdefault("fetched_at", {})[league_name] = time.time()
            save_meta(meta)
            
            logger.info(f"✅ Classement {league_name} mis à jour: {len(league_map)} équipes")
            return league_map
        else:
            logger.error(f"❌ Erreur HTTP {r.status_code} pour {league_name}")
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération de {league_name}: {e}")
    
    # Fallback sur le cache même expiré
    all_pos = load_positions()
    cached = all_pos.get(league_name, {})
    if cached:
        logger.warning(f"⚠️ Utilisation du cache expiré pour {league_name}")
    return cached

def update_all(leagues=None, force=False):
    """Met à jour tous les classements (ou une liste spécifique)"""
    if leagues is None:
        leagues = list(WIKI_MAP.keys())
    
    result = {}
    for lg in leagues:
        try:
            result[lg] = update_league(lg, force=force)
        except Exception as e:
            logger.error(f"❌ Erreur update {lg}: {e}")
            result[lg] = {}
    
    return result

def get_team_position(team_name, league_name):
    """
    Récupère la position d'une équipe dans une ligue.
    Fuzzy matching pour gérer les variations de noms.
    """
    pos_map = load_positions().get(league_name, {})
    normalized = _normalize_name(team_name)
    
    # Exact match
    if normalized in pos_map:
        return pos_map[normalized]
    
    # Fuzzy match
    for t, p in pos_map.items():
        if normalized == t:
            return p
        # Contient ou est contenu
        if normalized in t or t in normalized:
            return p
    
    return None

if __name__ == "__main__":
    print("🔄 Mise à jour de toutes les ligues...")
    r = update_all(force=True)
    for k, v in r.items():
        print(f"  {k}: {len(v)} équipes")
    print(f"✅ Sauvegardé dans {POSITIONS_FILE}")

# /app/backend/league_fetcher.py
"""
Récupération automatique des classements de ligues depuis Wikipedia.
Système robuste avec parsing standard des tableaux Wikipedia.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Configuration TTL (Time To Live) pour le cache
DEFAULT_TTL = 24 * 3600  # 24 heures en secondes

DATA_DIR = "/app/data/leagues"
os.makedirs(DATA_DIR, exist_ok=True)

# Configuration des ligues avec leurs URLs et méthodes de parsing
LEAGUE_CONFIG = {
    "LaLiga": {
        "url": "https://en.wikipedia.org/wiki/2025–26_La_Liga",
        "method": "scrape_laliga",
        "fallback_file": f"{DATA_DIR}/LaLiga.json"
    },
    "PremierLeague": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Premier_League",
        "method": "scrape_premier_league",
        "fallback_file": f"{DATA_DIR}/PremierLeague.json"
    },
    "SerieA": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Serie_A",
        "method": "scrape_serie_a",
        "fallback_file": f"{DATA_DIR}/SerieA.json"
    },
    "Ligue1": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Ligue_1",
        "method": "scrape_ligue1",
        "fallback_file": f"{DATA_DIR}/Ligue1.json"
    },
    "Bundesliga": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Bundesliga",
        "method": "scrape_bundesliga",
        "fallback_file": f"{DATA_DIR}/Bundesliga.json"
    },
    "PrimeiraLiga": {
        "url": "https://en.wikipedia.org/wiki/2025–26_Primeira_Liga",
        "method": "scrape_primeira_liga",
        "fallback_file": f"{DATA_DIR}/PrimeiraLiga.json"
    },
    "ChampionsLeague": {
        "url": "https://en.wikipedia.org/wiki/2024–25_UEFA_Champions_League",
        "method": "scrape_champions_league",
        "fallback_file": f"{DATA_DIR}/ChampionsLeague.json"
    },
    "EuropaLeague": {
        "url": "https://en.wikipedia.org/wiki/2024–25_UEFA_Europa_League",
        "method": "scrape_europa_league",
        "fallback_file": f"{DATA_DIR}/EuropaLeague.json"
    }
}

# Alias pour compatibilité avec server.py
WIKI_MAP = LEAGUE_CONFIG

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

def scrape_laliga(html):
    """Parse le classement LaLiga officiel"""
    try:
        soup = BeautifulSoup(html, "lxml")
        teams = []
        
        # LaLiga utilise une structure avec des divs/tables spécifiques
        # Chercher les lignes du classement
        rows = soup.find_all("tr", class_=re.compile("standing.*|table-row.*"))
        
        if not rows:
            # Fallback : chercher toute table avec des données de classement
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                break
        
        for i, row in enumerate(rows, 1):
            cols = row.find_all(["td", "th"])
            if len(cols) < 3:
                continue
            
            # Extraire le nom de l'équipe (généralement dans un <a> ou <span>)
            team_name = None
            for col in cols:
                link = col.find("a")
                if link:
                    text = link.get_text(strip=True)
                    if len(text) > 2 and not text.isdigit():
                        team_name = text
                        break
                
                span = col.find("span", class_=re.compile("team.*|club.*"))
                if span:
                    text = span.get_text(strip=True)
                    if len(text) > 2:
                        team_name = text
                        break
            
            if team_name:
                teams.append({
                    "name": _normalize_name(team_name),
                    "rank": i,
                    "points": 0  # Les points peuvent être extraits si besoin
                })
                
                if len(teams) >= 20:  # LaLiga a 20 équipes
                    break
        
        return teams
    except Exception as e:
        logger.error(f"Erreur parsing LaLiga: {e}")
        return []

def scrape_premier_league(html):
    """Parse le classement Premier League officiel"""
    try:
        soup = BeautifulSoup(html, "lxml")
        teams = []
        
        # Premier League utilise des classes spécifiques
        rows = soup.find_all("tr", class_=re.compile("table__row.*"))
        
        if not rows:
            # Fallback
            tables = soup.find_all("table")
            for table in tables:
                tbody = table.find("tbody")
                if tbody:
                    rows = tbody.find_all("tr")
                    break
        
        for i, row in enumerate(rows, 1):
            # Chercher le nom de l'équipe
            team_cell = row.find("td", class_=re.compile("team.*"))
            if not team_cell:
                team_cell = row.find("span", class_=re.compile("team.*|long.*"))
            
            if team_cell:
                team_name = team_cell.get_text(strip=True)
                if len(team_name) > 2:
                    teams.append({
                        "name": _normalize_name(team_name),
                        "rank": i,
                        "points": 0
                    })
                    
                    if len(teams) >= 20:
                        break
        
        return teams
    except Exception as e:
        logger.error(f"Erreur parsing Premier League: {e}")
        return []

def scrape_serie_a(html):
    """Parse Serie A (placeholder - à implémenter phase 2)"""
    logger.warning("Serie A parser pas encore implémenté")
    return []

def scrape_ligue1(html):
    """Parse Ligue 1 (placeholder - à implémenter phase 2)"""
    logger.warning("Ligue 1 parser pas encore implémenté")
    return []

def scrape_bundesliga(html):
    """Parse Bundesliga (placeholder - à implémenter phase 2)"""
    logger.warning("Bundesliga parser pas encore implémenté")
    return []

def scrape_primeira_liga(html):
    """Parse Primeira Liga (placeholder - à implémenter phase 2)"""
    logger.warning("Primeira Liga parser pas encore implémenté")
    return []

def scrape_champions_league(html):
    """
    Parse Champions League - Extrait les équipes participantes.
    Pour la Champions League, on ne peut pas vraiment faire un classement 1-36,
    donc on liste simplement les équipes participantes avec un rang fictif basé
    sur l'ordre alphabétique ou l'ordre d'apparition.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        teams = []
        seen = set()
        
        # Chercher les liens vers les pages d'équipes
        # Les équipes de Champions League ont des liens vers leurs pages wiki
        links = soup.find_all("a", href=re.compile(r"/wiki/.*_F\.?C\.?$|/wiki/.*_United|/wiki/.*_City|/wiki/Real_Madrid|/wiki/FC_Barcelona"))
        
        # Également chercher dans les tableaux de groupes
        tables = soup.find_all("table", class_=re.compile("wikitable"))
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                team_cell = row.find("td", class_=re.compile("team|club"))
                if not team_cell:
                    team_cell = row.find("a")
                
                if team_cell:
                    team_link = team_cell.find("a") if team_cell.name != "a" else team_cell
                    if team_link:
                        team_name = team_link.get_text(strip=True)
                        if len(team_name) > 2 and team_name not in seen:
                            seen.add(team_name)
                            teams.append({
                                "name": _normalize_name(team_name),
                                "rank": len(teams) + 1,
                                "points": 0
                            })
        
        # Si pas assez d'équipes trouvées, chercher tous les liens d'équipes
        if len(teams) < 10:
            all_links = soup.find_all("a")
            for link in all_links:
                text = link.get_text(strip=True)
                href = link.get("href", "")
                
                # Filtrer les liens d'équipes (heuristique)
                if href.startswith("/wiki/") and len(text) > 3 and text not in seen:
                    # Éviter les liens non-équipes
                    skip_words = ["UEFA", "Wikipedia", "League", "Group", "Knockout", "Final", "Season", "Match"]
                    if any(word in text for word in skip_words):
                        continue
                    
                    # Ajouter si ressemble à un nom d'équipe
                    if any(word in text for word in ["FC", "CF", "United", "City", "Madrid", "Barcelona", "Milan", "Juventus", "Bayern", "PSG", "Dortmund", "Liverpool", "Arsenal", "Chelsea", "Manchester"]):
                        seen.add(text)
                        teams.append({
                            "name": _normalize_name(text),
                            "rank": len(teams) + 1,
                            "points": 0
                        })
        
        # Limiter à 36 équipes (nouveau format Champions League)
        teams = teams[:36]
        
        logger.info(f"Champions League: {len(teams)} équipes extraites")
        return teams
        
    except Exception as e:
        logger.error(f"Erreur parsing Champions League: {e}")
        return []

def scrape_europa_league(html):
    """
    Parse Europa League - Extrait les équipes participantes.
    Même logique que Champions League mais pour l'Europa League.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        teams = []
        seen = set()
        
        # Chercher dans les tableaux
        tables = soup.find_all("table", class_=re.compile("wikitable"))
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                team_cell = row.find("td", class_=re.compile("team|club"))
                if not team_cell:
                    team_cell = row.find("a")
                
                if team_cell:
                    team_link = team_cell.find("a") if team_cell.name != "a" else team_cell
                    if team_link:
                        team_name = team_link.get_text(strip=True)
                        if len(team_name) > 2 and team_name not in seen:
                            seen.add(team_name)
                            teams.append({
                                "name": _normalize_name(team_name),
                                "rank": len(teams) + 1,
                                "points": 0
                            })
        
        # Fallback : chercher les liens d'équipes
        if len(teams) < 10:
            all_links = soup.find_all("a")
            for link in all_links:
                text = link.get_text(strip=True)
                href = link.get("href", "")
                
                if href.startswith("/wiki/") and len(text) > 3 and text not in seen:
                    skip_words = ["UEFA", "Wikipedia", "League", "Group", "Knockout", "Final", "Season", "Match"]
                    if any(word in text for word in skip_words):
                        continue
                    
                    if any(word in text for word in ["FC", "CF", "United", "Roma", "Lazio", "Sevilla", "Villarreal", "Ajax", "Feyenoord", "Porto", "Benfica", "Sporting"]):
                        seen.add(text)
                        teams.append({
                            "name": _normalize_name(text),
                            "rank": len(teams) + 1,
                            "points": 0
                        })
        
        # Limiter à 36 équipes (nouveau format)
        teams = teams[:36]
        
        logger.info(f"Europa League: {len(teams)} équipes extraites")
        return teams
        
    except Exception as e:
        logger.error(f"Erreur parsing Europa League: {e}")
        return []

def load_league_data(league_name):
    """Charge les données d'une ligue depuis son fichier JSON"""
    config = LEAGUE_CONFIG.get(league_name)
    if not config:
        return None
    
    filepath = config["fallback_file"]
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def save_league_data(league_name, data):
    """Sauvegarde les données d'une ligue dans son fichier JSON"""
    config = LEAGUE_CONFIG.get(league_name)
    if not config:
        return False
    
    filepath = config["fallback_file"]
    
    # Format standardisé
    output = {
        "league": league_name,
        "updated": datetime.now().isoformat() + "Z",
        "teams": data
    }
    
    try:
        _save_json(filepath, output)
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde {league_name}: {e}")
        return False

def load_positions():
    """Charge tous les classements (format compatible ancien système)"""
    all_standings = {}
    
    for league_name in LEAGUE_CONFIG.keys():
        data = load_league_data(league_name)
        if data and "teams" in data:
            # Convertir au format ancien : {team_name: rank}
            standings = {}
            for team in data["teams"]:
                standings[team["name"]] = team["rank"]
            all_standings[league_name] = standings
    
    return all_standings

def update_league(league_name, force=False):
    """
    Met à jour le classement d'une ligue depuis son site officiel.
    Utilise le cache si disponible et non expiré (sauf si force=True).
    """
    config = LEAGUE_CONFIG.get(league_name)
    if not config:
        logger.warning(f"⚠️ Ligue inconnue: {league_name}")
        return {}
    
    # Vérifier le cache (données locales)
    cached_data = load_league_data(league_name)
    if cached_data and not force:
        try:
            updated_dt = datetime.fromisoformat(cached_data["updated"].replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - updated_dt).total_seconds()
            
            if age_seconds < DEFAULT_TTL:
                logger.info(f"📊 Classement {league_name} en cache (âge: {int(age_seconds/3600)}h)")
                # Retourner au format ancien pour compatibilité
                standings = {team["name"]: team["rank"] for team in cached_data["teams"]}
                return standings
        except Exception as e:
            logger.warning(f"Erreur lecture cache {league_name}: {e}")
    
    # Récupération depuis le site officiel
    url = config["url"]
    method_name = config["method"]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        logger.info(f"🌐 Récupération classement {league_name} depuis {url}...")
        r = requests.get(url, headers=headers, timeout=20)
        
        if r.status_code == 200:
            # Appeler la fonction de parsing appropriée
            parser_func = globals().get(method_name)
            if not parser_func:
                logger.error(f"❌ Parser {method_name} introuvable")
                return _fallback_to_cache(league_name, cached_data)
            
            teams = parser_func(r.text)
            
            if not teams:
                logger.warning(f"⚠️ Aucune équipe extraite pour {league_name}")
                return _fallback_to_cache(league_name, cached_data)
            
            # Sauvegarder
            save_league_data(league_name, teams)
            
            logger.info(f"✅ Classement {league_name} mis à jour: {len(teams)} équipes")
            
            # Retourner au format ancien pour compatibilité
            standings = {team["name"]: team["rank"] for team in teams}
            return standings
        else:
            logger.error(f"❌ Erreur HTTP {r.status_code} pour {league_name}")
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération de {league_name}: {e}")
    
    # Fallback sur le cache
    return _fallback_to_cache(league_name, cached_data)

def _fallback_to_cache(league_name, cached_data):
    """Utilise les données en cache si disponibles"""
    if cached_data and "teams" in cached_data:
        logger.warning(f"⚠️ Utilisation du cache pour {league_name}")
        standings = {team["name"]: team["rank"] for team in cached_data["teams"]}
        return standings
    else:
        logger.error(f"❌ Aucune donnée disponible pour {league_name}")
        return {}

def update_all(leagues=None, force=False):
    """Met à jour tous les classements (ou une liste spécifique)"""
    if leagues is None:
        leagues = list(LEAGUE_CONFIG.keys())
    
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
    print(f"✅ Sauvegardé dans {DATA_DIR}")

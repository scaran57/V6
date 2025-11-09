#!/usr/bin/env python3
"""
OCR Parser + Auto-Mapping Intelligent + Détection Ligues Améliorée
- expose extract_match_info(image_path, manual_home=None, manual_away=None, manual_league=None)
- returns dict: { home_team, away_team, league, home_goals, away_goals, raw_text }
- Détecte les marqueurs de ligues dans le texte OCR (Ligue 1, LaLiga, Bundesliga, etc.)
"""

import re
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, List
from fuzzywuzzy import process
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import json
import datetime

# --- CONFIG ---
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
SCORE_PATTERN = re.compile(r"\b([0-9])\s*[-:]\s*([0-9])\b")

# Patterns de détection de ligues dans le texte OCR
LEAGUE_DETECTION_PATTERNS = {
    "Ligue1": [
        r"ligue\s*1", r"ligue\s*un", r"l1", r"ligue 1 mcdonald",
        r"championnat de france", r"french league"
    ],
    "LaLiga": [
        r"la\s*liga", r"laliga", r"liga\s*santander", r"liga\s*ea\s*sports",
        r"liga\s*espagnole", r"spanish\s*league", r"primera\s*division", r"liga\s*españa"
    ],
    "PremierLeague": [
        r"premier\s*league", r"epl", r"english\s*premier", r"barclays",
        r"league\s*anglaise", r"premier\s*league\s*anglaise"
    ],
    "Bundesliga": [
        r"bundesliga", r"buli", r"1\.\s*bundesliga", r"bundesliga\s*1",
        r"ligue\s*allemande", r"german\s*league"
    ],
    "SerieA": [
        r"serie\s*a", r"seria\s*a", r"calcio\s*serie\s*a", r"serie\s*a\s*tim",
        r"ligue\s*italienne", r"italian\s*league", r"serie\s*a\s*enilive"
    ],
    "Ligue2": [
        r"ligue\s*2", r"ligue\s*deux", r"l2", r"championship\s*france"
    ],
    "PrimeiraLiga": [
        r"primeira\s*liga", r"liga\s*portugal", r"liga\s*nos", r"liga\s*betclic",
        r"portuguese\s*league", r"ligue\s*portugaise", r"portugal\s*league"
    ],
    "Eredivisie": [
        r"eredivisie", r"eredivise", r"dutch\s*league", r"ligue\s*neerlandaise"
    ],
    "Championship": [
        r"championship", r"efl\s*championship", r"english\s*championship"
    ],
    "ChampionsLeague": [
        r"champions\s*league", r"ucl", r"c1", r"uefa\s*champions", r"ligue\s*des\s*champions"
    ],
    "EuropaLeague": [
        r"europa\s*league", r"uel", r"c3", r"uefa\s*europa"
    ]
}

# Table enrichie équipes → ligues
TEAM_LEAGUE_MAP = {
    # 🇫🇷 Ligue 1
    "psg": "Ligue1", "paris": "Ligue1", "paris saint-germain": "Ligue1", "paris saint germain": "Ligue1",
    "marseille": "Ligue1", "olympique de marseille": "Ligue1", "om": "Ligue1",
    "lyon": "Ligue1", "olympique lyonnais": "Ligue1", "ol": "Ligue1",
    "monaco": "Ligue1", "as monaco": "Ligue1",
    "lens": "Ligue1", "rc lens": "Ligue1",
    "lille": "Ligue1", "losc": "Ligue1",
    "rennes": "Ligue1", "stade rennais": "Ligue1",
    "nice": "Ligue1", "ogc nice": "Ligue1",
    "toulouse": "Ligue1", "tfc": "Ligue1",
    "reims": "Ligue1", "strasbourg": "Ligue1", "montpellier": "Ligue1",
    "nantes": "Ligue1", "brest": "Ligue1", "lorient": "Ligue1",
    
    # 🇪🇸 LaLiga
    "real madrid": "LaLiga", "madrid": "LaLiga",
    "barcelona": "LaLiga", "barca": "LaLiga", "fc barcelona": "LaLiga",
    "atletico": "LaLiga", "atletico madrid": "LaLiga", "atlético": "LaLiga",
    "sevilla": "LaLiga", "sevilla fc": "LaLiga",
    "valencia": "LaLiga", "villarreal": "LaLiga",
    "real sociedad": "LaLiga", "sociedad": "LaLiga",
    "real betis": "LaLiga", "betis": "LaLiga",
    "athletic": "LaLiga", "bilbao": "LaLiga", "athletic bilbao": "LaLiga",
    "celta": "LaLiga", "celta vigo": "LaLiga",
    "getafe": "LaLiga", "osasuna": "LaLiga", "girona": "LaLiga",
    "rayo": "LaLiga", "rayo vallecano": "LaLiga",
    
    # 🏴 Premier League
    "manchester city": "PremierLeague", "man city": "PremierLeague", "city": "PremierLeague",
    "manchester united": "PremierLeague", "man united": "PremierLeague", "united": "PremierLeague",
    "liverpool": "PremierLeague", "arsenal": "PremierLeague", "chelsea": "PremierLeague",
    "tottenham": "PremierLeague", "spurs": "PremierLeague",
    "newcastle": "PremierLeague", "brighton": "PremierLeague",
    "aston villa": "PremierLeague", "villa": "PremierLeague",
    "west ham": "PremierLeague", "everton": "PremierLeague",
    "leicester": "PremierLeague", "wolves": "PremierLeague",
    "crystal palace": "PremierLeague", "brentford": "PremierLeague",
    
    # 🇮🇹 Serie A
    "juventus": "SerieA", "juve": "SerieA",
    "inter": "SerieA", "inter milan": "SerieA",
    "milan": "SerieA", "ac milan": "SerieA",
    "napoli": "SerieA", "ssc napoli": "SerieA",
    "roma": "SerieA", "as roma": "SerieA",
    "lazio": "SerieA", "ss lazio": "SerieA",
    "atalanta": "SerieA", "fiorentina": "SerieA",
    "torino": "SerieA", "bologna": "SerieA",
    
    # 🇩🇪 Bundesliga
    "bayern": "Bundesliga", "bayern munich": "Bundesliga", "bayern münchen": "Bundesliga",
    "dortmund": "Bundesliga", "borussia dortmund": "Bundesliga", "bvb": "Bundesliga",
    "leipzig": "Bundesliga", "rb leipzig": "Bundesliga",
    "leverkusen": "Bundesliga", "bayer leverkusen": "Bundesliga",
    "union berlin": "Bundesliga", "frankfurt": "Bundesliga",
    "wolfsburg": "Bundesliga", "gladbach": "Bundesliga",
    "stuttgart": "Bundesliga", "freiburg": "Bundesliga",
    
    # 🇳🇱 Eredivisie
    "ajax": "Eredivisie", "ajax amsterdam": "Eredivisie",
    "psv": "Eredivisie", "psv eindhoven": "Eredivisie",
    "feyenoord": "Eredivisie", "az": "Eredivisie", "az alkmaar": "Eredivisie",
    "twente": "Eredivisie", "utrecht": "Eredivisie",
    
    # 🇵🇹 Primeira Liga
    "benfica": "PrimeiraLiga", "sl benfica": "PrimeiraLiga",
    "porto": "PrimeiraLiga", "fc porto": "PrimeiraLiga",
    "sporting": "PrimeiraLiga", "sporting cp": "PrimeiraLiga",
    "braga": "PrimeiraLiga", "sc braga": "PrimeiraLiga",
    
    # 🇹🇷 Süper Lig  
    "galatasaray": "SuperLig", "fenerbahce": "SuperLig", "fenerbahçe": "SuperLig",
    "besiktas": "SuperLig", "beşiktaş": "SuperLig",
    
    # 🌍 Champions/Europa
    "champions league": "ChampionsLeague", "ucl": "ChampionsLeague",
    "europa league": "EuropaLeague", "uel": "EuropaLeague",
}

TEAM_KEYS = list(TEAM_LEAGUE_MAP.keys())

# --- UTIL ---
def preprocess_image(image_path: str):
    """Prétraitement image pour améliorer OCR"""
    img = Image.open(image_path).convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    return img

def ocr_read(image_path: str) -> str:
    """Lecture OCR du texte"""
    img = preprocess_image(image_path)
    text = pytesseract.image_to_string(img, lang="eng+fra")
    return text

def parse_score(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extraction du score depuis le texte"""
    m = SCORE_PATTERN.search(text)
    if m:
        try:
            return int(m.group(1)), int(m.group(2))
        except:
            return None, None
    return None, None

def normalize_text(t: str) -> str:
    """Normalisation du texte pour recherche"""
    return re.sub(r"[^a-zA-Z0-9\s\-\.:]", " ", t).lower()

def extract_teams_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extraction des équipes avec plusieurs stratégies :
    1) Séparateurs courants (" - ", " vs ", etc.)
    2) Tokens connus directement
    3) Fuzzy matching
    """
    if not text:
        return None, None
    
    raw = text.strip()
    
    # Stratégie 1: séparateurs
    seps = [" - ", " – ", " vs ", " v ", " vs. ", " : ", "\n"]
    for sep in seps:
        if sep in raw:
            parts = [p.strip() for p in raw.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[0], parts[1]
    
    # Stratégie 2: tokens directs
    low = raw.lower()
    found = []
    for team in TEAM_KEYS:
        if team in low:
            found.append(team)
            if len(found) >= 2:
                break
    
    if len(found) == 2:
        return found[0].title(), found[1].title()
    
    # Stratégie 3: fuzzy matching
    candidates = process.extract(low, TEAM_KEYS, limit=5)
    filtered = [c[0] for c in candidates if c[1] >= 70]
    
    if len(filtered) >= 2:
        return filtered[0].title(), filtered[1].title()
    
    return None, None

def detect_league_from_teams(home: Optional[str], away: Optional[str]) -> str:
    """Détection de la ligue basée sur les équipes"""
    if not home and not away:
        return "Unknown"
    
    combined = " ".join(filter(None, [home or "", away or ""])).lower()
    leagues = []
    
    for k, v in TEAM_LEAGUE_MAP.items():
        if k in combined:
            leagues.append(v)
    
    if len(leagues) == 0:
        # Fuzzy single detection
        cand = process.extractOne(combined, TEAM_KEYS)
        if cand and cand[1] >= 75:
            return TEAM_LEAGUE_MAP[cand[0]]
        return "Unknown"
    
    # Si toutes les ligues détectées sont identiques
    if all(x == leagues[0] for x in leagues):
        return leagues[0]
    
    # Ligues différentes => compétition continentale
    if "ChampionsLeague" in leagues or "EuropaLeague" in leagues:
        return "ChampionsLeague"
    
    return leagues[0]

# --- API FUNCTION ---
def extract_match_info(image_path: str,
                       manual_home: Optional[str] = None,
                       manual_away: Optional[str] = None,
                       manual_league: Optional[str] = None) -> Dict:
    """
    Fonction principale d'extraction.
    
    Returns dict:
    {
      'home_team': str|None,
      'away_team': str|None,
      'league': str,
      'home_goals': int|None,
      'away_goals': int|None,
      'raw_text': str,
      'timestamp': iso
    }
    """
    # OCR du texte
    text = ocr_read(image_path)
    
    # Extraction du score
    home_goals, away_goals = parse_score(text)
    
    # Utiliser les valeurs manuelles si fournies
    if manual_home and manual_away:
        home = manual_home.strip()
        away = manual_away.strip()
    else:
        t1, t2 = extract_teams_from_text(text)
        home = t1
        away = t2
    
    # Détection de la ligue (priorité: manuel > détection > Unknown)
    if manual_league:
        league = manual_league
    else:
        league = detect_league_from_teams(home, away)
    
    return {
        "home_team": home,
        "away_team": away,
        "league": league or "Unknown",
        "home_goals": home_goals,
        "away_goals": away_goals,
        "raw_text": text,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# --- TEST ---
if __name__ == "__main__":
    folder = Path("/app/uploads/fdj_captures")
    out = []
    
    if folder.exists():
        print("=" * 70)
        print("TEST OCR PARSER - Extraction Équipes + Ligue")
        print("=" * 70)
        print()
        
        for p in folder.glob("*.[pjPJ]*[ngNG]"):
            info = extract_match_info(str(p))
            print(f"📸 {p.name}")
            print(f"   Équipes: {info.get('home_team', 'N/A')} vs {info.get('away_team', 'N/A')}")
            print(f"   Ligue: {info.get('league', 'Unknown')}")
            print(f"   Score: {info.get('home_goals', '?')}-{info.get('away_goals', '?')}")
            print()
            out.append(info)
        
        print("=" * 70)
        print(f"Total: {len(out)} images analysées")
    else:
        print(f"❌ Dossier introuvable: {folder}")

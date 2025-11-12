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
import cv2
import numpy as np

# --- CONFIG ---
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
SCORE_PATTERN = re.compile(r"\b([0-9])\s*[-:]\s*([0-9])\b")
OCR_MODE = os.getenv("OCR_MODE", "optimized")  # "optimized" ou "legacy"
GOOD_VARIANTS = ["orig", "resize_2x", "sharpen"]

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
    ],
    # === PATCH: Ajout du support "World Cup Qualification" ===
    "WorldCupQualification": [
        r"world\s*cup\s*qualification", r"world\s*cup\s*qualifiers", 
        r"fifa\s*world\s*cup\s*qualifiers", r"wc\s*qualification",
        r"qualif\s*coupe\s*du\s*monde", r"coupe\s*du\s*monde\s*qualification",
        r"world\s*cup\s*qualifying", r"world\s*cup", r"fifa\s*world\s*cup",
        r"eliminatoires\s*coupe\s*du\s*monde", r"eliminatoires\s*cdm"
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
    
    # 🌍 World Cup Qualification (Équipes nationales)
    "norway": "WorldCupQualification", "norvege": "WorldCupQualification", "norvège": "WorldCupQualification",
    "estonia": "WorldCupQualification", "estonie": "WorldCupQualification",
    "azerbaijan": "WorldCupQualification", "azerbaidjan": "WorldCupQualification", "azerbaïdjan": "WorldCupQualification",
    "iceland": "WorldCupQualification", "islande": "WorldCupQualification",
    "france": "WorldCupQualification", "équipe de france": "WorldCupQualification",
    "germany": "WorldCupQualification", "allemagne": "WorldCupQualification",
    "spain": "WorldCupQualification", "espagne": "WorldCupQualification",
    "portugal": "WorldCupQualification",
    "italy": "WorldCupQualification", "italie": "WorldCupQualification",
    "england": "WorldCupQualification", "angleterre": "WorldCupQualification",
    "belgium": "WorldCupQualification", "belgique": "WorldCupQualification",
    "sweden": "WorldCupQualification", "suede": "WorldCupQualification", "suède": "WorldCupQualification",
    "denmark": "WorldCupQualification", "danemark": "WorldCupQualification",
    "finland": "WorldCupQualification", "finlande": "WorldCupQualification",
    "poland": "WorldCupQualification", "pologne": "WorldCupQualification",
    "czech republic": "WorldCupQualification", "tchequie": "WorldCupQualification", "tchéquie": "WorldCupQualification",
    "hungary": "WorldCupQualification", "hongrie": "WorldCupQualification",
    "croatia": "WorldCupQualification", "croatie": "WorldCupQualification",
    "serbia": "WorldCupQualification", "serbie": "WorldCupQualification",
    "switzerland": "WorldCupQualification", "suisse": "WorldCupQualification",
    "netherlands": "WorldCupQualification", "pays-bas": "WorldCupQualification", "hollande": "WorldCupQualification",
    "turkey": "WorldCupQualification", "turquie": "WorldCupQualification",
    "greece": "WorldCupQualification", "grece": "WorldCupQualification", "grèce": "WorldCupQualification",
    "romania": "WorldCupQualification", "roumanie": "WorldCupQualification",
    "scotland": "WorldCupQualification", "ecosse": "WorldCupQualification", "écosse": "WorldCupQualification",
    "wales": "WorldCupQualification", "pays de galles": "WorldCupQualification",
    "ireland": "WorldCupQualification", "irlande": "WorldCupQualification",
    "slovakia": "WorldCupQualification", "slovaquie": "WorldCupQualification",
    "slovenia": "WorldCupQualification", "slovenie": "WorldCupQualification", "slovénie": "WorldCupQualification",
    "ukraine": "WorldCupQualification",
    "georgia": "WorldCupQualification", "georgie": "WorldCupQualification", "géorgie": "WorldCupQualification",
    "bosnia": "WorldCupQualification", "bosnie": "WorldCupQualification",
    "north macedonia": "WorldCupQualification", "macedoine du nord": "WorldCupQualification",
    "lithuania": "WorldCupQualification", "lituanie": "WorldCupQualification",
    "latvia": "WorldCupQualification", "lettonie": "WorldCupQualification",
    "luxembourg": "WorldCupQualification",
    "albania": "WorldCupQualification", "albanie": "WorldCupQualification",
    "kosovo": "WorldCupQualification",
    "cyprus": "WorldCupQualification", "chypre": "WorldCupQualification",
    "malta": "WorldCupQualification", "malte": "WorldCupQualification",
    "israel": "WorldCupQualification", "israël": "WorldCupQualification",
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
    
    Applique le nettoyage automatique sur les noms extraits.
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
                # NOUVEAU: Nettoyer les noms extraits
                home_cleaned = clean_team_name(parts[0])
                away_cleaned = clean_team_name(parts[1])
                
                # Vérifier que les noms nettoyés sont valides
                if home_cleaned and away_cleaned:
                    return home_cleaned, away_cleaned
    
    # Stratégie 2: tokens directs
    low = raw.lower()
    found = []
    for team in TEAM_KEYS:
        if team in low:
            found.append(team)
            if len(found) >= 2:
                break
    
    if len(found) == 2:
        # Nettoyer les noms
        home_cleaned = clean_team_name(found[0].title())
        away_cleaned = clean_team_name(found[1].title())
        if home_cleaned and away_cleaned:
            return home_cleaned, away_cleaned
    
    # Stratégie 3: fuzzy matching
    candidates = process.extract(low, TEAM_KEYS, limit=5)
    filtered = [c[0] for c in candidates if c[1] >= 70]
    
    if len(filtered) >= 2:
        home_cleaned = clean_team_name(filtered[0].title())
        away_cleaned = clean_team_name(filtered[1].title())
        if home_cleaned and away_cleaned:
            return home_cleaned, away_cleaned
    
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

def detect_league_from_text(text: str) -> Optional[str]:
    """
    Détecte la ligue à partir du texte OCR brut en cherchant les marqueurs.
    Retourne le nom de la ligue ou None si aucune détection.
    PRIORITÉ ABSOLUE sur le mapping par équipe.
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Chercher chaque pattern de ligue
    for league_name, patterns in LEAGUE_DETECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return league_name
    
    return None

def detect_all_leagues_in_text(text: str) -> List[Tuple[str, int]]:
    """
    Détecte TOUTES les ligues présentes dans le texte avec leur position.
    Crucial pour les images avec plusieurs matchs de différentes ligues.
    """
    if not text:
        return []
    
    text_lower = text.lower()
    detected = []
    
    for league_name, patterns in LEAGUE_DETECTION_PATTERNS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                detected.append((league_name, match.start(), match.group()))
    
    # Trier par position dans le texte
    detected.sort(key=lambda x: x[1])
    
    return detected

# --- API FUNCTION ---
def clean_team_name(name: str) -> str:
    """
    Nettoie un nom d'équipe en supprimant le texte parasite.
    GARDE les marqueurs de ligues dans le texte global, mais les retire des noms d'équipes.
    """
    if not name:
        return name
    
    # ÉTAPE 1: Supprimer les marqueurs de ligue des noms d'équipes
    league_markers = [
        r'Liga\s+Portugal', r'Primeira\s+Liga', r'Liga\s+Nos',
        r'Ligue\s+1', r'Ligue\s+2', r'La\s*Liga', r'LaLiga',
        r'Premier\s+League', r'Bundesliga', r'Serie\s+A',
        r'Champions\s+League', r'Europa\s+League',
        r'Ligue\s+des\s+Champions', r'Championship'
    ]
    
    cleaned = name
    for marker in league_markers:
        cleaned = re.sub(marker, ' ', cleaned, flags=re.IGNORECASE)
    
    # ÉTAPE 2: Patterns à supprimer des NOMS D'ÉQUIPES
    noise_patterns = [
        # Horaires (tous les formats)
        r'À\s*\d{1,2}h\d{2}',
        r'A\s*\d{1,2}h\d{2}',
        r'\d{1,2}h\d{2}',
        r'[ÀA]\s*\d{1,2}:\d{2}',
        r'\d{1,2}:\d{2}',  # Format 16:30, 20:45
        r'\d{2}h',          # Format 16h, 20h
        
        # Éléments d'interface bookmaker (PRIORITÉ)
        r'\bParis\b(?!\s+Saint)',  # "Paris" seul (pas "Paris Saint-Germain")
        r'Pari(?:er)?(?:\s+sur\s+mesure)?',  # "Parier", "Pari sur mesure"
        r'\bStats?\b',      # "Stat", "Stats"
        r'\bCompos?\b',     # "Compo", "Compos"
        r'\bCote(?:s)?\b',  # "Cote", "Cotes"
        r'sur\s+mesure',
        r'\bParis\s+Pari',  # "Paris Pari sur mesure"
        r'\bParier\b',
        r'\bS\'inscrire\b', # Bouton inscription
        
        # Texte publicitaire et promotionnel
        r'\bBonus\b',
        r'\bOffre\b',
        r'\bGratuit\b',
        r'\bPromo(?:tion)?\b',
        
        # Codes et symboles parasites
        r'\d{5,}\s*OCH',  # Codes comme "15552 OCH"
        r'neue\s+\w+',    # "neue ts", etc.
        r'[=\)]?\s*[JFL]e', # "=) Je", "=) Le", etc.
        
        # Lignes de séparation et symboles
        r'^[-_<>]+$',
        r'^\s*[<>]\s*$',
        
        # Texte technique
        r'MT\s*\d*',
        r'\(\s*[=\)]+\s*\)',
        
        # Symboles et caractères isolés
        r'[©®™§¶•]',  # Symboles spéciaux
        r'[@#$%&*]',
    ]
    
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    # ÉTAPE 3: Couper au premier pattern de données (scores, cotes)
    # Si on voit des patterns comme "1-0", "6,80", on coupe tout après
    data_cutoff = re.search(r'(\d+[-:]\d+|\d+,\d+|\d+\s+\d+\s+\d+)', cleaned)
    if data_cutoff:
        cleaned = cleaned[:data_cutoff.start()]
    
    # ÉTAPE 4: Supprimer les nombres isolés au début
    cleaned = re.sub(r'^\s*\d+\s+', '', cleaned)
    
    # ÉTAPE 5: Nettoyer les espaces multiples et trim
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # ÉTAPE 6: Limiter à 5 premiers mots (un nom d'équipe typique)
    words = cleaned.split()
    if len(words) > 5:
        cleaned = ' '.join(words[:5])
    
    # ÉTAPE 7: Validation finale
    # Si le résultat est trop court ou juste des symboles, retourner vide
    if len(cleaned) < 3 or cleaned in ['<', '>', '-', '_', 'o', 'Q', 'D', 'G', 'vs', 'e']:
        return ""
    
    return cleaned

# --- FONCTIONS OPTIMISÉES (basées sur diagnostic OCR) ---

def preprocess_variant(img, variant: str):
    """
    Applique une variante de prétraitement OpenCV.
    Variantes supportées: orig, resize_2x, gray, binar_otsu, adaptive, sharpen, denoise, morph_open
    """
    if img is None:
        return None
        
    h, w = img.shape[:2]
    
    if variant == "orig":
        return img
    elif variant == "resize_2x":
        return cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_CUBIC)
    elif variant == "gray":
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif variant == "binar_otsu":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return th
    elif variant == "adaptive":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
        return th
    elif variant == "sharpen":
        kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
        return cv2.filter2D(img, -1, kernel)
    elif variant == "denoise":
        return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    elif variant == "morph_open":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        kernel = np.ones((3,3), np.uint8)
        opened = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
        return opened
    return img

def ocr_image_optimized(img, psm=6, lang="fra+eng"):
    """OCR optimisé avec Tesseract."""
    config = f"--oem 1 --psm {psm}"
    text = pytesseract.image_to_string(img, lang=lang, config=config)
    return text

def find_scores_optimized(text: str) -> List[str]:
    """Trouve les scores dans le texte."""
    score_regex = re.compile(r"(\b\d{1,2}\s*[-:]\s*\d{1,2}\b)")
    scores = score_regex.findall(text)
    return [s.replace(" ", "").replace(":", "-") for s in scores]

def analyze_image_auto(img_path: str, team_map: Dict[str, str], use_crop: bool = False) -> Dict:
    """
    Analyse automatique avec variantes optimisées.
    
    - Auto-crop la zone utile (30-70% de l'image) si use_crop=True
    - Teste les meilleures variantes (orig, resize_2x, sharpen)
    - Choisit la meilleure sortie basée sur le score de confiance
    
    Returns:
        dict avec variant, text, cleaned, scores, confidence
    """
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"Impossible de lire {img_path}")
    
    # Optionnel: Auto crop pour réduire le bruit
    if use_crop:
        h, w = img.shape[:2]
        y1, y2 = int(h*0.3), int(h*0.7)
        cropped = img[y1:y2, :]
    else:
        cropped = img
    
    best_result = None
    best_score = -1
    
    for v in GOOD_VARIANTS:
        try:
            proc = preprocess_variant(cropped.copy(), v)
            if proc is None:
                continue
                
            text = ocr_image_optimized(proc, psm=6)
            cleaned = text.lower()
            
            # Nettoyage basique
            for word in ["paris", "stats", "compos", "pari sur mesure"]:
                cleaned = cleaned.replace(word, " ")
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            
            scores = find_scores_optimized(text)
            team_score = 0
            
            # Chercher la ligne contenant les noms d'équipes
            # (ligne avec " - " ou " vs " et contenant des noms connus)
            lines = text.split('\n')
            best_line = ""
            best_line_score = 0
            
            for line in lines:
                if any(sep in line for sep in [" - ", " vs ", " – "]):
                    line_score = 0
                    line_lower = line.lower()
                    for t in team_map.keys():
                        if t.lower() in line_lower:
                            line_score += 10
                    if line_score > best_line_score:
                        best_line_score = line_score
                        best_line = line
            
            # Fuzzy matching avec team_map sur le texte complet
            for t in team_map.keys():
                if t.lower() in cleaned.lower():
                    team_score += 1
            
            # Score de confiance
            confidence = team_score * 10 + len(scores) * 5 + best_line_score
            
            if confidence > best_score:
                best_score = confidence
                best_result = {
                    "variant": v,
                    "text": text,
                    "cleaned": cleaned,
                    "scores": scores,
                    "confidence": confidence,
                    "best_match_line": best_line  # Ligne avec les équipes
                }
        except Exception as e:
            print(f"[OCR] Erreur variant {v}: {e}")
            continue
    
    if best_result is None:
        # Fallback sur l'image originale sans crop
        try:
            text = ocr_image_optimized(img, psm=6)
            best_result = {
                "variant": "fallback",
                "text": text,
                "cleaned": text.lower(),
                "scores": find_scores_optimized(text),
                "confidence": 0
            }
        except:
            best_result = {
                "variant": "error",
                "text": "",
                "cleaned": "",
                "scores": [],
                "confidence": -1
            }
    
    return best_result

def extract_match_info(image_path: str,
                       manual_home: Optional[str] = None,
                       manual_away: Optional[str] = None,
                       manual_league: Optional[str] = None) -> Dict:
    """
    Fonction principale d'extraction.
    
    MODE OPTIMISÉ (OCR_MODE=optimized):
    - Auto-crop zone utile
    - Teste variantes (orig, resize_2x, sharpen)
    - Choisit meilleur résultat
    
    MODE LEGACY (OCR_MODE=legacy):
    - Ancien comportement
    
    Returns dict:
    {
      'home_team': str|None,
      'away_team': str|None,
      'league': str,
      'home_goals': int|None,
      'away_goals': int|None,
      'raw_text': str,
      'timestamp': iso,
      'ocr_variant': str (si optimized)
    }
    """
    # MODE OPTIMISÉ
    if OCR_MODE == "optimized":
        try:
            # Charger le team_map pour l'analyse optimisée
            team_map = TEAM_LEAGUE_MAP
            
            # Analyse avec variantes optimisées
            ocr_result = analyze_image_auto(image_path, team_map)
            text = ocr_result["text"]
            ocr_variant = ocr_result["variant"]
            best_match_line = ocr_result.get("best_match_line", "")
            
            print(f"[OCR Optimized] Variant: {ocr_variant}, Confidence: {ocr_result['confidence']}")
            if best_match_line:
                print(f"[OCR Optimized] Best match line: {best_match_line[:60]}")
        except Exception as e:
            print(f"[OCR Optimized] Erreur, fallback sur legacy: {e}")
            text = ocr_read(image_path)
            ocr_variant = "legacy_fallback"
            best_match_line = ""
    else:
        # MODE LEGACY
        text = ocr_read(image_path)
        ocr_variant = "legacy"
        best_match_line = ""
    
    # Détection du score (optionnel)
    home_goals, away_goals = parse_score(text)
    
    # Utiliser les valeurs manuelles si fournies
    if manual_home and manual_away:
        home = manual_home.strip()
        away = manual_away.strip()
    else:
        # En mode optimisé, essayer d'abord la meilleure ligne détectée
        if OCR_MODE == "optimized" and best_match_line:
            t1, t2 = extract_teams_from_text(best_match_line)
            # Si ça n'a pas marché, essayer sur le texte complet
            if not t1 or not t2:
                t1, t2 = extract_teams_from_text(text)
        else:
            t1, t2 = extract_teams_from_text(text)
        home = t1
        away = t2
    
    # Détection de la ligue - ORDRE DE PRIORITÉ MODIFIÉ:
    # 1. Manuel (override)
    # 2. Détection dans le texte OCR (NOUVEAU - PRIORITÉ MAXIMALE)
    # 3. Mapping par équipe (fallback)
    # 4. Unknown
    
    if manual_league:
        league = manual_league
        print(f"[OCR Parser] Ligue manuelle : {league}")
    else:
        # NOUVEAU: Chercher d'abord dans le texte OCR
        league_from_text = detect_league_from_text(text)
        
        if league_from_text:
            league = league_from_text
            print(f"[OCR Parser] ✅ Ligue détectée dans le texte : {league}")
        else:
            # Fallback sur le mapping par équipe
            league = detect_league_from_teams(home, away)
            if league and league != "Unknown":
                print(f"[OCR Parser] ⚠️ Ligue déduite des équipes : {league}")
            else:
                print(f"[OCR Parser] ❌ Ligue non détectée : Unknown")
    
    result = {
        "home_team": home,
        "away_team": away,
        "league": league or "Unknown",
        "home_goals": home_goals,
        "away_goals": away_goals,
        "raw_text": text,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    # Ajouter variant si mode optimisé
    if OCR_MODE == "optimized":
        result["ocr_variant"] = ocr_variant
    
    return result

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

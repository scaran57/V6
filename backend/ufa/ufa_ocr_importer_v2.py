#!/usr/bin/env python3
"""
UFA OCR Importer v2.0
Détection automatique : Score + Équipes + Ligue

Nouvelles fonctionnalités :
- Détection automatique des noms d'équipes dans l'image
- Fuzzy matching pour noms mal lus par l'OCR
- Détection automatique de la ligue basée sur les équipes
- Table enrichie de 50+ équipes
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import json
import os
import datetime
from pathlib import Path
from fuzzywuzzy import process

# Configuration
UFA_FILE = "/app/data/real_scores.jsonl"
UPLOAD_FOLDER = "/app/uploads/fdj_captures"
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# 🔎 Regex de détection de score
SCORE_PATTERNS = [
    re.compile(r"\b([0-9])\s*[-:–—]\s*([0-9])\b"),
    re.compile(r"\b([0-9])\s+([0-9])\b"),
]

# ⚽ Dictionnaire Équipes → Ligues (Table enrichie v2.0)
TEAM_LEAGUE_MAP = {
    # 🇫🇷 Ligue 1
    "PSG": "Ligue1",
    "Paris Saint-Germain": "Ligue1",
    "Paris": "Ligue1",
    "Marseille": "Ligue1",
    "OM": "Ligue1",
    "Lyon": "Ligue1",
    "OL": "Ligue1",
    "Monaco": "Ligue1",
    "Lens": "Ligue1",
    "Lille": "Ligue1",
    "LOSC": "Ligue1",
    "Rennes": "Ligue1",
    "Nice": "Ligue1",
    "Toulouse": "Ligue1",
    "Reims": "Ligue1",
    "Strasbourg": "Ligue1",
    "Montpellier": "Ligue1",
    "Nantes": "Ligue1",
    "Brest": "Ligue1",
    "Lorient": "Ligue1",
    "Clermont": "Ligue1",
    "Metz": "Ligue1",
    "Saint-Etienne": "Ligue1",
    "Bordeaux": "Ligue1",

    # 🇪🇸 LaLiga
    "Real Madrid": "LaLiga",
    "Madrid": "LaLiga",
    "Barcelona": "LaLiga",
    "Barca": "LaLiga",
    "Atletico": "LaLiga",
    "Atletico Madrid": "LaLiga",
    "Sevilla": "LaLiga",
    "Valencia": "LaLiga",
    "Villarreal": "LaLiga",
    "Real Sociedad": "LaLiga",
    "Sociedad": "LaLiga",
    "Real Betis": "LaLiga",
    "Betis": "LaLiga",
    "Athletic": "LaLiga",
    "Bilbao": "LaLiga",
    "Celta": "LaLiga",
    "Getafe": "LaLiga",
    "Osasuna": "LaLiga",
    "Girona": "LaLiga",
    "Rayo": "LaLiga",

    # 🏴 Premier League
    "Manchester City": "PremierLeague",
    "Man City": "PremierLeague",
    "City": "PremierLeague",
    "Liverpool": "PremierLeague",
    "Arsenal": "PremierLeague",
    "Chelsea": "PremierLeague",
    "Manchester United": "PremierLeague",
    "Man United": "PremierLeague",
    "United": "PremierLeague",
    "Tottenham": "PremierLeague",
    "Spurs": "PremierLeague",
    "Newcastle": "PremierLeague",
    "Brighton": "PremierLeague",
    "Aston Villa": "PremierLeague",
    "Villa": "PremierLeague",
    "West Ham": "PremierLeague",
    "Everton": "PremierLeague",
    "Leicester": "PremierLeague",
    "Wolves": "PremierLeague",
    "Crystal Palace": "PremierLeague",
    "Brentford": "PremierLeague",

    # 🇮🇹 Serie A
    "Inter": "SerieA",
    "Inter Milan": "SerieA",
    "Milan": "SerieA",
    "AC Milan": "SerieA",
    "Juventus": "SerieA",
    "Juve": "SerieA",
    "Napoli": "SerieA",
    "Roma": "SerieA",
    "AS Roma": "SerieA",
    "Lazio": "SerieA",
    "Atalanta": "SerieA",
    "Fiorentina": "SerieA",
    "Torino": "SerieA",
    "Bologna": "SerieA",

    # 🇩🇪 Bundesliga
    "Bayern": "Bundesliga",
    "Bayern Munich": "Bundesliga",
    "Dortmund": "Bundesliga",
    "BVB": "Bundesliga",
    "Leipzig": "Bundesliga",
    "RB Leipzig": "Bundesliga",
    "Leverkusen": "Bundesliga",
    "Bayer": "Bundesliga",
    "Union Berlin": "Bundesliga",
    "Frankfurt": "Bundesliga",
    "Wolfsburg": "Bundesliga",
    "Gladbach": "Bundesliga",
    "Stuttgart": "Bundesliga",
    "Freiburg": "Bundesliga",

    # 🇳🇱 Eredivisie
    "Ajax": "Eredivisie",
    "Ajax Amsterdam": "Eredivisie",
    "PSV": "Eredivisie",
    "PSV Eindhoven": "Eredivisie",
    "Feyenoord": "Eredivisie",
    "AZ": "Eredivisie",
    "AZ Alkmaar": "Eredivisie",
    "Twente": "Eredivisie",
    "Utrecht": "Eredivisie",

    # 🇵🇹 Liga Portugal
    "Benfica": "PrimeiraLiga",
    "Porto": "PrimeiraLiga",
    "FC Porto": "PrimeiraLiga",
    "Sporting": "PrimeiraLiga",
    "Sporting CP": "PrimeiraLiga",
    "Braga": "PrimeiraLiga",

    # 🇹🇷 Süper Lig
    "Galatasaray": "SuperLig",
    "Fenerbahce": "SuperLig",
    "Besiktas": "SuperLig",
    "Trabzonspor": "SuperLig",

    # 🏴 Scottish Premiership
    "Celtic": "ScottishPremiership",
    "Rangers": "ScottishPremiership",

    # 🌍 Champions League
    "Champions League": "ChampionsLeague",
    "UCL": "ChampionsLeague",

    # 🌍 Europa League
    "Europa League": "EuropaLeague",
    "UEL": "EuropaLeague",
}

def preprocess_image(image_path):
    """
    Améliore la qualité de l'image pour l'OCR.
    """
    try:
        img = Image.open(image_path)
        img = img.convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
        return img
    except Exception as e:
        print(f"❌ Erreur pré-traitement: {e}")
        return None

def extract_text(image_path):
    """
    Retourne le texte brut lu par OCR.
    """
    try:
        img = preprocess_image(image_path)
        if img is None:
            return None
        text = pytesseract.image_to_string(img, lang="eng+fra", config='--psm 6')
        return text
    except Exception as e:
        print(f"❌ Erreur OCR: {e}")
        return None

def detect_score(text):
    """
    Détecte le score dans le texte OCR.
    
    Returns:
        tuple: (home_goals, away_goals) ou (None, None)
    """
    if not text:
        return None, None
    
    for pattern in SCORE_PATTERNS:
        match = pattern.search(text)
        if match:
            home_goals = int(match.group(1))
            away_goals = int(match.group(2))
            
            if 0 <= home_goals <= 9 and 0 <= away_goals <= 9:
                return home_goals, away_goals
    
    return None, None

def detect_teams(text):
    """
    Cherche deux équipes connues dans le texte OCR.
    Utilise d'abord une recherche exacte, puis fuzzy matching si nécessaire.
    
    Returns:
        list: Liste des équipes détectées (max 2)
    """
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    # Recherche exacte
    for team in TEAM_LEAGUE_MAP.keys():
        if team.lower() in text_lower:
            if team not in found:
                found.append(team)
    
    # Si moins de 2 équipes trouvées, essayer fuzzy matching
    if len(found) < 2:
        # Extraire les mots du texte
        words = text.split()
        
        # Fuzzy matching sur les mots de plus de 4 caractères
        for word in words:
            if len(word) > 4:
                matches = process.extract(word, TEAM_LEAGUE_MAP.keys(), limit=1)
                if matches and matches[0][1] > 80:  # Seuil de similarité à 80%
                    team = matches[0][0]
                    if team not in found:
                        found.append(team)
                        if len(found) >= 2:
                            break
    
    return found[:2]

def detect_league(teams):
    """
    Retourne la ligue la plus probable à partir des équipes détectées.
    
    Args:
        teams: Liste des équipes détectées
        
    Returns:
        str: Nom de la ligue ou "Unknown"
    """
    if not teams:
        return "Unknown"
    
    leagues = [TEAM_LEAGUE_MAP.get(t, "Unknown") for t in teams]
    leagues = [l for l in leagues if l != "Unknown"]
    
    if not leagues:
        return "Unknown"
    
    # Si une seule ligue identifiée
    if len(leagues) == 1:
        return leagues[0]
    
    # Si deux ligues identiques
    if len(leagues) == 2 and leagues[0] == leagues[1]:
        return leagues[0]
    
    # Si ligues différentes, prendre la première (probable)
    return leagues[0]

def add_to_ufa(home, away, league, home_goals, away_goals, source="ocr_v2"):
    """
    Ajoute le match au système UFA.
    """
    try:
        entry = {
            "league": league,
            "home_team": home,
            "away_team": away,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "source": source
        }
        
        os.makedirs(os.path.dirname(UFA_FILE), exist_ok=True)
        
        with open(UFA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        print(f"✅ {home} vs {away} ({home_goals}-{away_goals}) - {league}")
        return entry
        
    except Exception as e:
        print(f"❌ Erreur ajout UFA: {e}")
        return None

def process_image(image_path):
    """
    Traite une image complètement : Score + Équipes + Ligue.
    """
    print(f"📸 Traitement de {os.path.basename(image_path)}...")
    
    # Extraire le texte
    text = extract_text(image_path)
    if not text:
        return {
            "success": False,
            "error": "Impossible d'extraire le texte",
            "image": os.path.basename(image_path)
        }
    
    # Détecter le score
    home_goals, away_goals = detect_score(text)
    
    # Détecter les équipes
    teams = detect_teams(text)
    
    # Détecter la ligue
    league = detect_league(teams)
    
    # Validation
    if home_goals is None or away_goals is None:
        print(f"⚠️ Score non détecté dans {os.path.basename(image_path)}")
        return {
            "success": False,
            "error": "Score non détecté",
            "image": os.path.basename(image_path),
            "text": text[:200]
        }
    
    if len(teams) < 2:
        print(f"⚠️ Équipes non détectées ({len(teams)}/2) dans {os.path.basename(image_path)}")
        print(f"   Équipes trouvées: {teams}")
        # On ajoute quand même avec Unknown
        teams = teams + ["Unknown"] * (2 - len(teams))
    
    # Ajouter au système
    home = teams[0] if len(teams) > 0 else "Unknown"
    away = teams[1] if len(teams) > 1 else "Unknown"
    
    entry = add_to_ufa(home, away, league, home_goals, away_goals)
    
    return {
        "success": True,
        "image": os.path.basename(image_path),
        "score": f"{home_goals}-{away_goals}",
        "teams": teams,
        "league": league,
        "entry": entry
    }

def process_folder(folder):
    """
    Analyse toutes les images dans le dossier.
    """
    if not os.path.exists(folder):
        print(f"❌ Dossier introuvable: {folder}")
        return {
            "success": False,
            "error": "Dossier introuvable"
        }
    
    print("=" * 70)
    print(f"🔄 TRAITEMENT DU DOSSIER: {folder}")
    print("=" * 70)
    print()
    
    results = []
    total = 0
    success = 0
    teams_detected = 0
    leagues_detected = 0
    
    for fname in sorted(os.listdir(folder)):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        
        total += 1
        path = os.path.join(folder, fname)
        result = process_image(path)
        results.append(result)
        
        if result["success"]:
            success += 1
            if result.get("teams") and len(result["teams"]) == 2 and "Unknown" not in result["teams"]:
                teams_detected += 1
            if result.get("league") != "Unknown":
                leagues_detected += 1
    
    print()
    print("=" * 70)
    print(f"📊 RÉSUMÉ:")
    print(f"   Total d'images: {total}")
    print(f"   Scores détectés: {success}/{total} ({success/total*100:.1f}% si total > 0)")
    print(f"   Équipes détectées: {teams_detected}/{total} ({teams_detected/total*100:.1f}% si total > 0)")
    print(f"   Ligues détectées: {leagues_detected}/{total} ({leagues_detected/total*100:.1f}% si total > 0)")
    print(f"   Échecs: {total - success}")
    print("=" * 70)
    
    return {
        "success": True,
        "total": total,
        "scores_detected": success,
        "teams_detected": teams_detected,
        "leagues_detected": leagues_detected,
        "failed": total - success,
        "results": results
    }

if __name__ == "__main__":
    import sys
    
    print()
    print("╔" + "="*68 + "╗")
    print("║" + " "*18 + "UFA OCR IMPORTER v2.0" + " "*29 + "║")
    print("║" + " "*12 + "Score + Équipes + Ligue Automatique" + " "*21 + "║")
    print("╚" + "="*68 + "╝")
    print()
    
    folder = sys.argv[1] if len(sys.argv) > 1 else UPLOAD_FOLDER
    
    report = process_folder(folder)
    
    if report.get("success") and report.get("scores_detected") > 0:
        print()
        print("💡 Les scores ont été ajoutés au système UFA avec détection automatique.")
        print("   Training automatique à 3h00, ou manuel:")
        print("   python3 /app/backend/ufa/training/trainer.py")

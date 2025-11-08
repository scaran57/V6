#!/usr/bin/env python3
"""
UFA OCR Importer v3.0 - Auto Training Intégré
Détection automatique + Training immédiat

Workflow complet :
1. OCR automatique des captures
2. Détection score + équipes + ligue
3. Ajout à real_scores.jsonl
4. Training UFA immédiat (pas d'attente 3h00)
5. Mise à jour des priors instantanée

Avantages :
- Feedback immédiat sur l'apprentissage
- Pas d'attente jusqu'à 3h00
- Idéal pour itérations rapides
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import json
import os
import datetime
import subprocess
from pathlib import Path
from fuzzywuzzy import process

# Configuration des chemins
UFA_FILE = "/app/data/real_scores.jsonl"
TRAINING_SCRIPT = "/app/backend/ufa/training/trainer.py"
UPLOAD_FOLDER = "/app/uploads/fdj_captures"

# Configuration Tesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# Regex de détection de score
SCORE_PATTERNS = [
    re.compile(r"\b([0-9])\s*[-:–—]\s*([0-9])\b"),
    re.compile(r"\b([0-9])\s+([0-9])\b"),
]

# Dictionnaire Équipes → Ligues (version enrichie)
TEAM_LEAGUE_MAP = {
    # 🇫🇷 Ligue 1
    "PSG": "Ligue1", "Paris Saint-Germain": "Ligue1", "Paris": "Ligue1",
    "Marseille": "Ligue1", "OM": "Ligue1",
    "Lyon": "Ligue1", "OL": "Ligue1",
    "Monaco": "Ligue1", "Lens": "Ligue1", "Lille": "Ligue1",
    "Rennes": "Ligue1", "Nice": "Ligue1", "Toulouse": "Ligue1",
    "Reims": "Ligue1", "Strasbourg": "Ligue1", "Montpellier": "Ligue1",
    
    # 🇪🇸 LaLiga
    "Real Madrid": "LaLiga", "Madrid": "LaLiga",
    "Barcelona": "LaLiga", "Barca": "LaLiga",
    "Atletico": "LaLiga", "Atletico Madrid": "LaLiga",
    "Sevilla": "LaLiga", "Valencia": "LaLiga", "Villarreal": "LaLiga",
    "Real Sociedad": "LaLiga", "Real Betis": "LaLiga", "Athletic": "LaLiga",
    
    # 🏴 Premier League
    "Manchester City": "PremierLeague", "Man City": "PremierLeague", "City": "PremierLeague",
    "Liverpool": "PremierLeague", "Arsenal": "PremierLeague", "Chelsea": "PremierLeague",
    "Manchester United": "PremierLeague", "Man United": "PremierLeague", "United": "PremierLeague",
    "Tottenham": "PremierLeague", "Newcastle": "PremierLeague", "Brighton": "PremierLeague",
    "Aston Villa": "PremierLeague", "West Ham": "PremierLeague",
    
    # 🇮🇹 Serie A
    "Inter": "SerieA", "Inter Milan": "SerieA",
    "Milan": "SerieA", "AC Milan": "SerieA",
    "Juventus": "SerieA", "Juve": "SerieA",
    "Napoli": "SerieA", "Roma": "SerieA", "Lazio": "SerieA",
    "Atalanta": "SerieA", "Fiorentina": "SerieA",
    
    # 🇩🇪 Bundesliga
    "Bayern": "Bundesliga", "Bayern Munich": "Bundesliga",
    "Dortmund": "Bundesliga", "BVB": "Bundesliga",
    "Leipzig": "Bundesliga", "RB Leipzig": "Bundesliga",
    "Leverkusen": "Bundesliga", "Bayer": "Bundesliga",
    "Union Berlin": "Bundesliga", "Frankfurt": "Bundesliga",
    
    # 🇳🇱 Eredivisie
    "Ajax": "Eredivisie", "Ajax Amsterdam": "Eredivisie",
    "PSV": "Eredivisie", "PSV Eindhoven": "Eredivisie",
    "Feyenoord": "Eredivisie", "AZ": "Eredivisie",
    
    # 🇵🇹 Liga Portugal
    "Benfica": "PrimeiraLiga", "Porto": "PrimeiraLiga", "Sporting": "PrimeiraLiga",
    
    # 🇹🇷 Süper Lig
    "Galatasaray": "SuperLig", "Fenerbahce": "SuperLig", "Besiktas": "SuperLig",
}

def preprocess_image(image_path):
    """Améliore la qualité d'image pour une lecture OCR optimale."""
    try:
        img = Image.open(image_path).convert("L")
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        return img
    except Exception as e:
        print(f"❌ Erreur pré-traitement: {e}")
        return None

def extract_text(image_path):
    """Retourne le texte brut lu par OCR."""
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
    """Détecte le score dans le texte OCR."""
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
    """Cherche deux équipes connues dans le texte OCR avec fuzzy matching."""
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    # Recherche exacte
    for team in TEAM_LEAGUE_MAP.keys():
        if team.lower() in text_lower:
            if team not in found:
                found.append(team)
    
    # Fuzzy matching si nécessaire
    if len(found) < 2:
        words = text.split()
        for word in words:
            if len(word) > 4:
                matches = process.extract(word, TEAM_LEAGUE_MAP.keys(), limit=1)
                if matches and matches[0][1] > 80:
                    team = matches[0][0]
                    if team not in found:
                        found.append(team)
                        if len(found) >= 2:
                            break
    
    return found[:2]

def detect_league(teams):
    """Retourne la ligue la plus probable à partir des équipes détectées."""
    if not teams:
        return "Unknown"
    
    leagues = [TEAM_LEAGUE_MAP.get(t, "Unknown") for t in teams]
    leagues = [l for l in leagues if l != "Unknown"]
    
    if not leagues:
        return "Unknown"
    
    if len(leagues) == 1:
        return leagues[0]
    
    if len(leagues) == 2 and leagues[0] == leagues[1]:
        return leagues[0]
    
    return leagues[0]

def add_to_ufa(home, away, league, home_goals, away_goals):
    """Ajoute le match au système UFA."""
    try:
        entry = {
            "league": league,
            "home_team": home,
            "away_team": away,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "source": "ocr_autotrain_v3"
        }
        
        os.makedirs(os.path.dirname(UFA_FILE), exist_ok=True)
        
        with open(UFA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        print(f"✅ Match ajouté : {home} vs {away} ({home_goals}-{away_goals}) - {league}")
        return True
    except Exception as e:
        print(f"❌ Erreur ajout UFA: {e}")
        return False

def train_now():
    """
    Déclenche immédiatement le moteur d'apprentissage UFA.
    Exécute le script de training et retourne les résultats.
    """
    print()
    print("=" * 70)
    print("🧠 DÉCLENCHEMENT DU TRAINING UFA IMMÉDIAT")
    print("=" * 70)
    
    try:
        # Vérifier que le script de training existe
        if not os.path.exists(TRAINING_SCRIPT):
            print(f"❌ Script de training introuvable: {TRAINING_SCRIPT}")
            return False
        
        # Lancer le training
        result = subprocess.run(
            ["python3", TRAINING_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60  # Timeout de 60 secondes
        )
        
        if result.returncode == 0:
            print("✅ Training terminé avec succès")
            print()
            print("📊 Sortie du training:")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return True
        else:
            print("⚠️ Erreur pendant le training")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ Training timeout (>60s)")
        return False
    except Exception as e:
        print(f"❌ Erreur lors du lancement du training: {e}")
        return False

def process_image(image_path):
    """Traite une image complètement."""
    print(f"📸 Traitement de {os.path.basename(image_path)}...")
    
    text = extract_text(image_path)
    if not text:
        return {"success": False, "error": "Extraction texte échouée"}
    
    home_goals, away_goals = detect_score(text)
    teams = detect_teams(text)
    league = detect_league(teams)
    
    if home_goals is None or away_goals is None:
        print(f"⚠️ Score non détecté dans {os.path.basename(image_path)}")
        return {"success": False, "error": "Score non détecté"}
    
    if len(teams) < 2:
        print(f"⚠️ Équipes partiellement détectées ({len(teams)}/2)")
        teams = teams + ["Unknown"] * (2 - len(teams))
    
    home = teams[0] if len(teams) > 0 else "Unknown"
    away = teams[1] if len(teams) > 1 else "Unknown"
    
    success = add_to_ufa(home, away, league, home_goals, away_goals)
    
    return {
        "success": success,
        "score": f"{home_goals}-{away_goals}",
        "teams": teams,
        "league": league
    }

def process_folder(folder, auto_train=True):
    """
    Analyse toutes les images FDJ et lance l'apprentissage immédiat.
    
    Args:
        folder: Chemin du dossier contenant les images
        auto_train: Si True, lance le training après traitement
    """
    if not os.path.exists(folder):
        print(f"❌ Dossier introuvable: {folder}")
        return {"success": False, "error": "Dossier introuvable"}
    
    print("=" * 70)
    print("🔄 TRAITEMENT AUTO-TRAIN (v3.0)")
    print("=" * 70)
    print()
    
    results = []
    total = 0
    success = 0
    
    for fname in sorted(os.listdir(folder)):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        
        total += 1
        path = os.path.join(folder, fname)
        result = process_image(path)
        results.append(result)
        
        if result["success"]:
            success += 1
    
    print()
    print("=" * 70)
    print(f"📊 RÉSUMÉ TRAITEMENT:")
    print(f"   Total d'images: {total}")
    print(f"   Scores ajoutés: {success}/{total}")
    print("=" * 70)
    
    # Auto-training si activé et si des scores ont été ajoutés
    training_success = False
    if auto_train and success > 0:
        training_success = train_now()
    elif success == 0:
        print()
        print("ℹ️  Aucun score ajouté, training non nécessaire")
    
    return {
        "success": True,
        "total": total,
        "added": success,
        "training_executed": training_success,
        "results": results
    }

if __name__ == "__main__":
    import sys
    
    print()
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "UFA OCR IMPORTER v3.0" + " "*32 + "║")
    print("║" + " "*13 + "Auto-Training Instantané" + " "*30 + "║")
    print("╚" + "="*68 + "╝")
    print()
    
    folder = sys.argv[1] if len(sys.argv) > 1 else UPLOAD_FOLDER
    auto_train = True if len(sys.argv) <= 2 else sys.argv[2].lower() != "false"
    
    report = process_folder(folder, auto_train=auto_train)
    
    if report.get("success"):
        print()
        if report.get("training_executed"):
            print("✅ Cycle complet terminé : OCR → Ajout → Training")
            print("📊 Les priors UFA ont été mis à jour instantanément")
        else:
            print("✅ Traitement terminé (training non exécuté)")
        print()
        print("💡 Pour voir l'état actuel:")
        print("   cat /app/backend/ufa/training/state.json")

#!/usr/bin/env python3
"""
UFA OCR Importer v1.0
Lecture automatique des scores réels à partir de captures FDJ

Fonctionnalités :
- OCR optimisé pour la détection de scores
- Pré-traitement d'image pour améliorer la précision
- Import automatique dans le système UFA
- Traitement par lot de dossiers
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import json
import os
import datetime
from pathlib import Path

# Configuration
UFA_FILE = "/app/data/real_scores.jsonl"
UPLOAD_FOLDER = "/app/uploads/fdj_captures"
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# 🔎 Regex de détection de score (flexible)
SCORE_PATTERNS = [
    re.compile(r"\b([0-9])\s*[-:–—]\s*([0-9])\b"),  # Format standard : 3-1, 3:1
    re.compile(r"\b([0-9])\s+([0-9])\b"),            # Format avec espace : 3 1
]

def preprocess_image(image_path):
    """
    Améliore la qualité de l'image pour l'OCR.
    
    Args:
        image_path: Chemin vers l'image
        
    Returns:
        PIL.Image: Image pré-traitée
    """
    try:
        img = Image.open(image_path)
        
        # Convertir en niveaux de gris
        img = img.convert("L")
        
        # Améliorer le contraste
        img = ImageEnhance.Contrast(img).enhance(2.0)
        
        # Améliorer la netteté
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        
        # Appliquer un filtre de netteté
        img = img.filter(ImageFilter.SHARPEN)
        
        return img
    except Exception as e:
        print(f"❌ Erreur lors du pré-traitement de {image_path}: {e}")
        return None

def extract_score_from_image(image_path):
    """
    Analyse une capture et extrait un score.
    
    Args:
        image_path: Chemin vers l'image
        
    Returns:
        tuple: (home_goals, away_goals, texte_complet)
    """
    try:
        # Pré-traiter l'image
        img = preprocess_image(image_path)
        if img is None:
            return None, None, None
        
        # Extraire le texte avec OCR
        text = pytesseract.image_to_string(img, lang="eng+fra", config='--psm 6')
        
        # Chercher un score dans le texte
        for pattern in SCORE_PATTERNS:
            match = pattern.search(text)
            if match:
                home_goals = int(match.group(1))
                away_goals = int(match.group(2))
                
                # Valider que les scores sont raisonnables (0-9)
                if 0 <= home_goals <= 9 and 0 <= away_goals <= 9:
                    return home_goals, away_goals, text
        
        return None, None, text
        
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction du score de {image_path}: {e}")
        return None, None, None

def add_to_ufa(home, away, league, home_goals, away_goals, source="ocr_importer"):
    """
    Ajoute le match au système UFA.
    
    Args:
        home: Équipe domicile
        away: Équipe extérieure
        league: Ligue
        home_goals: Buts domicile
        away_goals: Buts extérieur
        source: Source de l'import
        
    Returns:
        dict: Entrée créée
    """
    try:
        entry = {
            "league": league or "Unknown",
            "home_team": home or "Unknown",
            "away_team": away or "Unknown",
            "home_goals": home_goals,
            "away_goals": away_goals,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "source": source
        }
        
        # Créer le dossier si nécessaire
        os.makedirs(os.path.dirname(UFA_FILE), exist_ok=True)
        
        with open(UFA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        print(f"✅ Match ajouté : {home} vs {away} ({home_goals}-{away_goals})")
        return entry
        
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout au fichier UFA: {e}")
        return None

def process_image(image_path, home="Unknown", away="Unknown", league="Unknown"):
    """
    Traite une seule image.
    
    Args:
        image_path: Chemin vers l'image
        home: Nom de l'équipe domicile (optionnel)
        away: Nom de l'équipe extérieure (optionnel)
        league: Nom de la ligue (optionnel)
        
    Returns:
        dict: Résultat du traitement
    """
    print(f"📸 Traitement de {os.path.basename(image_path)}...")
    
    home_goals, away_goals, text = extract_score_from_image(image_path)
    
    if home_goals is not None and away_goals is not None:
        entry = add_to_ufa(home, away, league, home_goals, away_goals)
        return {
            "success": True,
            "image": os.path.basename(image_path),
            "score": f"{home_goals}-{away_goals}",
            "entry": entry
        }
    else:
        print(f"❌ Aucun score détecté dans {os.path.basename(image_path)}")
        if text:
            print(f"📝 Texte lu (extrait): {text[:200]}")
        return {
            "success": False,
            "image": os.path.basename(image_path),
            "error": "Aucun score détecté",
            "text": text[:200] if text else None
        }

def process_folder(folder, home="Unknown", away="Unknown", league="Unknown"):
    """
    Analyse tout un dossier de captures.
    
    Args:
        folder: Chemin vers le dossier
        home: Nom de l'équipe domicile par défaut
        away: Nom de l'équipe extérieure par défaut
        league: Nom de la ligue par défaut
        
    Returns:
        dict: Rapport de traitement
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
    
    # Parcourir tous les fichiers
    for fname in sorted(os.listdir(folder)):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        
        total += 1
        path = os.path.join(folder, fname)
        result = process_image(path, home, away, league)
        results.append(result)
        
        if result["success"]:
            success += 1
    
    print()
    print("=" * 70)
    print(f"📊 RÉSUMÉ:")
    print(f"   Total d'images traitées: {total}")
    print(f"   Scores détectés: {success}/{total} ({success/total*100:.1f}% si total > 0)")
    print(f"   Échecs: {total - success}")
    print("=" * 70)
    
    return {
        "success": True,
        "total": total,
        "detected": success,
        "failed": total - success,
        "results": results
    }

def create_upload_folder():
    """Crée le dossier d'upload si nécessaire"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print(f"✅ Dossier d'upload créé/vérifié: {UPLOAD_FOLDER}")

if __name__ == "__main__":
    import sys
    
    # Créer le dossier d'upload
    create_upload_folder()
    
    # Déterminer le dossier à traiter
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = UPLOAD_FOLDER
    
    print()
    print("╔" + "="*68 + "╗")
    print("║" + " "*20 + "UFA OCR IMPORTER v1.0" + " "*27 + "║")
    print("╚" + "="*68 + "╝")
    print()
    
    # Traiter le dossier
    report = process_folder(folder)
    
    if report.get("success") and report.get("detected") > 0:
        print()
        print("💡 Les scores ont été ajoutés au système UFA.")
        print("   Ils seront pris en compte lors du prochain training (3h00).")
        print()
        print("   Pour forcer le training maintenant:")
        print("   python3 /app/backend/ufa/training/trainer.py")

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import logging
import numpy as np

logger = logging.getLogger(__name__)

def extract_odds(image_path: str):
    """
    Extrait les cotes et scores depuis une image de bookmaker.
    Supporte le français, anglais et espagnol.
    Version améliorée pour gérer différents formats.
    """
    try:
        # Améliorer la qualité de l'image pour l'OCR
        img = Image.open(image_path)
        
        # Tenter différentes configurations OCR
        configs = [
            "--psm 6",  # Assume a single uniform block of text
            "--psm 4",  # Assume a single column of text of variable sizes
            "--psm 11", # Sparse text. Find as much text as possible
        ]
        
        best_text = ""
        best_score_count = 0
        
        for config in configs:
            try:
                text = pytesseract.image_to_string(img, lang="eng+fra+spa", config=config)
                # Compter combien de scores potentiels sont détectés
                score_count = len(re.findall(r"\d+[-:]\d+", text))
                if score_count > best_score_count:
                    best_score_count = score_count
                    best_text = text
            except:
                continue
        
        text = best_text if best_text else pytesseract.image_to_string(img, lang="eng+fra+spa")
        
        logger.info(f"=== TEXTE OCR COMPLET ===\n{text}\n=== FIN TEXTE OCR ===")
        
        scores = []
        
        # Pattern 1: Score suivi de cote avec espace(s) - ex: "2-1  3.50" ou "2:1    3.50"
        pattern1 = re.compile(r"(\d+[-:]\d+)\s+([0-9]+[.,][0-9]+)")
        for match in pattern1.finditer(text):
            score = match.group(1).replace(":", "-")
            odds_str = match.group(2).replace(",", ".")
            try:
                odds = float(odds_str)
                if 1.01 <= odds <= 1000:  # Cotes raisonnables
                    scores.append({"score": score, "odds": odds})
                    logger.info(f"✓ Pattern1 - Score trouvé: {score} avec cote {odds}")
            except ValueError:
                continue
        
        # Pattern 2: Score avec cote sans espace - ex: "2-13.50"
        pattern2 = re.compile(r"(\d+[-:]\d+)([0-9]+[.,][0-9]+)")
        for match in pattern2.finditer(text):
            score = match.group(1).replace(":", "-")
            odds_str = match.group(2).replace(",", ".")
            try:
                odds = float(odds_str)
                if 1.01 <= odds <= 1000:
                    # Vérifier que ce score n'existe pas déjà
                    if not any(s["score"] == score for s in scores):
                        scores.append({"score": score, "odds": odds})
                        logger.info(f"✓ Pattern2 - Score trouvé: {score} avec cote {odds}")
            except ValueError:
                continue
        
        # Pattern 3: Ligne avec score et chiffres séparés - ex: ligne "2 - 1" suivie de "3.50"
        lines = text.split('\n')
        for i, line in enumerate(lines):
            # Chercher "X - Y" ou "X-Y"
            score_match = re.search(r"(\d+)\s*[-:]\s*(\d+)", line)
            if score_match:
                score = f"{score_match.group(1)}-{score_match.group(2)}"
                # Chercher la cote dans la même ligne ou les suivantes
                for j in range(i, min(i+3, len(lines))):
                    odds_match = re.search(r"([0-9]+[.,][0-9]+)", lines[j])
                    if odds_match:
                        odds_str = odds_match.group(1).replace(",", ".")
                        try:
                            odds = float(odds_str)
                            if 1.01 <= odds <= 1000:
                                if not any(s["score"] == score for s in scores):
                                    scores.append({"score": score, "odds": odds})
                                    logger.info(f"✓ Pattern3 - Score trouvé: {score} avec cote {odds}")
                                break
                        except ValueError:
                            continue
        
        # Chercher "Autre" ou "Other" avec une cote
        for keyword in ["autre", "other", "any", "aut"]:
            other_regex = re.search(rf"{keyword}\s*([0-9]+[.,][0-9]+)", text, re.IGNORECASE)
            if other_regex:
                try:
                    odds_str = other_regex.group(1).replace(",", ".")
                    odds = float(odds_str)
                    if not any(s["score"] == "Autre" for s in scores):
                        scores.append({"score": "Autre", "odds": odds})
                        logger.info(f"✓ Option 'Autre' trouvée avec cote {odds}")
                        break
                except ValueError:
                    pass
        
        logger.info(f"📊 TOTAL: {len(scores)} scores extraits avec succès")
        
        return scores
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'extraction OCR: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []
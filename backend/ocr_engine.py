import pytesseract
from PIL import Image
import re
import logging

logger = logging.getLogger(__name__)

def extract_odds(image_path: str):
    """
    Extrait les cotes et scores depuis une image de bookmaker.
    Supporte le français, anglais et espagnol.
    """
    try:
        # OCR multi-langue (français, anglais, espagnol)
        text = pytesseract.image_to_string(Image.open(image_path), lang="eng+fra+spa")
        logger.info(f"Texte extrait de l'image: {text[:200]}...")  # Log les 200 premiers caractères
        
        # Regex pour capturer score (ex: "2-1" ou "2:1") et cote (ex: "3.50" ou "3")
        regex = re.compile(r"(\d+[-:]\d+)\s+([0-9]+\.[0-9]+|[0-9]+)")
        scores = []
        
        for match in regex.finditer(text):
            score = match.group(1).replace(":", "-")
            try:
                odds = float(match.group(2))
                if odds > 0:
                    scores.append({"score": score, "odds": odds})
                    logger.info(f"Score trouvé: {score} avec cote {odds}")
            except ValueError:
                continue
        
        # Chercher aussi "Autre" ou "Other" avec une cote
        other_regex = re.search(r"(autre|other)\s*([0-9]+\.[0-9]+|[0-9]+)", text, re.IGNORECASE)
        if other_regex:
            try:
                odds = float(other_regex.group(2))
                scores.append({"score": "Autre", "odds": odds})
                logger.info(f"Option 'Autre' trouvée avec cote {odds}")
            except ValueError:
                pass
        
        logger.info(f"Total de {len(scores)} scores extraits")
        return scores
        
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction OCR: {str(e)}")
        return []
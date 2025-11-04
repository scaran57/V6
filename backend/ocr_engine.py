import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
import re
import logging

logger = logging.getLogger(__name__)

def preprocess_for_green_buttons(image_path: str):
    """
    Preprocessing avancé pour détecter texte blanc sur fond vert (boutons bookmaker).
    Retourne plusieurs versions de l'image optimisées pour l'OCR.
    """
    # Lire l'image avec OpenCV
    img = cv2.imread(image_path)
    processed_images = []
    
    # 1. Image originale convertie en niveaux de gris
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    processed_images.append(("original_gray", gray))
    
    # 2. Isolation du canal vert (les boutons verts deviennent clairs)
    b, g, r = cv2.split(img)
    processed_images.append(("green_channel", g))
    
    # 3. Inversion pour convertir blanc sur vert en noir sur blanc
    inverted = cv2.bitwise_not(gray)
    processed_images.append(("inverted", inverted))
    
    # 4. Seuillage adaptatif pour isoler le texte
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                    cv2.THRESH_BINARY, 11, 2)
    processed_images.append(("adaptive_thresh", thresh))
    
    # 5. Seuillage Otsu
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    processed_images.append(("otsu", otsu))
    
    # 6. Isolation spécifique des zones vertes (boutons)
    # Convertir en HSV pour détecter le vert
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Plage de vert (ajuster selon les couleurs exactes)
    lower_green = np.array([35, 40, 40])
    upper_green = np.array([85, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    
    # Inverser le masque pour avoir le texte en noir
    green_isolated = cv2.bitwise_not(mask_green)
    processed_images.append(("green_isolated", green_isolated))
    
    # 7. Amélioration du contraste sur l'image originale
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    enhanced = cv2.merge((cl,a,b))
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    processed_images.append(("enhanced_contrast", enhanced_gray))
    
    # 8. Morphologie pour nettoyer
    kernel = np.ones((2,2), np.uint8)
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    processed_images.append(("morphology", morph))
    
    return processed_images

def extract_odds(image_path: str):
    """
    Extrait les cotes et scores depuis une image de bookmaker.
    Supporte le français, anglais et espagnol.
    Version améliorée pour gérer différents formats et fonds colorés.
    """
    try:
        # Charger l'image
        img = Image.open(image_path)
        
        # Preprocessing pour améliorer la détection OCR (surtout texte blanc sur fond vert)
        # Convertir en niveaux de gris
        img_gray = img.convert('L')
        
        # Augmenter le contraste
        enhancer = ImageEnhance.Contrast(img_gray)
        img_contrast = enhancer.enhance(2.0)
        
        # Augmenter la netteté
        img_sharp = img_contrast.filter(ImageFilter.SHARPEN)
        
        # Tenter différentes configurations OCR
        configs = [
            "--psm 6",  # Assume a single uniform block of text
            "--psm 4",  # Assume a single column of text of variable sizes
            "--psm 11", # Sparse text. Find as much text as possible
        ]
        
        all_texts = []
        
        # Essayer avec l'image originale
        for config in configs:
            try:
                text = pytesseract.image_to_string(img, lang="eng+fra+spa", config=config)
                all_texts.append(text)
            except:
                continue
        
        # Essayer avec l'image preprocessed
        for config in configs:
            try:
                text = pytesseract.image_to_string(img_sharp, lang="eng+fra+spa", config=config)
                all_texts.append(text)
            except:
                continue
        
        # Combiner tous les textes extraits
        combined_text = "\n".join(all_texts)
        
        logger.info(f"=== TEXTE OCR COMPLET ===\n{combined_text[:1000]}\n=== FIN TEXTE OCR (tronqué) ===")
        
        scores = []
        seen_scores = set()
        
        # Traiter chaque texte extrait
        for text in all_texts:
            # Pattern 1: Score suivi de cote avec espace(s) - ex: "2-1  3.50" ou "2:1    3.50"
            pattern1 = re.compile(r"(\d+[-:]\d+)\s+([0-9]+[.,][0-9]+)")
            for match in pattern1.finditer(text):
                score = match.group(1).replace(":", "-")
                odds_str = match.group(2).replace(",", ".")
                try:
                    odds = float(odds_str)
                    if 1.01 <= odds <= 1000:  # Cotes raisonnables
                        score_key = f"{score}_{odds}"
                        if score_key not in seen_scores:
                            scores.append({"score": score, "odds": odds})
                            seen_scores.add(score_key)
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
                        score_key = f"{score}_{odds}"
                        if score_key not in seen_scores:
                            scores.append({"score": score, "odds": odds})
                            seen_scores.add(score_key)
                            logger.info(f"✓ Pattern2 - Score trouvé: {score} avec cote {odds}")
                except ValueError:
                    continue
            
            # Pattern 3: Chercher scores et cotes séparément dans les lignes
            lines = text.split('\n')
            
            # D'abord extraire toutes les cotes potentielles
            all_odds = []
            for line in lines:
                odds_matches = re.findall(r"([0-9]+[.,][0-9]+)", line)
                for odds_str in odds_matches:
                    try:
                        odds = float(odds_str.replace(",", "."))
                        if 1.01 <= odds <= 1000:
                            all_odds.append(odds)
                    except:
                        continue
            
            # Ensuite extraire tous les scores
            all_scores_found = []
            for line in lines:
                score_matches = re.findall(r"(\d+[-:]\d+)", line)
                for score_match in score_matches:
                    score = score_match.replace(":", "-")
                    all_scores_found.append(score)
            
            # Associer scores et cotes (si nombre similaire)
            logger.info(f"Scores trouvés: {len(all_scores_found)}, Cotes trouvées: {len(all_odds)}")
            
            if len(all_scores_found) > 0 and len(all_odds) > 0:
                # Essayer d'associer dans l'ordre
                for i, score in enumerate(all_scores_found):
                    if i < len(all_odds):
                        odds = all_odds[i]
                        score_key = f"{score}_{odds}"
                        if score_key not in seen_scores:
                            scores.append({"score": score, "odds": odds})
                            seen_scores.add(score_key)
                            logger.info(f"✓ Pattern3 - Score trouvé: {score} avec cote {odds}")
        
        # Chercher "Autre" ou "Other" avec une cote
        for keyword in ["autre", "other", "any", "aut"]:
            other_regex = re.search(rf"{keyword}\s*([0-9]+[.,][0-9]+)", combined_text, re.IGNORECASE)
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
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
    Version avancée avec preprocessing pour fonds colorés (boutons verts, etc.).
    """
    try:
        logger.info("🔍 Début de l'extraction avec preprocessing avancé...")
        
        # Obtenir toutes les versions preprocessed de l'image
        processed_images = preprocess_for_green_buttons(image_path)
        
        # Charger aussi l'image PIL originale
        pil_img = Image.open(image_path)
        
        # Configurations OCR à tester
        configs = [
            "--psm 6",   # Single uniform block
            "--psm 4",   # Single column
            "--psm 11",  # Sparse text
            "--psm 3",   # Fully automatic
        ]
        
        all_texts = []
        
        # OCR sur l'image PIL originale
        logger.info("📸 OCR sur image originale...")
        for config in configs:
            try:
                text = pytesseract.image_to_string(pil_img, lang="eng+fra+spa", config=config)
                if text.strip():
                    all_texts.append(("pil_original", text))
            except Exception as e:
                logger.warning(f"Erreur OCR PIL: {e}")
        
        # OCR sur chaque version preprocessed
        for img_name, cv_img in processed_images:
            logger.info(f"📸 OCR sur version: {img_name}")
            for config in configs[:2]:  # Limiter à 2 configs par version pour performance
                try:
                    # Convertir numpy array en PIL Image
                    pil_from_cv = Image.fromarray(cv_img)
                    text = pytesseract.image_to_string(pil_from_cv, lang="eng+fra+spa", config=config)
                    if text.strip():
                        all_texts.append((img_name, text))
                except Exception as e:
                    logger.warning(f"Erreur OCR {img_name}: {e}")
        
        logger.info(f"✅ {len(all_texts)} textes extraits au total")
        
        # Afficher un échantillon du texte le plus complet
        if all_texts:
            longest_text = max(all_texts, key=lambda x: len(x[1]))
            logger.info(f"=== MEILLEUR TEXTE OCR ({longest_text[0]}) ===\n{longest_text[1][:500]}\n=== FIN ===")
        
        # Extraire les scores et cotes
        scores = []
        seen_scores = set()
        
        for source_name, text in all_texts:
            # Pattern 1: Score directement suivi de cote - ex: "1-0 15.20" ou "1-015.20"
            pattern1 = re.compile(r"(\d+[-:]\d+)\s*([0-9]+[.,][0-9]+)")
            for match in pattern1.finditer(text):
                score = match.group(1).replace(":", "-")
                # Nettoyer les scores mal reconnus
                # Ex: "3-07" → "3-0", "2-08" → "2-0", etc.
                parts = score.split('-')
                if len(parts) == 2:
                    try:
                        # Convertir en int puis back en string pour enlever les zéros initiaux
                        score = f"{int(parts[0])}-{int(parts[1])}"
                    except:
                        pass
                if re.match(r'^\d{1,2}-\d{1,2}$', score):  # Vérifier format valide
                    odds_str = match.group(2).replace(",", ".")
                    try:
                        odds = float(odds_str)
                        if 1.01 <= odds <= 1000:
                            score_key = f"{score}_{odds}"
                            if score_key not in seen_scores:
                                scores.append({"score": score, "odds": odds})
                                seen_scores.add(score_key)
                                logger.info(f"✓ [{source_name}] Pattern1 - {score} @ {odds}")
                    except ValueError:
                        continue
            
            # Pattern 2: Extraire tous les scores, puis toutes les cotes, et les associer
            all_scores_in_text = []
            all_odds_in_text = []
            
            # Extraire tous les scores possibles
            score_matches = re.findall(r"(\d+[-:]\d+)", text)
            for s in score_matches:
                score = s.replace(":", "-")
                # Nettoyer les scores mal reconnus
                score = re.sub(r'-0+(\d)$', r'-\1', score)
                if re.match(r'^\d{1,2}-\d{1,2}$', score):
                    all_scores_in_text.append(score)
            
            # Extraire toutes les cotes possibles
            odds_matches = re.findall(r"([0-9]+[.,][0-9]+)", text)
            for o in odds_matches:
                try:
                    odds_val = float(o.replace(",", "."))
                    if 1.01 <= odds_val <= 1000:
                        all_odds_in_text.append(odds_val)
                except:
                    continue
            
            # Associer scores et cotes dans l'ordre
            min_len = min(len(all_scores_in_text), len(all_odds_in_text))
            for i in range(min_len):
                score = all_scores_in_text[i]
                odds = all_odds_in_text[i]
                score_key = f"{score}_{odds}"
                if score_key not in seen_scores:
                    scores.append({"score": score, "odds": odds})
                    seen_scores.add(score_key)
                    logger.info(f"✓ [{source_name}] Pattern2 - {score} @ {odds}")
        
        # Chercher "Autre" avec une cote
        combined_text = " ".join([t[1] for t in all_texts])
        for keyword in ["autre", "other", "any"]:
            other_match = re.search(rf"{keyword}\s*([0-9]+[.,][0-9]+)", combined_text, re.IGNORECASE)
            if other_match:
                try:
                    odds = float(other_match.group(1).replace(",", "."))
                    if not any(s["score"] == "Autre" for s in scores):
                        scores.append({"score": "Autre", "odds": odds})
                        logger.info(f"✓ Option 'Autre' @ {odds}")
                        break
                except:
                    pass
        
        # Dédupliquer les scores identiques (garder celui avec la cote la plus courante)
        final_scores = []
        score_odds_map = {}
        for item in scores:
            score = item["score"]
            odds = item["odds"]
            if score not in score_odds_map:
                score_odds_map[score] = []
            score_odds_map[score].append(odds)
        
        # Pour chaque score, prendre la cote la plus fréquente
        for score, odds_list in score_odds_map.items():
            # Prendre la cote médiane si plusieurs valeurs
            odds_list.sort()
            median_odds = odds_list[len(odds_list) // 2]
            final_scores.append({"score": score, "odds": median_odds})
        
        logger.info(f"📊 TOTAL FINAL: {len(final_scores)} scores uniques extraits")
        
        return final_scores
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'extraction OCR: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []
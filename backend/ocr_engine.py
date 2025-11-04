import cv2
import pytesseract
import numpy as np
from PIL import Image
import re
import io
import logging

logger = logging.getLogger(__name__)

# Configuration Tesseract
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# Langues disponibles (multilingue)
LANGS = "eng+fra+spa"

def preprocess_image(image_path: str) -> list:
    """
    Transforme une image en plusieurs variantes prétraitées pour maximiser la lecture OCR.
    Amélioration spéciale: détection texte BLANC sur VERT (boutons Unibet/Winamax)
    """
    # Charger l'image
    image = Image.open(image_path).convert("RGB")
    img = np.array(image)

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)

    # Détection automatique du thème
    mean_brightness = np.mean(gray)
    is_dark_theme = mean_brightness < 100
    
    logger.info(f"🎨 Thème détecté: {'SOMBRE' if is_dark_theme else 'CLAIR'} (luminosité: {mean_brightness:.1f})")

    versions = []

    # 1. Original
    versions.append(("original", gray))

    # 2. Inversée (utile pour thème sombre)
    versions.append(("inverted", cv2.bitwise_not(gray)))

    # 3. Adaptative Threshold (améliore distinction 0/O, 1/I)
    thr1 = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, 11, 2)
    versions.append(("adaptive_thresh", thr1))

    # 4. CLAHE (améliore contraste)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl1 = clahe.apply(gray)
    versions.append(("clahe", cl1))

    # 5. Contraste + réduction bruit
    denoise = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
    versions.append(("denoise", denoise))

    # 6. Combinaison blur + threshold (Otsu)
    _, thr2 = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(("otsu", thr2))
    
    # 7. NOUVEAU: Isolation du canal ROUGE (texte blanc sur vert apparaît bien)
    # Le vert a peu de rouge, donc texte blanc ressort
    if len(img.shape) == 3:
        b, g, r = cv2.split(img)
        # Inverser le rouge pour que texte blanc devienne noir
        red_inverted = cv2.bitwise_not(r)
        versions.append(("red_channel_inv", red_inverted))
        
        # 8. NOUVEAU: Seuillage sur canal vert inversé
        green_inv = cv2.bitwise_not(g)
        _, green_thresh = cv2.threshold(green_inv, 150, 255, cv2.THRESH_BINARY)
        versions.append(("green_thresh", green_thresh))
        
        # 9. NOUVEAU: Masque spécifique pour boutons verts
        # Détecter zones vertes (boutons) et extraire le texte
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        # Plage de vert plus large
        lower_green = np.array([25, 40, 40])
        upper_green = np.array([95, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        # Inverser: zones vertes deviennent blanches, texte reste
        mask_inv = cv2.bitwise_not(mask)
        # Appliquer sur image grise
        green_buttons = cv2.bitwise_and(gray, gray, mask=mask_inv)
        versions.append(("green_buttons", green_buttons))

    return versions


def clean_score(score_str: str) -> str:
    """
    Nettoie un score individuel en corrigeant les erreurs OCR courantes.
    """
    # Normalisation des caractères (erreurs fréquentes)
    score_str = score_str.replace("O", "0").replace("I", "1").replace("l", "1")
    score_str = score_str.replace(":", "-").replace("_", "-")
    
    # Extraire les chiffres
    parts = score_str.split('-')
    if len(parts) == 2:
        try:
            # Convertir en int puis back en string pour nettoyer
            a, b = int(parts[0]), int(parts[1])
            return f"{a}-{b}"
        except:
            pass
    return score_str


def extract_odds(image_path: str):
    """
    Extrait les cotes et scores depuis une image de bookmaker.
    Version améliorée avec meilleure stabilité OCR et distinction 0/O, 1/I.
    Compatible avec l'API existante.
    """
    try:
        logger.info("🔍 Début de l'extraction OCR améliorée...")
        
        # Obtenir toutes les versions preprocessed
        versions = preprocess_image(image_path)
        
        all_texts = []
        
        # OCR sur chaque version
        for img_name, cv_img in versions:
            logger.info(f"📸 OCR sur version: {img_name}")
            try:
                # Convertir numpy array en PIL Image
                pil_img = Image.fromarray(cv_img)
                text = pytesseract.image_to_string(pil_img, lang=LANGS, config="--psm 6")
                
                if text.strip():
                    all_texts.append((img_name, text))
                    logger.info(f"✅ {img_name}: {len(text)} caractères extraits")
            except Exception as e:
                logger.warning(f"Erreur OCR {img_name}: {e}")
        
        logger.info(f"✅ {len(all_texts)} textes extraits au total")
        
        # Afficher un échantillon du meilleur texte
        if all_texts:
            longest_text = max(all_texts, key=lambda x: len(x[1]))
            logger.info(f"=== MEILLEUR TEXTE OCR ({longest_text[0]}) ===\n{longest_text[1][:300]}\n=== FIN ===")
        
        # Extraire les scores et cotes
        scores = []
        seen_scores = set()
        
        for source_name, text in all_texts:
            # Normalisation du texte
            text_normalized = text.replace("O", "0").replace("I", "1").replace("l", "1")
            text_normalized = text_normalized.replace(",", ".")
            
            # Pattern 1: Score suivi de cote - ex: "1-0 15.20"
            pattern1 = re.compile(r"(\d+[-:]\d+)\s*([0-9]+\.[0-9]+)")
            for match in pattern1.finditer(text_normalized):
                score = clean_score(match.group(1))
                
                if re.match(r'^\d{1,2}-\d{1,2}$', score):  # Format valide
                    odds_str = match.group(2)
                    try:
                        odds = float(odds_str)
                        if odds > 100:  # Probablement un pourcentage
                            continue
                        if 1.01 <= odds <= 100:
                            score_key = f"{score}_{odds}"
                            if score_key not in seen_scores:
                                scores.append({"score": score, "odds": odds})
                                seen_scores.add(score_key)
                                logger.info(f"✓ [{source_name}] Pattern1 - {score} @ {odds}")
                    except ValueError:
                        continue
            
            # Pattern 2: Extraire tous les scores, puis toutes les cotes
            all_scores_in_text = []
            all_odds_in_text = []
            
            # Scores
            score_matches = re.findall(r"(\d+[-:]\d+)", text_normalized)
            for s in score_matches:
                score = clean_score(s)
                if re.match(r'^\d{1,2}-\d{1,2}$', score):
                    all_scores_in_text.append(score)
            
            # Cotes
            odds_matches = re.findall(r"([0-9]+\.[0-9]+)", text_normalized)
            for o in odds_matches:
                try:
                    odds_val = float(o)
                    if 1.01 <= odds_val <= 100:
                        all_odds_in_text.append(odds_val)
                except:
                    continue
            
            # Associer dans l'ordre
            min_len = min(len(all_scores_in_text), len(all_odds_in_text))
            for i in range(min_len):
                score = all_scores_in_text[i]
                odds = all_odds_in_text[i]
                score_key = f"{score}_{odds}"
                if score_key not in seen_scores:
                    scores.append({"score": score, "odds": odds})
                    seen_scores.add(score_key)
                    logger.info(f"✓ [{source_name}] Pattern2 - {score} @ {odds}")
        
        # Chercher "Autre"
        combined_text = " ".join([t[1] for t in all_texts])
        for keyword in ["autre", "other", "any"]:
            other_match = re.search(rf"{keyword}\s*([0-9]+\.[0-9]+)", combined_text, re.IGNORECASE)
            if other_match:
                try:
                    odds = float(other_match.group(1))
                    if not any(s["score"] == "Autre" for s in scores):
                        scores.append({"score": "Autre", "odds": odds})
                        logger.info(f"✓ Option 'Autre' @ {odds}")
                        break
                except:
                    pass
        
        # Dédupliquer et valider
        final_scores = []
        score_odds_map = {}
        
        for item in scores:
            score = item["score"]
            odds = item["odds"]
            
            # Validation des scores
            if score != "Autre":
                parts = score.split('-')
                if len(parts) == 2:
                    try:
                        home, away = int(parts[0]), int(parts[1])
                        
                        # Rejeter les scores impossibles
                        if home < 0 or away < 0:
                            logger.warning(f"⚠️ Score rejeté (négatif): {score}")
                            continue
                        if home > 9 or away > 9:
                            logger.warning(f"⚠️ Score rejeté (>9 buts): {score}")
                            continue
                        if abs(home - away) > 4:
                            logger.warning(f"⚠️ Score rejeté (différence >4): {score}")
                            continue
                    except:
                        logger.warning(f"⚠️ Score rejeté (format invalide): {score}")
                        continue
            
            if score not in score_odds_map:
                score_odds_map[score] = []
            score_odds_map[score].append(odds)
        
        # Prendre la cote médiane pour chaque score
        for score, odds_list in score_odds_map.items():
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
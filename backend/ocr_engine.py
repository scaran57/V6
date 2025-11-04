import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
import re
import logging

# Configurer le chemin de tesseract explicitement
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

logger = logging.getLogger(__name__)

def preprocess_for_green_buttons(image_path: str):
    """
    Preprocessing optimisé pour détecter texte sur fonds colorés.
    Version améliorée supportant thèmes clairs ET sombres.
    """
    img = cv2.imread(image_path)
    processed_images = []
    
    # 1. Image originale
    processed_images.append(("original", img))
    
    # 2. Niveaux de gris
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    processed_images.append(("gray", gray))
    
    # 3. Détection automatique du thème (clair vs sombre)
    mean_brightness = np.mean(gray)
    is_dark_theme = mean_brightness < 100  # Si moyenne < 100, c'est un thème sombre
    
    logger.info(f"🎨 Thème détecté: {'SOMBRE' if is_dark_theme else 'CLAIR'} (luminosité moyenne: {mean_brightness:.1f})")
    
    if is_dark_theme:
        # THÈME SOMBRE: texte blanc sur fond noir
        # Inverser pour avoir texte noir sur fond blanc
        inverted = cv2.bitwise_not(gray)
        processed_images.append(("inverted_dark", inverted))
        
        # Améliorer le contraste sur l'image inversée
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced_inv = clahe.apply(inverted)
        processed_images.append(("enhanced_inverted", enhanced_inv))
        
        # Seuillage sur l'image inversée
        _, thresh_inv = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(("thresh_inverted", thresh_inv))
    else:
        # THÈME CLAIR: traitement classique
        # Amélioration contraste CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        processed_images.append(("enhanced", enhanced))
        
        # Augmenter luminosité et contraste
        alpha = 1.5
        beta = 30
        bright = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
        processed_images.append(("bright", bright))
        
        # Seuillage Otsu
        _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(("otsu", otsu))
    
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
        
        # Configurations OCR à tester (réduit pour performance)
        configs = [
            "--psm 6",   # Single uniform block
            "--psm 11",  # Sparse text
        ]
        
        all_texts = []
        
        # OCR sur l'image PIL originale (1 seule config)
        logger.info("📸 OCR sur image originale...")
        try:
            text = pytesseract.image_to_string(pil_img, lang="eng+fra+spa", config=configs[0])
            if text.strip():
                all_texts.append(("original", text))
        except Exception as e:
            logger.warning(f"Erreur OCR original: {e}")
        
        # OCR sur chaque version preprocessed (1 config par version)
        for img_name, cv_img in processed_images:
            logger.info(f"📸 OCR sur version: {img_name}")
            try:
                pil_from_cv = Image.fromarray(cv_img)
                text = pytesseract.image_to_string(pil_from_cv, lang="eng+fra+spa", config=configs[1])
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
            # Ignorer les % qui peuvent suivre
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
                        # Ignorer si c'est un pourcentage (< 100 est suspect, mais > 1.01)
                        if odds > 100:  # Probablement un pourcentage mal détecté
                            logger.warning(f"⚠️ Cote ignorée (>100, probablement %): {odds}")
                            continue
                        if 1.01 <= odds <= 100:
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
                parts = score.split('-')
                if len(parts) == 2:
                    try:
                        score = f"{int(parts[0])}-{int(parts[1])}"
                    except:
                        pass
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
            
            # VALIDATION: Rejeter les scores impossibles ou peu probables
            if score != "Autre":
                parts = score.split('-')
                if len(parts) == 2:
                    try:
                        home = int(parts[0])
                        away = int(parts[1])
                        
                        # Rejeter les scores impossibles:
                        # - Plus de 9 buts pour une équipe (très rare)
                        # - Différence de plus de 5 buts (peu probable)
                        # - Scores négatifs
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
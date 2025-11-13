import cv2
import pytesseract
import numpy as np
from PIL import Image
import re
import io
import logging
from debug_logger import log_debug, log_ocr_step

logger = logging.getLogger(__name__)

# Configuration Tesseract
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# Langues disponibles (multilingue)
LANGS = "eng+fra+spa"

# === NOUVEAU: Préprocesseur OCR avancé ===
USE_ADVANCED_PREPROCESSOR = False  # DÉSACTIVÉ : Crée des artefacts qui trompent l'OCR (lit 100 comme 2.0)

try:
    from tools.ocr_preprocessor import preprocess_for_ocr as advanced_preprocess
    logger.info("⚠️ Préprocesseur OCR avancé DÉSACTIVÉ (cause erreurs de lecture)")
except ImportError:
    logger.warning("⚠️ Préprocesseur OCR avancé non disponible")
    USE_ADVANCED_PREPROCESSOR = False

def preprocess_image(image_path: str, use_advanced: bool = None) -> list:
    """
    Transforme une image en plusieurs variantes prétraitées pour maximiser la lecture OCR.
    Amélioration spéciale: détection texte BLANC sur VERT (boutons Unibet/Winamax)
    + CROP automatique du haut (interface/heure) pour éviter faux positifs
    
    Args:
        image_path: Chemin de l'image
        use_advanced: Force l'utilisation du préprocesseur avancé (None = auto)
    
    Returns:
        Liste de tuples (nom_variante, image_prétraitée)
    """
    # Décider si on utilise le préprocesseur avancé
    use_adv = use_advanced if use_advanced is not None else USE_ADVANCED_PREPROCESSOR
    
    # Si préprocesseur avancé activé, l'utiliser EN PLUS des variantes classiques
    if use_adv:
        try:
            logger.info("🔧 Utilisation du préprocesseur OCR avancé")
            advanced_img = advanced_preprocess(
                image_path,
                remove_overlay=True,
                auto_crop=True,
                enhance=True,
                denoise=False
            )
            # Ajouter cette version en première position
            advanced_versions = [("advanced_full", advanced_img)]
            logger.info("✅ Prétraitement avancé réussi")
        except Exception as e:
            logger.error(f"⚠️ Erreur préprocesseur avancé: {e}")
            advanced_versions = []
    else:
        advanced_versions = []
    
    # Charger l'image
    image = Image.open(image_path).convert("RGB")
    img = np.array(image)
    
    # NOUVEAU: Couper le haut de l'image (20% supérieur = interface/heure/icônes)
    height, width = img.shape[:2]
    crop_top = int(height * 0.20)  # Enlever 20% du haut
    img_cropped = img[crop_top:, :]  # Garder de 20% à 100%
    
    logger.info(f"✂️ Image cropée: {height}px → {img_cropped.shape[0]}px (enlevé {crop_top}px du haut)")

    gray = cv2.cvtColor(img_cropped, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)

    # Détection automatique du thème
    mean_brightness = np.mean(gray)
    is_dark_theme = mean_brightness < 100
    
    logger.info(f"🎨 Thème détecté: {'SOMBRE' if is_dark_theme else 'CLAIR'} (luminosité: {mean_brightness:.1f})")

    versions = []

    # 1. Original (cropé)
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
    
    # 7. Isolation du canal ROUGE (texte blanc sur vert apparaît bien)
    if len(img_cropped.shape) == 3:
        b, g, r = cv2.split(img_cropped)
        # Inverser le rouge pour que texte blanc devienne noir
        red_inverted = cv2.bitwise_not(r)
        versions.append(("red_channel_inv", red_inverted))
        
        # 8. Seuillage sur canal vert inversé
        green_inv = cv2.bitwise_not(g)
        _, green_thresh = cv2.threshold(green_inv, 150, 255, cv2.THRESH_BINARY)
        versions.append(("green_thresh", green_thresh))
        
        # 9. Masque spécifique pour boutons verts
        hsv = cv2.cvtColor(img_cropped, cv2.COLOR_RGB2HSV)
        lower_green = np.array([25, 40, 40])
        upper_green = np.array([95, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        mask_inv = cv2.bitwise_not(mask)
        green_buttons = cv2.bitwise_and(gray, gray, mask=mask_inv)
        versions.append(("green_buttons", green_buttons))

    # Ajouter les versions avancées en premier (priorité)
    return advanced_versions + versions


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


def extract_bold_team_names_parionssport(image_path: str):
    """
    Extraction spécialisée pour Parions Sport:
    - Cible les GRANDES LETTRES en GRAS
    - Zone près des drapeaux (section haute de l'image)
    - Amélioration du contraste pour texte en gras
    """
    try:
        image = Image.open(image_path).convert("RGB")
        img = np.array(image)
        height, width = img.shape[:2]
        
        # Zone haute où se trouvent généralement les noms d'équipes (5-40% de la hauteur)
        # Élargi pour capturer plus de variantes de mise en page
        team_zone = img[int(height * 0.05):int(height * 0.40), :]
        
        # Convertir en niveaux de gris
        gray = cv2.cvtColor(team_zone, cv2.COLOR_RGB2GRAY)
        
        # Améliorer le contraste pour détecter le texte en GRAS
        # Les caractères gras ont plus de pixels noirs/foncés
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Seuillage pour isoler le texte foncé (gras)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Dilatation pour renforcer les caractères gras
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        dilated = cv2.dilate(binary, kernel, iterations=1)
        
        # OCR avec configuration pour texte large et espacé (noms d'équipes)
        # Utiliser PSM 6 (bloc de texte uniforme) et accepter lettres + espaces
        custom_config = r'--oem 3 --psm 6'
        
        text = pytesseract.image_to_string(
            Image.fromarray(dilated),
            lang=LANGS,
            config=custom_config
        )
        
        logger.info(f"🎯 OCR spécialisé Parions Sport (texte gras): {text[:300]}")
        
        # Nettoyer et extraire les noms d'équipes
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Mots à exclure (UI elements, bookmaker text, etc.)
        excluded_words_lower = {
            'league', 'ligue', 'champions', 'europa', 'conference', 'coupe', 'cup',
            'qualification', 'barrage', 'finale', 'demi', 'quart', 'huitième',
            'match', 'jour', 'journée', 'tour', 'phase', 'groupe', 'poule',
            'parions', 'sport', 'fdj', 'pmu', 'cote', 'cotes', 'score', 'exact',
            'stats', 'statistiques', 'live', 'direct', 'résultat', 'but', 'buts',
            'the', 'and', 'vs', 'versus'
        }
        
        # Filtrer les lignes qui ressemblent à des noms d'équipes
        team_candidates = []
        raw_lines_log = []
        
        for line in lines:
            raw_lines_log.append(line[:50])  # Pour debugging
            
            # Ignorer lignes trop courtes ou trop longues
            if len(line) < 2 or len(line) > 60:
                continue
            
            # Ignorer si trop de chiffres (probablement des cotes)
            digit_count = sum(1 for c in line if c.isdigit())
            if digit_count > len(line) * 0.3:
                continue
            
            # Ignorer si contient des symboles de cotes suspects (:, x, /, \)
            # Mais ACCEPTER les tirets (-) et points (.) car présents dans noms d'équipes
            suspect_symbol_count = sum(1 for c in line if c in ':x/\\')
            if suspect_symbol_count > 1:
                continue
            
            # Nettoyer la ligne
            clean_line = line.strip()
            
            # Vérifier si la ligne contient des mots exclus
            line_lower = clean_line.lower()
            words_in_line = line_lower.split()
            
            # Exclure si un mot complet est dans excluded_words_lower
            has_excluded = False
            for word in words_in_line:
                if word in excluded_words_lower:
                    has_excluded = True
                    break
            
            if has_excluded:
                continue
            
            # Garder si commence par une majuscule et contient principalement des lettres ou espaces
            alpha_space_count = sum(1 for c in clean_line if c.isalpha() or c.isspace())
            total_relevant = sum(1 for c in clean_line if c.isalpha() or c.isspace() or c in '-.')
            
            if (alpha_space_count > len(clean_line) * 0.6 and 
                clean_line[0].isupper() and
                total_relevant > len(clean_line) * 0.8):
                team_candidates.append(clean_line)
        
        logger.info(f"📄 Lignes brutes extraites: {raw_lines_log[:10]}")
        
        if team_candidates:
            logger.info(f"✅ Candidats trouvés ({len(team_candidates)}): {team_candidates}")
        else:
            logger.warning(f"⚠️ Aucun candidat trouvé. Texte brut extrait: {text[:500]}")
        
        return team_candidates
        
    except Exception as e:
        logger.error(f"Erreur extraction spécialisée: {e}")
        return []


def extract_match_info(image_path: str):
    """
    Extrait le nom du match et le bookmaker depuis l'image.
    Version améliorée avec analyse complète et détection intelligente.
    PRIORITÉ: Extraction spécialisée pour Parions Sport (texte en gras)
    """
    try:
        # Charger l'image complète
        image = Image.open(image_path).convert("RGB")
        img = np.array(image)
        
        height, width = img.shape[:2]
        
        # Analyser TOUTE l'image avec plusieurs prétraitements
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Collecter le texte avec différentes méthodes OCR
        all_texts = []
        
        # Méthode 1: OCR normal
        text1 = pytesseract.image_to_string(Image.fromarray(gray), lang=LANGS, config="--psm 6")
        all_texts.append(text1)
        
        # Méthode 2: OCR inversé (pour thèmes sombres)
        inverted = cv2.bitwise_not(gray)
        text2 = pytesseract.image_to_string(Image.fromarray(inverted), lang=LANGS, config="--psm 6")
        all_texts.append(text2)
        
        # Méthode 3: OCR avec seuillage adaptatif
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        text3 = pytesseract.image_to_string(Image.fromarray(thresh), lang=LANGS, config="--psm 6")
        all_texts.append(text3)
        
        # Méthode 4: Section centrale (15-45% de la hauteur) - évite header/footer
        # C'est ici que se trouvent généralement les noms d'équipes
        central_section = img[int(height * 0.15):int(height * 0.45), :]
        gray_central = cv2.cvtColor(central_section, cv2.COLOR_RGB2GRAY)
        text4 = pytesseract.image_to_string(Image.fromarray(gray_central), lang=LANGS, config="--psm 6")
        all_texts.append(text4)
        
        # Méthode 5: Section haute (meilleure pour titres si présents)
        top_section = img[:int(height * 0.25), :]
        gray_top = cv2.cvtColor(top_section, cv2.COLOR_RGB2GRAY)
        text5 = pytesseract.image_to_string(Image.fromarray(gray_top), lang=LANGS, config="--psm 6")
        all_texts.append(text5)
        
        # Combiner tous les textes
        all_text = "\n".join(all_texts)
        
        logger.info(f"📝 Texte OCR extrait ({len(all_text)} caractères)")
        logger.info(f"Échantillon: {all_text[:400]}")
        
        # ========== DÉTECTION DU BOOKMAKER ==========
        bookmaker = None
        bookmaker_keywords = {
            "unibet": "Unibet",
            "betclic": "BetClic", 
            "betclick": "BetClic",
            "winamax": "Winamax",
            "wina max": "Winamax",
            "pmu": "PMU",
            "parions": "Parions Sport",
            "bwin": "Bwin",
            "zebet": "ZEbet",
            "netbet": "NetBet",
            "france pari": "France Pari",
            "bet365": "Bet365",
            "1xbet": "1xBet",
            "fdj": "Parions Sport"
        }
        
        text_lower = all_text.lower()
        for keyword, name in bookmaker_keywords.items():
            if keyword in text_lower:
                bookmaker = name
                logger.info(f"✓ Bookmaker: {keyword} → {name}")
                break
        
        # Fallback: nom de fichier
        if not bookmaker:
            filename_lower = image_path.lower()
            for keyword, name in bookmaker_keywords.items():
                if keyword in filename_lower:
                    bookmaker = name
                    logger.info(f"✓ Bookmaker (fichier): {name}")
                    break
        
        # ========== DÉTECTION DU NOM DU MATCH ==========
        match_name = None
        
        # SI PARIONS SPORT DÉTECTÉ : Utiliser l'extraction spécialisée pour texte en GRAS
        if bookmaker and "Parions" in bookmaker:
            logger.info("🎯 Bookmaker Parions Sport détecté - Utilisation extraction spécialisée (texte gras)")
            bold_teams = extract_bold_team_names_parionssport(image_path)
            
            # Vérifier si un candidat contient déjà les deux équipes séparées par "-"
            for candidate in bold_teams:
                if " - " in candidate or " -" in candidate or "- " in candidate:
                    # Splitter sur le tiret
                    parts = re.split(r'\s*-\s*', candidate)
                    if len(parts) == 2:
                        team1 = parts[0].strip()
                        team2 = parts[1].strip()
                        if len(team1) >= 2 and len(team2) >= 2:
                            match_name = f"{team1} - {team2}"
                            logger.info(f"✅ Match détecté (ligne complète avec tiret): {match_name}")
                            return {"match_name": match_name, "bookmaker": bookmaker}
            
            if len(bold_teams) >= 2:
                # Prendre les 2 premiers candidats comme équipes
                match_name = f"{bold_teams[0]} - {bold_teams[1]}"
                logger.info(f"✅ Match détecté (méthode gras - 2 lignes): {match_name}")
                return {"match_name": match_name, "bookmaker": bookmaker}
            elif len(bold_teams) == 1:
                # Un seul nom détecté, chercher le second dans le texte général
                match_name = f"{bold_teams[0]} - ?"
                logger.info(f"⚠️ Un seul nom détecté (méthode gras): {bold_teams[0]}")
        
        # Extraire toutes les lignes du texte (méthode classique si Parions Sport échoue ou autre bookmaker)
        lines = all_text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        # Mots/phrases à exclure (interface, boutons, contexte, bookmakers)
        excluded_words = {
            'score', 'exact', 'cote', 'match', 'autre', 'but', 'foot', 'football',
            'preview', 'bookmaker', 'top', 'voir', 'cotes', 'extraites', 'scores',
            'inscrire', 'connexion', 'parier', 'paris', 'live', 'direct', 'resultat',
            'probabilite', 'recommandation', 'interpretation', 'confiance', 'analyse',
            'analyser', 'predire', 'upload', 'image', 'choisir', 'glissez', 'cliquez',
            'temps', 'ecart', 'handicap', 'corner', 'carton', 'penalty', 'buteur',
            'ligue', 'champions', 'europa', 'coupe', 'division', 'finale', 'groupe',
            'journee', 'tour', 'phase', 'qualification', 'premier', 'deuxieme',
            'coro', 'produit', 'made', 'with', 'emergent', 'plus', 'probable',
            'aptos', 'application', 'android', 'ios', 'mobile', 'championsleague',
            'unibet', 'betclic', 'winamax', 'parions', 'sport', 'fdj', 'pmu',
            'stats', 'compos', 'mesure', 'parisurmesure', 'compositions', 'statistiques'
        }
        
        # Phrases à exclure (multi-mots)
        excluded_phrases = {
            'mi-temps', 'mi temps', 'score exact', 'the coro', 'coro produit',
            'top scores', 'top 3', 'niveau de', 'made with', 'pari sur mesure',
            'sur mesure'
        }
        
        # Chercher les noms d'équipes (mots capitalisés de 3+ caractères)
        team_candidates = []
        for line in lines:
            # Ignorer les lignes avec beaucoup de chiffres ou de symboles
            if len(re.findall(r'\d', line)) > len(line) * 0.3:
                continue
            if len(line) < 3 or len(line) > 40:
                continue
            
            # Chercher des mots qui commencent par une majuscule
            words = line.split()
            team_name_parts = []
            for word in words:
                # Nettoyer le mot (enlever ponctuation)
                clean_word = re.sub(r'[^\w\s\-\'À-ÿ]', '', word)
                
                # Mot commence par majuscule, pas de chiffres, 3+ caractères
                if clean_word and clean_word[0].isupper() and not any(c.isdigit() for c in clean_word) and len(clean_word) >= 3:
                    # Exclure les mots communs d'interface
                    if clean_word.lower() not in excluded_words:
                        team_name_parts.append(clean_word)
            
            if team_name_parts:
                potential_team = ' '.join(team_name_parts[:3])  # Max 3 mots
                
                # Vérifier que ce n'est pas une phrase exclue
                is_excluded = False
                for excluded_phrase in excluded_phrases:
                    if excluded_phrase in potential_team.lower():
                        is_excluded = True
                        break
                
                if not is_excluded and len(potential_team) >= 4:
                    team_candidates.append(potential_team)
        
        # Filtrer et dédupliquer
        team_candidates = list(dict.fromkeys(team_candidates))  # Garder l'ordre, supprimer doublons
        
        logger.info(f"🔍 Équipes candidates: {team_candidates[:10]}")
        
        # Chercher des paires d'équipes
        if len(team_candidates) >= 2:
            # Prendre les 2 premières équipes différentes et valides
            team1 = None
            team2 = None
            
            # Trouver la première équipe valide
            for candidate in team_candidates:
                # Une vraie équipe a généralement au moins 4 caractères
                # et ne contient pas trop de mots (max 3)
                word_count = len(candidate.split())
                if len(candidate) >= 4 and word_count <= 3:
                    team1 = candidate
                    break
            
            if team1:
                # Chercher la deuxième équipe (différente)
                for candidate in team_candidates:
                    if candidate == team1:
                        continue
                    
                    # Vérifier que ce n'est pas une variation du même nom
                    similarity_check = (
                        candidate.lower() != team1.lower() and 
                        not (candidate.lower() in team1.lower()) and 
                        not (team1.lower() in candidate.lower())
                    )
                    
                    word_count = len(candidate.split())
                    if similarity_check and len(candidate) >= 4 and word_count <= 3:
                        team2 = candidate
                        break
            
            if team1 and team2:
                # Nettoyer les noms d'équipes (enlever les mots collés type "ChampionsLeague")
                team1_clean = ' '.join([w for w in team1.split() if w.lower() not in excluded_words and len(w) >= 3])
                team2_clean = ' '.join([w for w in team2.split() if w.lower() not in excluded_words and len(w) >= 3])
                
                if team1_clean and team2_clean:
                    match_name = f"{team1_clean} - {team2_clean}"  # Utiliser tiret au lieu de "vs"
                    logger.info(f"✓ Match détecté: {match_name}")
        
        # Pattern alternatif: chercher "vs", "v", "-" dans le texte
        if not match_name:
            vs_patterns = [
                r"([A-ZÀ-Ÿ][a-zA-ZÀ-ÿ\s]{2,20})\s+(?:vs\.?|v\.?|-|—)\s+([A-ZÀ-Ÿ][a-zA-ZÀ-ÿ\s]{2,20})",
            ]
            
            for pattern in vs_patterns:
                matches = re.finditer(pattern, all_text, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    team1 = match.group(1).strip()
                    team2 = match.group(2).strip()
                    
                    # Validation et nettoyage
                    if len(team1) >= 3 and len(team2) >= 3:
                        if not any(c.isdigit() for c in team1+team2):
                            # Nettoyer les noms
                            team1_clean = ' '.join([w for w in team1.split() if w.lower() not in excluded_words and len(w) >= 3])
                            team2_clean = ' '.join([w for w in team2.split() if w.lower() not in excluded_words and len(w) >= 3])
                            
                            if team1_clean and team2_clean:
                                match_name = f"{team1_clean} - {team2_clean}"  # Tiret au lieu de "vs"
                                logger.info(f"✓ Match (pattern): {match_name}")
                                break
                
                if match_name:
                    break
        
        logger.info(f"🏟️ Résultat final - Match: {match_name or 'Match non détecté'}")
        logger.info(f"🎰 Résultat final - Bookmaker: {bookmaker or 'Bookmaker inconnu'}")
        
        return {
            "match_name": match_name or "Match non détecté",
            "bookmaker": bookmaker or "Bookmaker inconnu"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur extraction: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "match_name": "Match non détecté",
            "bookmaker": "Bookmaker inconnu"
        }


def extract_odds_with_vision(image_path: str):
    """
    Extrait les cotes via Vision GPT-4 OCR (plus précis que Tesseract)
    """
    try:
        from tools.vision_ocr import extract_odds_from_image
        logger.info("🔮 Utilisation de Vision GPT-4 OCR pour extraction des cotes...")
        result = extract_odds_from_image(image_path)
        
        # Si Vision OCR retourne un dict structuré, le convertir au format attendu
        if isinstance(result, dict) and 'raw_text' in result:
            # Vision OCR a échoué, fallback Tesseract
            logger.warning("⚠️ Vision OCR a échoué, fallback vers Tesseract")
            return extract_odds_tesseract(image_path)
        
        return result
    except Exception as e:
        logger.error(f"❌ Erreur Vision OCR: {e}")
        logger.info("↩️ Fallback vers Tesseract")
        return extract_odds_tesseract(image_path)

def extract_odds(image_path: str, use_vision: bool = False):
    """
    Extrait les cotes et scores depuis une image de bookmaker.
    
    Args:
        image_path: Chemin de l'image
        use_vision: Si True, utilise Vision GPT-4 (plus précis, mais coûte des tokens)
    
    Returns:
        Liste de dicts {"score": "X-Y", "odds": float}
    """
    if use_vision:
        return extract_odds_with_vision(image_path)
    else:
        return extract_odds_tesseract(image_path)

def extract_odds_tesseract(image_path: str):
    """
    Extrait les cotes et scores depuis une image de bookmaker via Tesseract.
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
                
                # Utiliser PSM 11 (sparse text) pour boutons isolés si c'est une version spéciale
                if img_name in ["red_channel_inv", "green_thresh", "green_buttons"]:
                    text = pytesseract.image_to_string(pil_img, lang=LANGS, config="--psm 11")
                else:
                    text = pytesseract.image_to_string(pil_img, lang=LANGS, config="--psm 6")
                
                if text.strip():
                    all_texts.append((img_name, text))
                    logger.info(f"✅ {img_name}: {len(text)} caractères extraits")
            except Exception as e:
                logger.warning(f"Erreur OCR {img_name}: {e}")
        
        logger.info(f"✅ {len(all_texts)} textes extraits au total")
        
        # DEBUG: Log étape OCR
        log_ocr_step("Extraction OCR complétée", len(all_texts))
        
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
            
            # Cotes (nombres décimaux entre 1.01 et 100)
            odds_matches = re.findall(r"([0-9]+\.[0-9]+)", text_normalized)
            for o in odds_matches:
                try:
                    odds_val = float(o)
                    if 1.01 <= odds_val <= 100:
                        all_odds_in_text.append(odds_val)
                except:
                    continue
            
            # NOUVEAU: Aussi chercher nombres ENTIERS comme cotes (ex: "13", "24")
            # Format Unibet avec gros chiffres
            integer_odds = re.findall(r"\b([1-9][0-9]?)\b", text_normalized)
            for o in integer_odds:
                try:
                    odds_val = float(o)
                    if 2 <= odds_val <= 100:  # Cotes entières raisonnables
                        all_odds_in_text.append(odds_val)
                except:
                    continue
            
            logger.info(f"[{source_name}] Scores: {len(all_scores_in_text)}, Cotes: {len(all_odds_in_text)}")
            
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
        
        # DEBUG: Log scores finaux extraits
        log_ocr_step("Scores validés et filtrés", len(final_scores), final_scores)
        
        return final_scores
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'extraction OCR: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []
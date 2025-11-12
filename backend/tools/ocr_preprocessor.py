#!/usr/bin/env python3
"""
OCR Preprocessor - Nettoyage et optimisation d'images pour améliorer l'OCR
Gère les overlays, le bruit, et optimise le contraste pour extraire le texte.

Techniques implémentées :
- Suppression du bruit par filtrage gaussien
- Recadrage automatique des zones texte
- Conversion noir et blanc avec threshold adaptatif
- Détection et suppression d'overlays
- Amélioration du contraste (CLAHE)
"""

import cv2
import numpy as np
import logging
from typing import Tuple, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def remove_overlays(img: np.ndarray) -> np.ndarray:
    """
    Supprime les overlays colorés (scores, logos, UI) de l'image.
    
    Stratégie :
    - Détecte les zones avec saturation élevée (overlays colorés)
    - Les remplace par du blanc/gris pour ne pas perturber l'OCR
    
    Args:
        img: Image BGR (OpenCV format)
    
    Returns:
        Image nettoyée
    """
    # Convertir en HSV pour détecter les zones colorées
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Masque pour les zones très saturées (overlays colorés)
    # Saturation > 100, Value > 50
    lower_overlay = np.array([0, 100, 50])
    upper_overlay = np.array([180, 255, 255])
    mask = cv2.inRange(hsv, lower_overlay, upper_overlay)
    
    # Dilater le masque pour capturer toute la zone overlay
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=2)
    
    # Remplacer les zones overlay par du blanc
    img_clean = img.copy()
    img_clean[mask > 0] = [255, 255, 255]
    
    logger.debug(f"Overlays supprimés : {np.sum(mask > 0)} pixels modifiés")
    
    return img_clean


def auto_crop_text_regions(img: np.ndarray) -> np.ndarray:
    """
    Recadrage automatique pour garder uniquement les zones de texte.
    
    Stratégie :
    - Détecte les zones avec beaucoup de contours (texte)
    - Garde la région centrale contenant le plus de texte
    - Coupe les marges vides (header/footer)
    
    Args:
        img: Image BGR
    
    Returns:
        Image recadrée
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Détection de contours pour trouver les zones de texte
    edges = cv2.Canny(gray, 50, 150)
    
    # Trouver les contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        logger.warning("Aucun contour détecté, pas de recadrage")
        return img
    
    # Trouver le rectangle englobant de tous les contours
    x_min, y_min = img.shape[1], img.shape[0]
    x_max, y_max = 0, 0
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        x_min = min(x_min, x)
        y_min = min(y_min, y)
        x_max = max(x_max, x + w)
        y_max = max(y_max, y + h)
    
    # Ajouter une marge de 10 pixels
    margin = 10
    x_min = max(0, x_min - margin)
    y_min = max(0, y_min - margin)
    x_max = min(img.shape[1], x_max + margin)
    y_max = min(img.shape[0], y_max + margin)
    
    # Recadrer
    cropped = img[y_min:y_max, x_min:x_max]
    
    logger.debug(f"Image recadrée : {img.shape} → {cropped.shape}")
    
    return cropped


def enhance_contrast(img: np.ndarray) -> np.ndarray:
    """
    Améliore le contraste de l'image avec CLAHE (Contrast Limited Adaptive Histogram Equalization).
    
    Args:
        img: Image BGR ou grayscale
    
    Returns:
        Image avec contraste amélioré
    """
    # Convertir en niveaux de gris si nécessaire
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    # Appliquer CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    logger.debug("Contraste amélioré avec CLAHE")
    
    return enhanced


def adaptive_threshold(img: np.ndarray) -> np.ndarray:
    """
    Convertit l'image en noir et blanc avec threshold adaptatif.
    Meilleur que le threshold global pour gérer les variations d'éclairage.
    
    Args:
        img: Image grayscale
    
    Returns:
        Image binaire (noir et blanc)
    """
    # Appliquer un flou gaussien pour réduire le bruit
    blurred = cv2.GaussianBlur(img, (3, 3), 0)
    
    # Threshold adaptatif
    binary = cv2.adaptiveThreshold(
        blurred, 
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,  # Taille du voisinage
        2    # Constante soustraite
    )
    
    logger.debug("Threshold adaptatif appliqué")
    
    return binary


def denoise_image(img: np.ndarray) -> np.ndarray:
    """
    Supprime le bruit de l'image avec un filtre non-local means.
    
    Args:
        img: Image BGR ou grayscale
    
    Returns:
        Image débruitée
    """
    if len(img.shape) == 3:
        # Image couleur
        denoised = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    else:
        # Image grayscale
        denoised = cv2.fastNlMeansDenoising(img, None, 10, 7, 21)
    
    logger.debug("Bruit supprimé")
    
    return denoised


def preprocess_for_ocr(
    img_path: str,
    remove_overlay: bool = True,
    auto_crop: bool = True,
    enhance: bool = True,
    denoise: bool = False,
    output_path: Optional[str] = None
) -> np.ndarray:
    """
    Pipeline complet de prétraitement pour optimiser l'OCR.
    
    Args:
        img_path: Chemin de l'image à traiter
        remove_overlay: Supprimer les overlays colorés
        auto_crop: Recadrer automatiquement les zones de texte
        enhance: Améliorer le contraste
        denoise: Supprimer le bruit (lent)
        output_path: Chemin pour sauvegarder l'image prétraitée (optionnel)
    
    Returns:
        Image prétraitée (grayscale)
    """
    logger.info(f"🔧 Prétraitement OCR : {img_path}")
    
    # Charger l'image
    img = cv2.imread(img_path)
    
    if img is None:
        raise ValueError(f"Impossible de charger l'image : {img_path}")
    
    logger.debug(f"Image chargée : {img.shape}")
    
    # Étape 1 : Supprimer les overlays
    if remove_overlay:
        img = remove_overlays(img)
    
    # Étape 2 : Recadrage automatique
    if auto_crop:
        img = auto_crop_text_regions(img)
    
    # Étape 3 : Débruitage (optionnel, lent)
    if denoise:
        img = denoise_image(img)
    
    # Étape 4 : Conversion en niveaux de gris
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    
    # Étape 5 : Amélioration du contraste
    if enhance:
        gray = enhance_contrast(gray)
    
    # Étape 6 : Threshold adaptatif
    binary = adaptive_threshold(gray)
    
    # Sauvegarder si demandé
    if output_path:
        cv2.imwrite(output_path, binary)
        logger.info(f"✅ Image prétraitée sauvegardée : {output_path}")
    
    logger.info(f"✅ Prétraitement terminé : {img.shape} → {binary.shape}")
    
    return binary


def preprocess_multiple_variants(img_path: str, output_dir: Optional[str] = None) -> List[Tuple[str, np.ndarray]]:
    """
    Crée plusieurs variantes prétraitées de l'image pour maximiser les chances de bon OCR.
    
    Args:
        img_path: Chemin de l'image source
        output_dir: Dossier pour sauvegarder les variantes (optionnel)
    
    Returns:
        Liste de tuples (nom_variante, image_prétraitée)
    """
    logger.info(f"🔄 Génération de variantes pour : {img_path}")
    
    variants = []
    
    # Variante 1 : Traitement complet
    try:
        v1 = preprocess_for_ocr(img_path, remove_overlay=True, auto_crop=True, enhance=True, denoise=False)
        variants.append(("full_processing", v1))
    except Exception as e:
        logger.error(f"Erreur variante 1: {e}")
    
    # Variante 2 : Sans recadrage (garde tout)
    try:
        v2 = preprocess_for_ocr(img_path, remove_overlay=True, auto_crop=False, enhance=True, denoise=False)
        variants.append(("no_crop", v2))
    except Exception as e:
        logger.error(f"Erreur variante 2: {e}")
    
    # Variante 3 : Minimal (juste threshold)
    try:
        v3 = preprocess_for_ocr(img_path, remove_overlay=False, auto_crop=False, enhance=True, denoise=False)
        variants.append(("minimal", v3))
    except Exception as e:
        logger.error(f"Erreur variante 3: {e}")
    
    # Sauvegarder les variantes si demandé
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        base_name = Path(img_path).stem
        
        for i, (variant_name, img) in enumerate(variants):
            output_path = Path(output_dir) / f"{base_name}_{variant_name}.png"
            cv2.imwrite(str(output_path), img)
            logger.debug(f"Variante sauvegardée : {output_path}")
    
    logger.info(f"✅ {len(variants)} variantes générées")
    
    return variants


# Test du module
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) < 2:
        print("Usage: python ocr_preprocessor.py <image_path>")
        sys.exit(1)
    
    img_path = sys.argv[1]
    
    print("=" * 70)
    print("TEST OCR PREPROCESSOR")
    print("=" * 70)
    print()
    
    # Test prétraitement simple
    print("📸 Test 1: Prétraitement simple")
    try:
        processed = preprocess_for_ocr(img_path, output_path="/tmp/preprocessed_test.png")
        print(f"✅ Image prétraitée : {processed.shape}")
        print(f"   Sauvegardée : /tmp/preprocessed_test.png")
    except Exception as e:
        print(f"❌ Erreur : {e}")
    
    print()
    
    # Test variantes multiples
    print("📸 Test 2: Génération de variantes")
    try:
        variants = preprocess_multiple_variants(img_path, output_dir="/tmp/ocr_variants")
        print(f"✅ {len(variants)} variantes générées")
        print("   Sauvegardées dans : /tmp/ocr_variants/")
    except Exception as e:
        print(f"❌ Erreur : {e}")
    
    print()
    print("=" * 70)

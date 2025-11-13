#!/usr/bin/env python3
"""
Script de test pour l'intégration Vision OCR avec GPT-4 Vision
Teste l'extraction de données d'une image de bookmaker
"""

import sys
import os

# Ajouter le répertoire backend au path
sys.path.insert(0, '/app/backend')

from tools.vision_ocr import extract_odds_from_image
import json

def test_vision_ocr():
    """
    Test l'extraction OCR avec Vision AI
    """
    print("=" * 70)
    print("🧪 TEST VISION OCR - GPT-4 Vision + Emergent LLM Key")
    print("=" * 70)
    
    # Vérifier si une image de test existe
    test_images = [
        "/app/tests/bookmaker_samples/sample1.jpg",
        "/app/tests/bookmaker_samples/sample1.png",
        "/app/backend/test_image.jpg",
        "/app/backend/test_image.png"
    ]
    
    test_image = None
    for img in test_images:
        if os.path.exists(img):
            test_image = img
            break
    
    if not test_image:
        print("❌ Aucune image de test trouvée!")
        print(f"   Chemins testés: {test_images}")
        print("\n💡 Pour tester, placez une image de bookmaker à l'un de ces emplacements.")
        return
    
    print(f"\n📸 Image de test: {test_image}\n")
    
    # Test 1: Extraction avec Vision OCR
    print("=" * 70)
    print("TEST 1: Extraction avec système intelligent (Tesseract → GPT-4 Vision)")
    print("=" * 70)
    
    result = extract_odds_from_image(test_image)
    
    print(f"\n✅ Résultat:")
    print(f"   Provider: {result.get('provider', 'unknown')}")
    print(f"   Confidence: {result.get('confidence', 0.0):.2f}")
    print(f"\n📊 Données extraites:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Vérifier si c'était Tesseract ou Vision
    if result.get('provider') == 'tesseract':
        print("\n⚠️  Tesseract a été utilisé (confiance suffisante)")
        print("    Pour forcer GPT-4 Vision, diminuez TESSERACT_MIN_CONFIDENCE dans vision_ocr.py")
    elif result.get('provider') == 'gpt4_vision':
        print("\n✅ GPT-4 Vision a été utilisé avec succès!")
        print("    Vérifiez si les données extraites sont correctes:")
        if result.get('league'):
            print(f"    • Ligue: {result.get('league')}")
        if result.get('home_team'):
            print(f"    • Équipe domicile: {result.get('home_team')}")
        if result.get('away_team'):
            print(f"    • Équipe extérieure: {result.get('away_team')}")
        if result.get('home_odds'):
            print(f"    • Cote domicile: {result.get('home_odds')}")
        if result.get('draw_odds'):
            print(f"    • Cote nul: {result.get('draw_odds')}")
        if result.get('away_odds'):
            print(f"    • Cote extérieure: {result.get('away_odds')}")
    
    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)

if __name__ == "__main__":
    test_vision_ocr()

#!/usr/bin/env python3
"""
Diagnostic OCR complet
Teste GPT-Vision et Tesseract sur une image test
"""
import os
import sys

sys.path.insert(0, '/app')
sys.path.insert(0, '/app/backend')

TEST_FILE = "/app/test_images/ocr_test_premierleague.jpg"

print("="*70)
print("DIAGNOSTIC OCR COMPLET")
print("="*70)

# Vérifier l'image test
if not os.path.exists(TEST_FILE):
    print(f"❌ Image test manquante: {TEST_FILE}")
    print("\n💡 Générez l'image avec:")
    print("   python /app/generate_test_image.py")
    exit(1)

print(f"✅ Image trouvée: {TEST_FILE}")
print(f"   Taille: {os.path.getsize(TEST_FILE)} bytes")

# Test 1: Pipeline OCR unifié
print("\n" + "="*70)
print("TEST 1: Pipeline OCR unifié (core.ocr_pipeline)")
print("="*70)

try:
    from core.ocr_pipeline import process_image
    
    # Test GPT-Vision
    print("\n🤖 Test GPT-Vision:")
    print("-" * 50)
    gpt_result = process_image(TEST_FILE, prefer_gpt_vision=True)
    print(f"Moteur utilisé: {gpt_result.get('ocr_engine')}")
    print(f"Succès: {gpt_result.get('success')}")
    print(f"Confiance: {gpt_result.get('confidence', 0):.2%}")
    print(f"Scores extraits: {len(gpt_result.get('parsed_scores', []))}")
    
    if gpt_result.get('parsed_scores'):
        print("\nPremiers scores:")
        for score in gpt_result['parsed_scores'][:3]:
            print(f"  {score}")
    
    # Test Tesseract
    print("\n📝 Test Tesseract:")
    print("-" * 50)
    tess_result = process_image(TEST_FILE, prefer_gpt_vision=False)
    print(f"Moteur utilisé: {tess_result.get('ocr_engine')}")
    print(f"Succès: {tess_result.get('success')}")
    print(f"Confiance: {tess_result.get('confidence', 0):.2%}")
    print(f"Scores extraits: {len(tess_result.get('parsed_scores', []))}")
    
    if tess_result.get('parsed_scores'):
        print("\nPremiers scores:")
        for score in tess_result['parsed_scores'][:3]:
            print(f"  {score}")
    
    # Texte brut
    if tess_result.get('raw_text'):
        print("\nTexte brut (premiers 200 caractères):")
        print(tess_result['raw_text'][:200])
    
except Exception as e:
    print(f"❌ Erreur pipeline unifié: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Système OCR existant
print("\n" + "="*70)
print("TEST 2: Système OCR existant (ocr_engine.py)")
print("="*70)

try:
    from ocr_engine import extract_odds
    
    result = extract_odds(TEST_FILE)
    
    print(f"Scores extraits: {len(result.get('extractedScores', []))}")
    print(f"Texte brut disponible: {bool(result.get('rawText'))}")
    
    if result.get('extractedScores'):
        print("\nPremiers scores:")
        for score in result['extractedScores'][:5]:
            print(f"  {score}")
    
except Exception as e:
    print(f"❌ Erreur système existant: {e}")

# Test 3: Vision OCR
print("\n" + "="*70)
print("TEST 3: GPT-4 Vision (tools/vision_ocr_scores.py)")
print("="*70)

try:
    from tools.vision_ocr_scores import extract_odds_from_image
    
    result = extract_odds_from_image(TEST_FILE)
    
    if isinstance(result, list):
        print(f"✅ Scores extraits: {len(result)}")
        if result:
            print("\nPremiers scores:")
            for score in result[:5]:
                print(f"  {score}")
    elif isinstance(result, dict) and 'scores' in result:
        scores = result['scores']
        print(f"✅ Scores extraits: {len(scores)}")
        if scores:
            print("\nPremiers scores:")
            for score in scores[:5]:
                print(f"  {score}")
    else:
        print(f"⚠️ Format de résultat inattendu: {type(result)}")
    
except Exception as e:
    print(f"❌ Erreur GPT-4 Vision: {e}")
    import traceback
    traceback.print_exc()

# Résumé
print("\n" + "="*70)
print("RÉSUMÉ")
print("="*70)

tests_ok = []
tests_fail = []

try:
    from core.ocr_pipeline import process_image
    r = process_image(TEST_FILE, prefer_gpt_vision=False)
    if r.get('success'):
        tests_ok.append("Pipeline OCR ✅")
    else:
        tests_fail.append("Pipeline OCR ❌")
except:
    tests_fail.append("Pipeline OCR ❌")

try:
    from ocr_engine import extract_odds
    r = extract_odds(TEST_FILE)
    if r.get('extractedScores'):
        tests_ok.append("OCR Existant ✅")
    else:
        tests_fail.append("OCR Existant ❌")
except:
    tests_fail.append("OCR Existant ❌")

try:
    from tools.vision_ocr_scores import extract_odds_from_image
    r = extract_odds_from_image(TEST_FILE)
    if r and len(r) > 0:
        tests_ok.append("GPT-4 Vision ✅")
    else:
        tests_fail.append("GPT-4 Vision ❌")
except:
    tests_fail.append("GPT-4 Vision ❌")

print("\n✅ Tests réussis:")
for test in tests_ok:
    print(f"   {test}")

if tests_fail:
    print("\n❌ Tests échoués:")
    for test in tests_fail:
        print(f"   {test}")

print(f"\n📊 Score: {len(tests_ok)}/{len(tests_ok) + len(tests_fail)} ({len(tests_ok)/(len(tests_ok) + len(tests_fail))*100:.1f}%)")
print("="*70)

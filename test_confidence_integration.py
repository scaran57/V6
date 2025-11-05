#!/usr/bin/env python3
"""
Test de l'intégration du calcul de confiance dans le système complet
"""
import sys
sys.path.insert(0, '/app/backend')

from score_predictor import calculate_probabilities, calculate_confidence

# Scores d'exemple
test_scores_1 = [
    {"score": "2-0", "odds": 7.25},
    {"score": "1-1", "odds": 17.75},
    {"score": "0-1", "odds": 6.5},
    {"score": "2-1", "odds": 7.8},
    {"score": "0-0", "odds": 9.5}
]

test_scores_2 = [
    {"score": "1-0", "odds": 2.1},  # Cote très basse = favori clair
    {"score": "2-0", "odds": 8.5},
    {"score": "0-1", "odds": 12.0}
]

print("╔════════════════════════════════════════════════════════════════════╗")
print("║    🧪 TEST D'INTÉGRATION - CALCUL DE CONFIANCE GLOBALE            ║")
print("╚════════════════════════════════════════════════════════════════════╝")
print()

# ============================================================================
# TEST 1: Distribution équilibrée
# ============================================================================
print("─" * 70)
print("🎯 TEST 1: DISTRIBUTION ÉQUILIBRÉE (plusieurs scores possibles)")
print("─" * 70)
print()

result1 = calculate_probabilities(test_scores_1, diff_expected=2, use_odds_weighting=False)

print(f"Score le plus probable: {result1['mostProbableScore']}")
print(f"Probabilité: {result1['probabilities'][result1['mostProbableScore']]:.2f}%")
print(f"Confiance: {result1['confidence']:.3f} ({result1['confidence']*100:.1f}%)")
print()

sorted_probs = sorted(result1['probabilities'].items(), key=lambda x: x[1], reverse=True)
print("Top 3:")
for i, (score, prob) in enumerate(sorted_probs[:3], 1):
    print(f"   {i}. {score} → {prob:.2f}%")
print()

# ============================================================================
# TEST 2: Favori clair
# ============================================================================
print("─" * 70)
print("🎯 TEST 2: FAVORI CLAIR (un score domine)")
print("─" * 70)
print()

result2 = calculate_probabilities(test_scores_2, diff_expected=2, use_odds_weighting=False)

print(f"Score le plus probable: {result2['mostProbableScore']}")
print(f"Probabilité: {result2['probabilities'][result2['mostProbableScore']]:.2f}%")
print(f"Confiance: {result2['confidence']:.3f} ({result2['confidence']*100:.1f}%)")
print()

sorted_probs2 = sorted(result2['probabilities'].items(), key=lambda x: x[1], reverse=True)
print("Top 3:")
for i, (score, prob) in enumerate(sorted_probs2[:3], 1):
    print(f"   {i}. {score} → {prob:.2f}%")
print()

# ============================================================================
# COMPARAISON
# ============================================================================
print("═" * 70)
print("📊 ANALYSE DE LA CONFIANCE")
print("═" * 70)
print()

print(f"Test 1 (équilibré):")
print(f"   • Meilleur score: {result1['mostProbableScore']} à {result1['probabilities'][result1['mostProbableScore']]:.1f}%")
print(f"   • Confiance: {result1['confidence']:.3f} → Moyenne (plusieurs possibilités)")
print()

print(f"Test 2 (favori clair):")
print(f"   • Meilleur score: {result2['mostProbableScore']} à {result2['probabilities'][result2['mostProbableScore']]:.1f}%")
print(f"   • Confiance: {result2['confidence']:.3f} → Élevée (domination claire)")
print()

print("💡 Interprétation de la confiance:")
print("   • 0.0 - 0.4 : Confiance FAIBLE (très incertain)")
print("   • 0.4 - 0.7 : Confiance MOYENNE (plusieurs possibilités)")
print("   • 0.7 - 1.0 : Confiance ÉLEVÉE (prédiction fiable)")
print()

# ============================================================================
# TEST AVEC PONDÉRATION PAR COTES
# ============================================================================
print("═" * 70)
print("🚀 TEST 3: AVEC PONDÉRATION PAR COTES")
print("═" * 70)
print()

result3 = calculate_probabilities(test_scores_1, diff_expected=2, use_odds_weighting=True)

print(f"Score le plus probable: {result3['mostProbableScore']}")
print(f"Probabilité: {result3['probabilities'][result3['mostProbableScore']]:.2f}%")
print(f"Confiance: {result3['confidence']:.3f} ({result3['confidence']*100:.1f}%)")
print()

print("Impact de la pondération par cotes:")
print(f"   Sans pondération: confiance = {result1['confidence']:.3f}")
print(f"   Avec pondération: confiance = {result3['confidence']:.3f}")
print(f"   Différence: {(result3['confidence'] - result1['confidence']):.3f}")
print()

print("✅ Tests terminés avec succès!")
print()

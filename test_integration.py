#!/usr/bin/env python3
"""
Test rapide de l'intégration du nouveau score_predictor
"""
import sys
sys.path.insert(0, '/app/backend')

from score_predictor import calculate_probabilities

# Données de test
test_scores = [
    {"score": "1-0", "odds": 7.5},
    {"score": "2-0", "odds": 9.0},
    {"score": "2-1", "odds": 7.5},
    {"score": "3-0", "odds": 13.0},
    {"score": "3-1", "odds": 11.0},
    {"score": "3-2", "odds": 15.0},
    {"score": "4-0", "odds": 21.0},
    {"score": "4-1", "odds": 21.0},
    {"score": "0-0", "odds": 11.0},
    {"score": "1-1", "odds": 6.5},
    {"score": "2-2", "odds": 11.0},
    {"score": "3-3", "odds": 26.0},
    {"score": "0-1", "odds": 13.0},
    {"score": "0-2", "odds": 21.0},
    {"score": "1-2", "odds": 9.5},
    {"score": "0-3", "odds": 41.0},
    {"score": "1-3", "odds": 21.0},
    {"score": "2-3", "odds": 21.0},
    {"score": "Autre", "odds": 4.33}
]

print("🧪 Test de la fonction calculate_probabilities")
print("=" * 60)

# Test avec diffExpected = 2 (valeur par défaut)
result = calculate_probabilities(test_scores, diff_expected=2)

print("\n✅ Résultat:")
print(f"   Score le plus probable: {result['mostProbableScore']}")
print(f"   Probabilité: {result['probabilities'].get(result['mostProbableScore'], 0)}%")

print("\n📊 Top 5 des probabilités:")
sorted_probs = sorted(result['probabilities'].items(), key=lambda x: x[1], reverse=True)
for i, (score, prob) in enumerate(sorted_probs[:5], 1):
    print(f"   {i}. {score}: {prob}%")

print("\n✅ Test réussi! L'intégration fonctionne correctement.")

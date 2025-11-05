#!/usr/bin/env python3
"""
Test du module de pondération par cote bookmaker
Compare les résultats avec et sans pondération
"""
import sys
sys.path.insert(0, '/app/backend')

from score_predictor import calculate_probabilities, process_scores_with_odds

# Scores d'exemple (similaires à ceux extraits de Betclic)
test_scores = [
    {"score": "1-0", "odds": 8.75},
    {"score": "2-0", "odds": 7.25},
    {"score": "1-1", "odds": 17.75},
    {"score": "2-1", "odds": 7.8},
    {"score": "2-2", "odds": 15.5},
    {"score": "0-1", "odds": 6.5},
    {"score": "0-2", "odds": 11.0},
    {"score": "1-2", "odds": 8.2},
    {"score": "3-0", "odds": 12.0},
    {"score": "0-0", "odds": 9.5}
]

print("╔════════════════════════════════════════════════════════════════════╗")
print("║      🧪 TEST DE LA PONDÉRATION PAR COTE BOOKMAKER                 ║")
print("╚════════════════════════════════════════════════════════════════════╝")
print()

print("📊 Scores de test (10 scores):")
for item in test_scores[:5]:
    print(f"   {item['score']:5s} → Cote: {item['odds']:5.2f}")
print("   ...")
print()

# ============================================================================
# TEST 1: Pondération par cotes uniquement
# ============================================================================
print("─" * 70)
print("🎯 TEST 1: PONDÉRATION PAR COTES UNIQUEMENT")
print("─" * 70)
print()

result_odds_only = process_scores_with_odds(test_scores)

print("Résultat (Top 5):")
for i, (score, prob) in enumerate(list(result_odds_only.items())[:5], 1):
    print(f"   {i}. {score:5s} → {prob:5.2f}%")
print()

# ============================================================================
# TEST 2: Algorithme complet SANS pondération par cotes
# ============================================================================
print("─" * 70)
print("🧮 TEST 2: ALGORITHME COMPLET (SANS pondération par cotes)")
print("─" * 70)
print()

result_without = calculate_probabilities(test_scores, diff_expected=2, use_odds_weighting=False)

print(f"Score le plus probable: {result_without['mostProbableScore']}")
print(f"Probabilité: {result_without['probabilities'][result_without['mostProbableScore']]:.2f}%")
print()
print("Top 5:")
sorted_probs = sorted(result_without['probabilities'].items(), key=lambda x: x[1], reverse=True)
for i, (score, prob) in enumerate(sorted_probs[:5], 1):
    print(f"   {i}. {score:5s} → {prob:5.2f}%")
print()

# ============================================================================
# TEST 3: Algorithme complet AVEC pondération par cotes
# ============================================================================
print("─" * 70)
print("🚀 TEST 3: ALGORITHME COMPLET (AVEC pondération par cotes)")
print("─" * 70)
print()

result_with = calculate_probabilities(test_scores, diff_expected=2, use_odds_weighting=True)

print(f"Score le plus probable: {result_with['mostProbableScore']}")
print(f"Probabilité: {result_with['probabilities'][result_with['mostProbableScore']]:.2f}%")
print()
print("Top 5:")
sorted_probs_with = sorted(result_with['probabilities'].items(), key=lambda x: x[1], reverse=True)
for i, (score, prob) in enumerate(sorted_probs_with[:5], 1):
    print(f"   {i}. {score:5s} → {prob:5.2f}%")
print()

# ============================================================================
# COMPARAISON
# ============================================================================
print("═" * 70)
print("📊 COMPARAISON DES RÉSULTATS")
print("═" * 70)
print()

print(f"{'Score':<10} | {'Sans pond.':<12} | {'Avec pond.':<12} | {'Différence':<12}")
print("─" * 70)

for score in sorted_probs[:5]:
    score_name = score[0]
    prob_without = result_without['probabilities'].get(score_name, 0)
    prob_with = result_with['probabilities'].get(score_name, 0)
    diff = prob_with - prob_without
    diff_str = f"{diff:+.2f}%"
    
    print(f"{score_name:<10} | {prob_without:>10.2f}% | {prob_with:>10.2f}% | {diff_str:>12}")

print()
print("═" * 70)
print("✅ Test terminé!")
print()
print("💡 Observations:")
print("   • La pondération par cotes ajuste les probabilités selon la confiance du bookmaker")
print("   • Les cotes très basses sont légèrement pénalisées (trop évidentes)")
print("   • Les cotes moyennes-hautes (value bets) sont favorisées")
print("   • Les cotes extrêmes sont réduites (peu probables)")
print()

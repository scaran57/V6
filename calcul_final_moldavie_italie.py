#!/usr/bin/env python3
"""
Calcul RÉEL des scores pour Moldavie vs Italie avec coefficients FIFA
"""

import sys
sys.path.insert(0, '/app/backend')

# Import du système complet
from score_predictor import calculate_probabilities
from learning import get_diff_expected
from tools.fifa_ranking_manager import get_team_coefficient
import json

# Cotes extraites de l'image (depuis les logs)
SCORES_WITH_ODDS = {
    "1-0": 84.0, "0-0": 25.0, "0-1": 7.7,
    "2-0": 100.0, "1-1": 27.0, "0-2": 4.65,
    "2-1": 100.0, "2-2": 100.0, "1-2": 14.5,
    "3-0": 100.0, "3-3": 100.0, "0-3": 4.1,
    "3-1": 100.0, "4-4": 100.0, "1-3": 13.0,
    "3-2": 100.0, "2-3": 84.0,
    "4-0": 100.0, "0-4": 4.7,
    "4-1": 100.0, "1-4": 15.0,
    "4-2": 100.0, "4-3": 100.0,
}

print("=" * 80)
print("🎯 CALCUL RÉEL - Moldavie vs Italie avec Coefficients FIFA")
print("=" * 80)
print()

# 1. Récupérer les coefficients FIFA
moldavie_coeff = get_team_coefficient("Moldavie")
italie_coeff = get_team_coefficient("Italie")

print(f"📊 Coefficients FIFA:")
print(f"   🟦 Moldavie: {moldavie_coeff:.3f}")
print(f"   🟩 Italie: {italie_coeff:.3f}")
print()

# 2. Diff expected
diff_expected = get_diff_expected()
print(f"📈 Différence attendue (learning): {diff_expected:.3f}")
print()

# 3. Calcul avec le système réel
print("⚙️ Calcul en cours avec score_predictor...")
print()

result = calculate_probabilities(
    scores=SCORES_WITH_ODDS,
    diff_expected=diff_expected,
    use_odds_weighting=False,
    home_team="Moldavie",
    away_team="Italie",
    league="WorldCupQualification",
    use_league_coeff=True
)

print("=" * 80)
print("✅ RÉSULTAT AVEC COEFFICIENTS FIFA")
print("=" * 80)
print()

most_probable = result.get('mostProbableScore', 'N/A')
confidence = result.get('confidence', 0) * 100
probabilities = result.get('probabilities', {})

print(f"🏆 Score le plus probable: {most_probable}")
print(f"💯 Probabilité: {probabilities.get(most_probable, 0):.2f}%")
print(f"🎯 Confiance globale: {confidence:.2f}%")
print()

print("=" * 80)
print("📊 TOP 10 DES SCORES")
print("=" * 80)
print()

# Trier par probabilité
sorted_scores = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)

for i, (score, prob) in enumerate(sorted_scores[:10], 1):
    bar = "█" * int(prob / 2)
    print(f"   {i:2d}. {score:5s} : {prob:6.2f}% {bar}")

print()

# Analyse 1-N-2
moldavie_wins = sum(prob for score, prob in probabilities.items() 
                    if int(score.split('-')[0]) > int(score.split('-')[1]))
draws = sum(prob for score, prob in probabilities.items() 
            if int(score.split('-')[0]) == int(score.split('-')[1]))
italie_wins = sum(prob for score, prob in probabilities.items() 
                  if int(score.split('-')[0]) < int(score.split('-')[1]))

print("=" * 80)
print("📊 DISTRIBUTION 1-N-2")
print("=" * 80)
print()
print(f"   🟦 Victoire Moldavie: {moldavie_wins:.2f}%")
print(f"   ⚪ Match nul: {draws:.2f}%")
print(f"   🟩 Victoire Italie: {italie_wins:.2f}%")
print()

if italie_wins > moldavie_wins:
    print(f"   ✅ L'Italie est favorite (écart: +{italie_wins - moldavie_wins:.2f}%)")
else:
    print(f"   ⚠️ Distribution anormale détectée")

print()
print("=" * 80)
print("📋 COMPARAISON")
print("=" * 80)
print()
print(f"   ❌ ANCIEN (Ligue1, coeffs 1.00/1.00):")
print(f"      → Score: 3-2 (20.02%)")
print(f"      → Moldavie wins: ~33%")
print(f"      → Draws: ~33%")
print(f"      → Italie wins: ~33%")
print()
print(f"   ✅ NOUVEAU (WorldCupQualification, coeffs {moldavie_coeff:.2f}/{italie_coeff:.2f}):")
print(f"      → Score: {most_probable} ({probabilities.get(most_probable, 0):.2f}%)")
print(f"      → Moldavie wins: {moldavie_wins:.2f}%")
print(f"      → Draws: {draws:.2f}%")
print(f"      → Italie wins: {italie_wins:.2f}%")
print()

# Changement significatif ?
if most_probable != "3-2":
    print(f"   🎯 LE SCORE PRÉDIT A CHANGÉ !")
    print(f"   → De 3-2 (victoire Moldavie) à {most_probable}")
else:
    old_prob = 20.02
    new_prob = probabilities.get(most_probable, 0)
    print(f"   ℹ️ Score identique mais probabilité ajustée:")
    print(f"   → Variation: {new_prob - old_prob:+.2f}%")

print()
print("=" * 80)
print("✅ CALCUL TERMINÉ")
print("=" * 80)

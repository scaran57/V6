#!/usr/bin/env python3
"""
Script pour recalculer les scores corrects de Moldavie vs Italie
en utilisant directement score_predictor avec les bons coefficients
"""

import sys
sys.path.insert(0, '/app/backend')

from tools.fifa_ranking_manager import get_team_rank, get_team_coefficient
import json

# Cotes extraites de l'image originale
SCORES_DICT = {
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

def main():
    print("=" * 80)
    print("🔄 RECALCUL DES SCORES - Moldavie vs Italie")
    print("=" * 80)
    print()
    
    # Récupérer les coefficients FIFA
    print("📊 Récupération des coefficients FIFA...")
    
    moldavie_coeff = get_team_coefficient("Moldavie")
    moldavie_rank = get_team_rank("Moldavie")
    
    italie_coeff = get_team_coefficient("Italie")
    italie_rank = get_team_rank("Italie")
    
    print(f"   🟦 Moldavie: Rank #{moldavie_rank} → Coefficient {moldavie_coeff:.3f}")
    print(f"   🟩 Italie: Rank #{italie_rank} → Coefficient {italie_coeff:.3f}")
    
    if moldavie_rank and italie_rank:
        ratio = italie_coeff / moldavie_coeff
        print(f"   📈 Ratio de force: {ratio:.3f}x (en faveur de l'Italie)")
    
    print()
    print("=" * 80)
    print("📈 CALCUL DES PROBABILITÉS")
    print("=" * 80)
    print()
    
    # Import du calculateur
    from score_predictor import (
        calculate_poisson_weights,
        apply_league_coefficients,
        calculate_adjusted_probabilities,
        apply_draw_correction,
        calculate_confidence
    )
    from learning import get_diff_expected
    
    # 1. Calculer diff_expected
    diff_expected = get_diff_expected()
    print(f"1️⃣ Différence attendue (learning): {diff_expected:.3f}")
    
    # 2. Poids Poisson
    poisson_weights = calculate_poisson_weights(list(SCORES_DICT.keys()), diff_expected)
    print(f"2️⃣ Poids Poisson calculés pour {len(poisson_weights)} scores")
    
    # 3. Appliquer les coefficients de ligue (FIFA)
    print(f"3️⃣ Application des coefficients FIFA:")
    print(f"   • Moldavie: {moldavie_coeff:.3f}")
    print(f"   • Italie: {italie_coeff:.3f}")
    
    league_weights = apply_league_coefficients(
        scores=list(SCORES_DICT.keys()),
        home_coeff=moldavie_coeff,
        away_coeff=italie_coeff
    )
    
    # 4. Probabilités ajustées
    adjusted_probs = calculate_adjusted_probabilities(
        scores=list(SCORES_DICT.keys()),
        poisson_weights=poisson_weights,
        league_weights=league_weights
    )
    
    # 5. Correction des nuls
    final_probs = apply_draw_correction(adjusted_probs)
    
    # 6. Confiance
    confidence = calculate_confidence(final_probs)
    
    # 7. Score le plus probable
    most_probable = max(final_probs.items(), key=lambda x: x[1])
    
    print()
    print("=" * 80)
    print("✅ RÉSULTATS AVEC COEFFICIENTS FIFA")
    print("=" * 80)
    print()
    print(f"🏆 Score le plus probable: {most_probable[0]} ({most_probable[1]:.2f}%)")
    print(f"💯 Confiance globale: {confidence * 100:.2f}%")
    print()
    
    print("📊 TOP 10 DES SCORES LES PLUS PROBABLES:")
    print("-" * 80)
    
    # Trier les scores par probabilité décroissante
    sorted_scores = sorted(final_probs.items(), key=lambda x: x[1], reverse=True)
    
    for i, (score, prob) in enumerate(sorted_scores[:10], 1):
        bar = "█" * int(prob / 2)  # Barre visuelle
        print(f"   {i:2d}. {score:5s} : {prob:6.2f}% {bar}")
    
    print()
    print("=" * 80)
    print("📋 COMPARAISON")
    print("=" * 80)
    print()
    
    print(f"   ❌ ANCIEN (Ligue1 - Coeffs 1.00/1.00): 3-2 (20.02%)")
    print(f"   ✅ NOUVEAU (WorldCupQualification - FIFA): {most_probable[0]} ({most_probable[1]:.2f}%)")
    print()
    
    if most_probable[0] != "3-2":
        print(f"   ⚠️ LE SCORE PRÉDIT A CHANGÉ avec les bons coefficients FIFA !")
        print(f"   → Cela démontre l'importance d'utiliser les bons coefficients.")
    else:
        old_prob = 20.02
        new_prob = most_probable[1]
        diff = new_prob - old_prob
        print(f"   ℹ️ Le score prédit reste 3-2, mais la probabilité a changé:")
        print(f"   → Variation: {diff:+.2f} points de pourcentage")
    
    print()
    print("=" * 80)
    print("🎯 ANALYSE")
    print("=" * 80)
    print()
    print(f"Avec un ratio de force de {ratio:.2f}x en faveur de l'Italie:")
    print(f"   • Les victoires de l'Italie (0-1, 0-2, 0-3, etc.) sont plus probables")
    print(f"   • Les victoires de la Moldavie (1-0, 2-0, etc.) sont moins probables")
    print(f"   • Les matchs nuls restent possibles mais ajustés")
    print()
    
    # Vérifier la distribution
    moldavie_wins = sum(prob for score, prob in final_probs.items() 
                        if int(score.split('-')[0]) > int(score.split('-')[1]))
    draws = sum(prob for score, prob in final_probs.items() 
                if int(score.split('-')[0]) == int(score.split('-')[1]))
    italie_wins = sum(prob for score, prob in final_probs.items() 
                      if int(score.split('-')[0]) < int(score.split('-')[1]))
    
    print("📊 DISTRIBUTION 1-N-2:")
    print(f"   • Victoire Moldavie: {moldavie_wins:.2f}%")
    print(f"   • Match nul: {draws:.2f}%")
    print(f"   • Victoire Italie: {italie_wins:.2f}%")
    print()
    
    print("=" * 80)
    print("✅ RECALCUL TERMINÉ")
    print("=" * 80)

if __name__ == "__main__":
    main()

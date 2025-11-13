#!/usr/bin/env python3
"""
Script pour recalculer les scores corrects de Moldavie vs Italie
avec les coefficients FIFA appropriés
"""

import sys
sys.path.insert(0, '/app/backend')

from tools.fifa_ranking_manager import get_team_rank, calculate_strength_coefficient
from score_predictor import calculate_probabilities_v2
import json

# Cotes extraites de l'image originale (depuis les logs)
ODDS_DATA = [
    {"score": "1-0", "odds": 84.0},
    {"score": "0-0", "odds": 25.0},
    {"score": "0-1", "odds": 7.7},
    {"score": "2-0", "odds": 100.0},
    {"score": "1-1", "odds": 27.0},
    {"score": "0-2", "odds": 4.65},
    {"score": "2-1", "odds": 100.0},
    {"score": "2-2", "odds": 100.0},
    {"score": "1-2", "odds": 14.5},
    {"score": "3-0", "odds": 100.0},
    {"score": "3-3", "odds": 100.0},
    {"score": "0-3", "odds": 4.1},
    {"score": "3-1", "odds": 100.0},
    {"score": "4-4", "odds": 100.0},
    {"score": "1-3", "odds": 13.0},
    {"score": "3-2", "odds": 100.0},
    {"score": "2-3", "odds": 84.0},
    {"score": "4-0", "odds": 100.0},
    {"score": "0-4", "odds": 4.7},
    {"score": "4-1", "odds": 100.0},
    {"score": "1-4", "odds": 15.0},
    {"score": "4-2", "odds": 100.0},
    {"score": "4-3", "odds": 100.0},
]

def main():
    print("=" * 80)
    print("🔄 RECALCUL DES SCORES - Moldavie vs Italie")
    print("=" * 80)
    print()
    
    # Récupérer les coefficients FIFA
    print("📊 Récupération des coefficients FIFA...")
    
    try:
        # Moldavie
        moldavie_rank = get_team_rank("Moldavie")
        moldavie_coeff = calculate_strength_coefficient(moldavie_rank) if moldavie_rank else 1.0
        
        # Italie
        italie_rank = get_team_rank("Italie")
        italie_coeff = calculate_strength_coefficient(italie_rank) if italie_rank else 1.0
        
        print(f"   🟦 Moldavie: Rank {moldavie_rank} → Coefficient {moldavie_coeff:.2f}")
        print(f"   🟩 Italie: Rank {italie_rank} → Coefficient {italie_coeff:.2f}")
        
        if moldavie_rank and italie_rank:
            ratio = italie_coeff / moldavie_coeff
            print(f"   📈 Ratio de force: {ratio:.2f} (en faveur de l'Italie)")
        
    except Exception as e:
        print(f"   ⚠️ Erreur FIFA: {e}")
        print(f"   ℹ️ Utilisation de coefficients par défaut")
        moldavie_coeff = 0.85  # Pays plus faible
        italie_coeff = 1.30    # Top équipe
    
    print()
    print("=" * 80)
    print("📈 CALCUL DES PROBABILITÉS AVEC COEFFICIENTS FIFA")
    print("=" * 80)
    print()
    
    # Calculer les probabilités avec les coefficients FIFA
    try:
        result = calculate_probabilities_v2(
            odds_data=ODDS_DATA,
            home_team="Moldavie",
            away_team="Italie",
            league="WorldCupQualification",
            home_coeff=moldavie_coeff,
            away_coeff=italie_coeff
        )
        
        print(f"✅ Calcul réussi !")
        print()
        print(f"🏆 Score le plus probable: {result['most_probable']} ({result['probabilities'].get(result['most_probable'], 0):.2f}%)")
        print(f"💯 Confiance globale: {result['confidence'] * 100:.2f}%")
        print()
        
        print("📊 TOP 10 DES SCORES LES PLUS PROBABLES:")
        print("-" * 80)
        
        # Trier les scores par probabilité décroissante
        sorted_scores = sorted(
            result['probabilities'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for i, (score, prob) in enumerate(sorted_scores[:10], 1):
            bar = "█" * int(prob / 2)  # Barre visuelle
            print(f"   {i:2d}. {score:5s} : {prob:6.2f}% {bar}")
        
        print()
        print("=" * 80)
        print("📋 COMPARAISON AVEC L'ANCIENNE PRÉDICTION")
        print("=" * 80)
        print()
        
        old_prediction = "3-2 (20.02%)"
        new_prediction = f"{result['most_probable']} ({result['probabilities'].get(result['most_probable'], 0):.2f}%)"
        
        print(f"   ❌ ANCIEN (Ligue1 - coefficients neutres): {old_prediction}")
        print(f"   ✅ NOUVEAU (WorldCupQualification - FIFA): {new_prediction}")
        print()
        
        if result['most_probable'] != "3-2":
            print(f"   ⚠️ Le score prédit a CHANGÉ avec les bons coefficients !")
        else:
            print(f"   ℹ️ Le score prédit est le même, mais les probabilités ont changé.")
        
        print()
        print("=" * 80)
        print("💾 DONNÉES COMPLÈTES (JSON)")
        print("=" * 80)
        print()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Erreur lors du calcul: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("✅ RECALCUL TERMINÉ")
    print("=" * 80)

if __name__ == "__main__":
    main()

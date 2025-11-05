#!/usr/bin/env python3
"""
Script pour générer et afficher le rapport de suivi automatique du système.
Usage: python generate_report.py
"""

import requests
import sys
import json

API_URL = "http://localhost:8001/api/system/report"

def display_report():
    """Génère et affiche le rapport de suivi"""
    try:
        print("🔄 Génération du rapport de suivi...\n")
        
        response = requests.get(API_URL, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Afficher le rapport textuel formaté
            print(data.get('report_text', 'Aucun rapport disponible'))
            
            # Afficher les détails JSON si demandé
            if '--json' in sys.argv:
                print("\n📄 Données JSON complètes:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Statistiques détaillées
            if '--stats' in sys.argv:
                stats = data.get('statistics', {})
                print("\n📈 STATISTIQUES DÉTAILLÉES:")
                print(f"   Total de matchs analysés: {stats.get('total_matches', 0)}")
                print(f"   Confiance moyenne: {stats.get('average_confidence', 0) * 100:.2f}%")
                print(f"   Nombre de bookmakers différents: {stats.get('bookmakers_count', 0)}")
                
                bookmakers = stats.get('bookmakers_distribution', {})
                if bookmakers:
                    print(f"\n   Distribution par bookmaker:")
                    for bm, count in sorted(bookmakers.items(), key=lambda x: x[1], reverse=True):
                        percentage = (count / stats.get('total_matches', 1)) * 100
                        print(f"      • {bm}: {count} match(s) ({percentage:.1f}%)")
            
            # Liste des matchs récents
            if '--recent' in sys.argv:
                recent = data.get('recent_matches', [])
                if recent:
                    print(f"\n📋 MATCHS RÉCENTS ({len(recent)}):")
                    for i, match in enumerate(reversed(recent), 1):
                        print(f"\n   {i}. {match.get('match_name', 'N/A')}")
                        print(f"      Match ID: {match.get('match_id', 'N/A')}")
                        print(f"      Bookmaker: {match.get('bookmaker', 'N/A')}")
                        print(f"      Score prédit: {match.get('top_score', 'N/A')}")
                        print(f"      Confiance: {match.get('confidence', 0) * 100:.1f}%")
                        print(f"      Analysé le: {match.get('analyzed_at', 'N/A')[:19]}")
            
            return 0
            
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            print(response.text)
            return 1
            
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter au serveur backend")
        print("   Assurez-vous que le serveur est démarré sur http://localhost:8001")
        return 1
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return 1

if __name__ == "__main__":
    # Afficher l'aide si demandé
    if '--help' in sys.argv or '-h' in sys.argv:
        print("""
Usage: python generate_report.py [options]

Options:
  --json      Affiche les données JSON complètes
  --stats     Affiche les statistiques détaillées
  --recent    Affiche la liste complète des matchs récents
  --help, -h  Affiche cette aide

Exemples:
  python generate_report.py                    # Rapport de base
  python generate_report.py --stats            # Avec statistiques détaillées
  python generate_report.py --stats --recent   # Rapport complet
  python generate_report.py --json             # Export JSON
        """)
        sys.exit(0)
    
    sys.exit(display_report())

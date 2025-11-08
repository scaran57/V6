#!/usr/bin/env python3
"""
UFA Check Balance v1.0
Module de vérification d'équilibre et de cohérence des ligues

Surveille en temps réel :
- Ratio de matchs "Unknown"
- Diversité des scores
- Moyenne de buts par ligue
- Cohérence des prédictions
"""

import json
import os
import statistics
from collections import defaultdict
from datetime import datetime

UFA_FILE = "/app/data/real_scores.jsonl"
REPORT_FILE = "/app/data/ufa_balance_report.json"

THRESHOLDS = {
    "unknown_max_ratio": 0.35,    # max 35% Unknown
    "avg_goals_min": 2.0,         # Minimum attendu
    "avg_goals_max": 3.3,         # Maximum attendu
    "score_repeat_limit": 0.25,   # Si >25% même score → alerte
    "min_matches_per_league": 3   # Minimum de matchs pour analyse fiable
}

def analyze_balance():
    """
    Analyse l'équilibre et la cohérence des données UFA.
    
    Returns:
        dict: Rapport d'analyse complet
    """
    if not os.path.exists(UFA_FILE):
        print("❌ Aucun fichier de scores UFA trouvé.")
        return {
            "status": "error",
            "message": "Fichier UFA introuvable"
        }

    # Charger les données
    with open(UFA_FILE, "r", encoding="utf-8") as f:
        matches = [json.loads(line) for line in f]

    total = len(matches)
    
    if total == 0:
        print("⚠️ Aucun match trouvé dans le fichier UFA.")
        return {
            "status": "warning",
            "message": "Aucune donnée disponible"
        }

    # Structures de données
    leagues = defaultdict(list)
    scores = defaultdict(int)
    results = defaultdict(int)  # 1 (domicile), X (nul), 2 (extérieur)
    
    # Analyse des matchs
    for m in matches:
        lg = m.get("league", "Unknown")
        hg = m.get("home_goals")
        ag = m.get("away_goals")
        
        if hg is None or ag is None:
            continue
        
        total_goals = hg + ag
        leagues[lg].append({
            "total_goals": total_goals,
            "home_goals": hg,
            "away_goals": ag
        })
        
        score = f"{hg}-{ag}"
        scores[score] += 1
        
        # Résultat 1X2
        if hg > ag:
            results["1"] += 1
        elif hg == ag:
            results["X"] += 1
        else:
            results["2"] += 1

    print("=" * 70)
    print(f"📊 ANALYSE D'ÉQUILIBRE UFA - {total} matchs")
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # === 1. Vérification du ratio Unknown ===
    print("┌" + "─" * 68 + "┐")
    print("│ 1️⃣  RATIO DE MATCHS UNKNOWN                                      │")
    print("├" + "─" * 68 + "┤")
    
    unknown_count = len(leagues.get("Unknown", []))
    unknown_ratio = unknown_count / max(total, 1)
    
    print(f"│   Total Unknown: {unknown_count}/{total} matchs                                │")
    print(f"│   Ratio: {unknown_ratio*100:.1f}%                                              │")
    
    if unknown_ratio > THRESHOLDS["unknown_max_ratio"]:
        print("│   ⚠️  Trop de matchs Unknown !                                   │")
        print("│   → Améliorer la table de détection ou l'OCR                    │")
    else:
        print("│   ✅ Ratio Unknown acceptable                                    │")
    
    print("└" + "─" * 68 + "┘")
    print()

    # === 2. Diversité des scores ===
    print("┌" + "─" * 68 + "┐")
    print("│ 2️⃣  DIVERSITÉ DES SCORES                                         │")
    print("├" + "─" * 68 + "┤")
    
    if scores:
        top_score, freq = max(scores.items(), key=lambda x: x[1])
        ratio_repeat = freq / max(total, 1)
        
        print(f"│   Score le plus fréquent: {top_score} ({freq} fois, {ratio_repeat*100:.1f}%)        │")
        
        if ratio_repeat > THRESHOLDS["score_repeat_limit"]:
            print("│   ⚠️  Score trop fréquent - manque de diversité !               │")
        else:
            print("│   ✅ Diversité des scores acceptable                            │")
        
        # Top 5 des scores
        print("│                                                                  │")
        print("│   Top 5 des scores:                                             │")
        for score, count in sorted(scores.items(), key=lambda x: -x[1])[:5]:
            pct = count / total * 100
            print(f"│      {score:6s} : {count:3d} fois ({pct:5.1f}%)                               │")
    
    print("└" + "─" * 68 + "┘")
    print()

    # === 3. Distribution 1X2 ===
    print("┌" + "─" * 68 + "┐")
    print("│ 3️⃣  DISTRIBUTION DES RÉSULTATS (1X2)                             │")
    print("├" + "─" * 68 + "┤")
    
    total_results = sum(results.values())
    if total_results > 0:
        r1 = results["1"] / total_results * 100
        rx = results["X"] / total_results * 100
        r2 = results["2"] / total_results * 100
        
        print(f"│   Victoire domicile (1): {results['1']:3d} matchs ({r1:5.1f}%)                │")
        print(f"│   Match nul (X):         {results['X']:3d} matchs ({rx:5.1f}%)                │")
        print(f"│   Victoire extérieur (2): {results['2']:3d} matchs ({r2:5.1f}%)               │")
        
        # Vérification équilibre (attendu ~45% / 25% / 30%)
        if r1 < 35 or r1 > 55:
            print("│   ⚠️  Distribution domicile anormale                             │")
        elif rx < 15 or rx > 35:
            print("│   ⚠️  Distribution nuls anormale                                 │")
        else:
            print("│   ✅ Distribution 1X2 cohérente                                  │")
    
    print("└" + "─" * 68 + "┘")
    print()

    # === 4. Moyenne par ligue ===
    print("┌" + "─" * 68 + "┐")
    print("│ 4️⃣  MOYENNE DE BUTS PAR LIGUE                                    │")
    print("├" + "─" * 68 + "┤")
    
    league_stats = {}
    
    for lg, matches_data in sorted(leagues.items(), key=lambda x: -len(x[1])):
        if not matches_data:
            continue
        
        total_goals_list = [m["total_goals"] for m in matches_data]
        avg_goals = statistics.mean(total_goals_list)
        std_dev = statistics.stdev(total_goals_list) if len(total_goals_list) > 1 else 0
        
        num_matches = len(matches_data)
        
        # Déterminer le statut
        status = "✅"
        issue = None
        
        if num_matches < THRESHOLDS["min_matches_per_league"]:
            status = "ℹ️ "
            issue = "Peu de données"
        elif avg_goals < THRESHOLDS["avg_goals_min"]:
            status = "⚠️ "
            issue = "Trop bas"
        elif avg_goals > THRESHOLDS["avg_goals_max"]:
            status = "⚠️ "
            issue = "Trop élevé"
        
        print(f"│ {status} {lg:20s} → {avg_goals:4.2f} buts (σ={std_dev:4.2f}, n={num_matches:2d})    │")
        if issue:
            print(f"│    └─ {issue:56s} │")
        
        league_stats[lg] = {
            "avg_goals": avg_goals,
            "std_dev": std_dev,
            "matches": num_matches,
            "status": status.strip()
        }
    
    print("└" + "─" * 68 + "┘")
    print()

    # === Rapport final ===
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_matches": total,
        "unknown_ratio": unknown_ratio,
        "top_score": {
            "score": top_score if scores else None,
            "frequency": freq / total if scores else 0
        },
        "results_distribution": {
            "home": results["1"],
            "draw": results["X"],
            "away": results["2"]
        },
        "league_stats": league_stats,
        "alerts": []
    }
    
    # Générer les alertes
    if unknown_ratio > THRESHOLDS["unknown_max_ratio"]:
        report["alerts"].append(f"Ratio Unknown trop élevé: {unknown_ratio*100:.1f}%")
    
    if scores and (freq / total) > THRESHOLDS["score_repeat_limit"]:
        report["alerts"].append(f"Score {top_score} trop fréquent: {freq/total*100:.1f}%")
    
    # Sauvegarder le rapport
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("=" * 70)
    if report["alerts"]:
        print(f"⚠️  {len(report['alerts'])} alerte(s) détectée(s)")
        for alert in report["alerts"]:
            print(f"   • {alert}")
    else:
        print("✅ Aucune alerte - Système équilibré")
    
    print()
    print(f"📄 Rapport sauvegardé: {REPORT_FILE}")
    print("=" * 70)
    
    return report


if __name__ == "__main__":
    analyze_balance()

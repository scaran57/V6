#!/usr/bin/env python3
# scripts/rebuild_from_learning_log.py
"""
Script de reconstruction de l'historique depuis le log append-only
Rejoue tous les événements d'apprentissage pour recréer teams_data.json et learning_meta.json
"""
import json
import os
import sys

# Ajouter le path parent pour importer le module
sys.path.insert(0, '/app')

from modules.local_learning_safe import (
    LEARNING_LOG, 
    TEAMS_FILE, 
    META_FILE, 
    SCHEMA_VERSION, 
    _atomic_write_json
)

def rebuild(keep_last=20):
    """
    Reconstruit teams_data.json et learning_meta.json depuis le log
    
    Args:
        keep_last: Nombre de matchs à conserver par équipe (défaut: 20)
    """
    if not os.path.exists(LEARNING_LOG):
        print(f"❌ Aucun learning log trouvé : {LEARNING_LOG}")
        return False

    teams = {}
    meta = {"diffExpected": 2.0, "schema_version": SCHEMA_VERSION}

    # Lire tous les événements dans l'ordre chronologique et les rejouer
    with open(LEARNING_LOG, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"📖 Lecture de {len(lines)} événements d'apprentissage...")
    
    processed = 0
    for idx, line in enumerate(lines, 1):
        try:
            e = json.loads(line)
        except:
            print(f"⚠️  Ligne {idx} ignorée (JSON invalide)")
            continue
        
        real = e.get("real")
        home = e.get("home")
        away = e.get("away")
        
        if not all([real, home, away]):
            print(f"⚠️  Ligne {idx} ignorée (données incomplètes)")
            continue
        
        # Mettre à jour la liste des équipes
        try:
            rh, ra = map(int, real.split("-"))
        except:
            print(f"⚠️  Ligne {idx} ignorée (score invalide: {real})")
            continue
        
        # Équipe domicile
        teams.setdefault(home, []).append([rh, ra])
        teams[home] = teams[home][-keep_last:]
        
        # Équipe extérieur
        teams.setdefault(away, []).append([ra, rh])
        teams[away] = teams[away][-keep_last:]

        # Mettre à jour diffExpected en rejouant la règle 60/40
        old = meta.get("diffExpected", 2.0)
        try:
            diff_real = abs(ra - rh)
            new_diff = (old * 3 + diff_real * 2) / 5.0
            meta["diffExpected"] = round(new_diff, 3)
        except:
            pass
        
        processed += 1

    # Sauvegarder atomiquement
    _atomic_write_json(TEAMS_FILE, teams)
    _atomic_write_json(META_FILE, meta)
    
    print("\n" + "="*60)
    print("✅ Rebuild terminé avec succès !")
    print("="*60)
    print(f"📊 Événements traités: {processed}/{len(lines)}")
    print(f"👥 Équipes reconstituées: {len(teams)}")
    print(f"📈 diffExpected final: {meta.get('diffExpected')}")
    print(f"📁 Fichiers mis à jour:")
    print(f"   - {TEAMS_FILE}")
    print(f"   - {META_FILE}")
    print("="*60)
    
    # Afficher les équipes
    if teams:
        print("\n🏆 Équipes avec leurs historiques:")
        for team, matches in sorted(teams.items()):
            avg_for = sum(m[0] for m in matches) / len(matches) if matches else 0
            avg_against = sum(m[1] for m in matches) / len(matches) if matches else 0
            print(f"   • {team}: {len(matches)} matchs (avg: {avg_for:.1f} marqués, {avg_against:.1f} encaissés)")
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reconstruit l'historique depuis le log d'apprentissage")
    parser.add_argument("--keep-last", type=int, default=20, 
                       help="Nombre de matchs à conserver par équipe (défaut: 20)")
    args = parser.parse_args()
    
    success = rebuild(keep_last=args.keep_last)
    sys.exit(0 if success else 1)

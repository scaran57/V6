#!/usr/bin/env python3
"""
Script de vérification du système d'apprentissage sécurisé
Usage: python3 /app/scripts/check_learning_system.py
"""
import sys
sys.path.insert(0, '/app')

from modules.local_learning_safe import (
    check_schema_compatibility, 
    load_meta, 
    load_teams, 
    get_learning_stats,
    LEARNING_LOG,
    TEAMS_FILE,
    META_FILE
)
import os
import json

def print_header(title):
    """Affiche un en-tête formaté"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def check_system():
    """Vérifie l'état complet du système d'apprentissage"""
    
    print_header("🧠 VÉRIFICATION DU SYSTÈME D'APPRENTISSAGE")
    
    # 1. Compatibilité du schéma
    print("\n📋 Compatibilité:")
    compatible = check_schema_compatibility()
    status = "✅" if compatible else "❌"
    print(f"   {status} Schema compatible: {compatible}")
    
    if not compatible:
        print("   ⚠️  ATTENTION: Schéma incompatible!")
        return False
    
    # 2. Métadonnées
    print("\n📈 Métadonnées:")
    meta = load_meta()
    print(f"   • diffExpected: {meta.get('diffExpected')}")
    print(f"   • Schema version: {meta.get('schema_version')}")
    
    # 3. Équipes
    print("\n👥 Équipes enregistrées:")
    teams = load_teams()
    if not teams:
        print("   ⚠️  Aucune équipe enregistrée")
    else:
        for team, matches in sorted(teams.items()):
            avg_for = sum(m[0] for m in matches) / len(matches) if matches else 0
            avg_against = sum(m[1] for m in matches) / len(matches) if matches else 0
            print(f"   • {team}:")
            print(f"      - {len(matches)} matchs")
            print(f"      - Moyenne: {avg_for:.1f} marqués, {avg_against:.1f} encaissés")
    
    # 4. Log d'apprentissage
    print("\n📝 Log d'apprentissage:")
    if os.path.exists(LEARNING_LOG):
        log_size = os.path.getsize(LEARNING_LOG)
        with open(LEARNING_LOG, 'r') as f:
            num_events = len(f.readlines())
        print(f"   ✅ Présent: {LEARNING_LOG}")
        print(f"   • Taille: {log_size:,} octets ({log_size/1024:.2f} KB)")
        print(f"   • Événements: {num_events}")
        
        # Afficher les 3 derniers événements
        if num_events > 0:
            print("\n   📊 Derniers événements:")
            with open(LEARNING_LOG, 'r') as f:
                lines = f.readlines()
            for i, line in enumerate(lines[-3:], 1):
                try:
                    event = json.loads(line)
                    print(f"      {i}. {event.get('iso', 'N/A')[:19]}: "
                          f"{event.get('home', 'N/A')} vs {event.get('away', 'N/A')} "
                          f"(réel: {event.get('real', 'N/A')})")
                except:
                    pass
    else:
        print(f"   ❌ MANQUANT: {LEARNING_LOG}")
    
    # 5. Statistiques générales
    print("\n📊 Statistiques générales:")
    stats = get_learning_stats()
    print(f"   • Total événements: {stats.get('total_learning_events', 0)}")
    print(f"   • Équipes: {stats.get('teams_count', 0)}")
    print(f"   • diffExpected: {stats.get('diffExpected', 'N/A')}")
    
    # 6. Fichiers
    print("\n📁 Fichiers:")
    files = [
        (LEARNING_LOG, "Log d'apprentissage"),
        (TEAMS_FILE, "Données équipes"),
        (META_FILE, "Métadonnées")
    ]
    
    all_exist = True
    for filepath, description in files:
        exists = os.path.exists(filepath)
        status = "✅" if exists else "❌"
        size = f"({os.path.getsize(filepath):,} octets)" if exists else ""
        print(f"   {status} {description}: {filepath} {size}")
        if not exists:
            all_exist = False
    
    # 7. Résumé final
    print_header("✅ RÉSUMÉ")
    
    if all_exist and compatible and num_events > 0:
        print("\n🎉 Système d'apprentissage OPÉRATIONNEL")
        print(f"   • {num_events} événements enregistrés")
        print(f"   • {len(teams)} équipes avec historique")
        print(f"   • diffExpected = {meta.get('diffExpected')}")
        print("\n💡 Tout est prêt pour l'apprentissage!")
        return True
    else:
        print("\n⚠️  Système d'apprentissage INCOMPLET")
        if not all_exist:
            print("   • Fichiers manquants détectés")
        if not compatible:
            print("   • Schéma incompatible")
        if num_events == 0:
            print("   • Aucun événement d'apprentissage")
        print("\n🔧 Actions recommandées:")
        print("   1. Vérifier les fichiers manquants")
        print("   2. Exécuter la migration si nécessaire:")
        print("      python3 /app/scripts/migrate_existing_data.py")
        print("   3. Ou reconstruire depuis le log:")
        print("      python3 /app/scripts/rebuild_from_learning_log.py")
        return False

if __name__ == "__main__":
    try:
        success = check_system()
        print("\n" + "=" * 60 + "\n")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Erreur lors de la vérification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

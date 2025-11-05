#!/usr/bin/env python3
"""
Script de migration des données existantes vers le nouveau système avec log
Crée les événements d'apprentissage depuis teams_data.json existant
"""
import json
import sys
import os

sys.path.insert(0, '/app')

from modules.local_learning_safe import record_learning_event, load_teams, load_meta

def migrate_from_existing():
    """Migre les données existantes vers le système de log"""
    
    print("🔄 Migration des données existantes vers le système de log...\n")
    
    # Charger les données existantes
    try:
        teams = load_teams()
        meta = load_meta()
    except Exception as e:
        print(f"❌ Erreur lors du chargement des données: {e}")
        return False
    
    print(f"📊 Données trouvées:")
    print(f"   - {len(teams)} équipes")
    print(f"   - diffExpected actuel: {meta.get('diffExpected')}")
    
    if not teams:
        print("\n⚠️  Aucune donnée d'équipe à migrer")
        return True
    
    # Créer des événements d'apprentissage pour chaque match
    # Note: On simule les événements puisqu'on n'a que les résultats réels
    event_count = 0
    
    for team_name, matches in teams.items():
        print(f"\n📋 Migration de {team_name} ({len(matches)} matchs)...")
        
        for idx, match in enumerate(matches):
            # Format: [goals_for, goals_against]
            goals_for, goals_against = match
            
            # Créer un match_id simulé
            match_id = f"migrated_{team_name}_{idx}"
            
            # Pour la migration, on considère l'équipe comme domicile
            # et on simule un adversaire générique
            real_score = f"{goals_for}-{goals_against}"
            predicted_score = real_score  # On ne connait pas la prédiction originale
            
            # Enregistrer l'événement
            success, result = record_learning_event(
                match_id=match_id,
                home_team=team_name,
                away_team="Unknown",  # Adversaire inconnu
                predicted=predicted_score,
                real=real_score,
                agent_id="migration_script"
            )
            
            if success:
                event_count += 1
            else:
                print(f"   ⚠️  Erreur pour match {idx}: {result}")
    
    print(f"\n✅ Migration terminée !")
    print(f"📊 {event_count} événements créés dans le log")
    
    return True

if __name__ == "__main__":
    success = migrate_from_existing()
    sys.exit(0 if success else 1)

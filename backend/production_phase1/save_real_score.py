"""
Production Phase 1 - Enregistrement des scores réels
Enregistre simplement les scores réels sans apprentissage.
L'apprentissage sera géré séparément par le module UFA.
"""
import json
from datetime import datetime
from pathlib import Path

DATA_PATH = Path("/app/data/real_scores.jsonl")

def save_real_score(match_id, league, home_team, away_team, home_goals, away_goals):
    """
    Enregistre un score réel dans le fichier de données.
    Aucun apprentissage n'est effectué ici.
    
    Args:
        match_id: ID du match
        league: Nom de la ligue
        home_team: Équipe domicile
        away_team: Équipe extérieure
        home_goals: Buts domicile
        away_goals: Buts extérieur
    """
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "match_id": match_id,
        "league": league,
        "home_team": home_team,
        "away_team": away_team,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "source": "production_phase1"
    }
    
    with open(DATA_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print(f"[Phase1] Score réel enregistré pour {home_team} - {away_team}: {home_goals}-{away_goals}")
    return entry

def get_real_scores(limit=None):
    """
    Récupère les scores réels enregistrés.
    
    Args:
        limit: Nombre maximum de scores à retourner
        
    Returns:
        Liste des scores réels
    """
    if not DATA_PATH.exists():
        return []
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        scores = [json.loads(line) for line in f]
    
    if limit:
        scores = scores[-limit:]
    
    return scores

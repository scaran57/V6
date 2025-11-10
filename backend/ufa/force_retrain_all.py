#!/usr/bin/env python3
# /app/backend/ufa/force_retrain_all.py
"""
Script de réentraînement complet du modèle UFA.

Charge toutes les données disponibles, corrige les incohérences,
applique les coefficients appropriés, et réentraîne le modèle.

Usage:
    python3 /app/backend/ufa/force_retrain_all.py
"""
import os
import json
import time
import sys
from datetime import datetime
from pathlib import Path

# Ajouter le backend au path
sys.path.insert(0, '/app/backend')

from fuzzywuzzy import process
from league_coeff import get_coeffs_for_match

BASE_PATH = "/app/data"
LOG_PATH = "/app/logs/train_report.log"
MODEL_PATH = "/app/models/ufa_model_v2.pkl"

# Créer les dossiers nécessaires
Path("/app/logs").mkdir(parents=True, exist_ok=True)
Path("/app/models").mkdir(parents=True, exist_ok=True)

def fuzzy_match_team(team_name, known_teams):
    """Corrige les noms d'équipes avec fuzzy matching."""
    if not team_name or not known_teams:
        return team_name
    match, score = process.extractOne(team_name, known_teams)
    return match if score > 75 else team_name

def detect_league_auto(league_text):
    """Détecte et normalise le nom de la ligue."""
    if not league_text:
        return "Unknown"
    
    league_lower = league_text.lower()
    
    # Mapping des ligues
    league_map = {
        "ligue 1": "Ligue1",
        "ligue1": "Ligue1",
        "ligue 2": "Ligue2",
        "ligue2": "Ligue2",
        "la liga": "LaLiga",
        "laliga": "LaLiga",
        "premier league": "PremierLeague",
        "premierleague": "PremierLeague",
        "epl": "PremierLeague",
        "serie a": "SerieA",
        "seriea": "SerieA",
        "bundesliga": "Bundesliga",
        "champions league": "ChampionsLeague",
        "uefa": "ChampionsLeague",
        "europa league": "EuropaLeague",
        "primeira liga": "PrimeiraLiga",
        "liga portugal": "PrimeiraLiga",
        "eredivisie": "Eredivisie",
        "world cup": "WorldCup",
        "worldcup": "WorldCup",
        "qualification": "WorldCupQualification"
    }
    
    for key, value in league_map.items():
        if key in league_lower:
            return value
    
    return league_text

def load_jsonl(path):
    """Charge un fichier JSONL."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def save_jsonl(path, data):
    """Sauvegarde des données en JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for d in data:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

def log(msg):
    """Log un message dans le fichier et la console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")
    print(log_msg)

def build_training_set():
    """
    Construit le dataset d'entraînement en fusionnant les prédictions
    et les scores réels, avec correction automatique des données.
    """
    log("=" * 70)
    log("📊 CONSTRUCTION DU DATASET D'ENTRAÎNEMENT")
    log("=" * 70)
    
    # Charger les données
    predicted = load_jsonl(f"{BASE_PATH}/predicted_matches.jsonl")
    real = load_jsonl(f"{BASE_PATH}/real_scores.jsonl")
    
    log(f"📥 Prédictions chargées: {len(predicted)}")
    log(f"📥 Scores réels chargés: {len(real)}")
    
    if not predicted or not real:
        log("❌ Pas assez de données pour l'entraînement.")
        return None
    
    # Construire la liste des équipes connues pour le fuzzy matching
    known_teams = list({p.get("home_team", "") for p in predicted if p.get("home_team")} | 
                      {p.get("away_team", "") for p in predicted if p.get("away_team")})
    log(f"🏟️  Équipes connues: {len(known_teams)}")
    
    merged = []
    used = 0
    skipped_no_match = 0
    skipped_incomplete = 0
    
    for match in predicted:
        # Correction des noms d'équipes
        home = match.get("home_team", "")
        away = match.get("away_team", "")
        
        if not home or not away:
            skipped_incomplete += 1
            continue
        
        home = fuzzy_match_team(home, known_teams)
        away = fuzzy_match_team(away, known_teams)
        
        # Correction de la ligue
        league = detect_league_auto(match.get("league", "Unknown"))
        
        # Chercher le score réel correspondant
        real_match = None
        for r in real:
            r_home = r.get("home_team", "")
            r_away = r.get("away_team", "")
            if home.lower() in r_home.lower() and away.lower() in r_away.lower():
                real_match = r
                break
        
        if not real_match:
            skipped_no_match += 1
            continue
        
        # Obtenir les coefficients
        try:
            home_coeff, away_coeff = get_coeffs_for_match(home, away, league)
        except Exception as e:
            log(f"⚠️  Erreur coefficients pour {home} vs {away}: {e}")
            home_coeff, away_coeff = 1.0, 1.0
        
        # Créer l'entrée d'entraînement
        merged.append({
            "home_team": home,
            "away_team": away,
            "league": league,
            "predicted": match.get("predicted_score", {}),
            "actual": real_match.get("score", {}),
            "home_coeff": home_coeff,
            "away_coeff": away_coeff,
            "timestamp": datetime.now().isoformat()
        })
        used += 1
    
    # Statistiques
    log("=" * 70)
    log("📈 STATISTIQUES DU DATASET")
    log("=" * 70)
    log(f"✅ Matchs utilisés: {used}")
    log(f"⚠️  Matchs sans correspondance: {skipped_no_match}")
    log(f"⚠️  Matchs incomplets: {skipped_incomplete}")
    log(f"📊 Taux de réussite: {(used / len(predicted) * 100):.1f}%")
    
    if used == 0:
        log("❌ Aucun match utilisable trouvé.")
        return None
    
    # Sauvegarder le dataset
    training_set_path = f"{BASE_PATH}/training_set.jsonl"
    save_jsonl(training_set_path, merged)
    log(f"💾 Dataset sauvegardé: {training_set_path}")
    
    return training_set_path

def train_ufa_model(dataset_path):
    """
    Entraîne le modèle UFA avec le dataset fourni.
    """
    log("=" * 70)
    log("🤖 ENTRAÎNEMENT DU MODÈLE UFA")
    log("=" * 70)
    
    try:
        # Importer le module d'entraînement UFA
        from ufa.training.trainer import train_model
        
        log("🔧 Démarrage de l'entraînement...")
        model = train_model(dataset_path, save_path=MODEL_PATH)
        
        log("=" * 70)
        log("✅ ENTRAÎNEMENT TERMINÉ AVEC SUCCÈS")
        log("=" * 70)
        log(f"📦 Modèle sauvegardé: {MODEL_PATH}")
        
        return model
        
    except ImportError as e:
        log(f"❌ Erreur d'import du trainer UFA: {e}")
        log("⚠️  Entraînement simulé (trainer non disponible)")
        return None
    except Exception as e:
        log(f"❌ Erreur durant l'entraînement: {e}")
        import traceback
        log(traceback.format_exc())
        return None

def main():
    """Fonction principale du script de réentraînement."""
    log("\n" + "=" * 70)
    log("🚀 DÉMARRAGE DU RÉENTRAÎNEMENT GLOBAL UFA")
    log("=" * 70)
    log(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"📂 Données: {BASE_PATH}")
    log(f"📝 Logs: {LOG_PATH}")
    log(f"🤖 Modèle: {MODEL_PATH}")
    
    # Étape 1: Construire le dataset
    dataset_path = build_training_set()
    
    if not dataset_path:
        log("⚠️  Aucune donnée valide trouvée. Arrêt du processus.")
        return
    
    # Étape 2: Entraîner le modèle
    model = train_ufa_model(dataset_path)
    
    if model:
        log("=" * 70)
        log("🎉 PROCESSUS TERMINÉ")
        log("=" * 70)
        log("✅ Le modèle UFA a été recalibré avec succès")
        log(f"📁 Dataset: {dataset_path}")
        log(f"🤖 Modèle: {MODEL_PATH}")
        log(f"📝 Rapport: {LOG_PATH}")
    else:
        log("=" * 70)
        log("⚠️  PROCESSUS TERMINÉ AVEC AVERTISSEMENTS")
        log("=" * 70)
        log("Le dataset a été créé mais l'entraînement a échoué")
        log("Vérifiez les logs ci-dessus pour plus de détails")

if __name__ == "__main__":
    main()

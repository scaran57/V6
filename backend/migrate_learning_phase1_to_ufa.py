#!/usr/bin/env python3
"""
Script de migration : Learning Phase 1 → UFA
Convertit les anciens matchs au format UFA avec détection automatique de ligue
"""

import json
import os
from datetime import datetime

# --- TABLE DE CORRESPONDANCE DES ÉQUIPES → LIGUE (VERSION ENRICHIE v2.3.1) ---
TEAM_LEAGUE_MAP = {
    # 🇪🇸 LaLiga
    "real madrid": "LaLiga", "madrid": "LaLiga", "barcelona": "LaLiga", 
    "atletico": "LaLiga", "atlético": "LaLiga",
    "sevilla": "LaLiga", "valencia": "LaLiga", "villarreal": "LaLiga",
    "betis": "LaLiga", "athletic": "LaLiga", "bilbao": "LaLiga",
    "sociedad": "LaLiga", "celta": "LaLiga", "getafe": "LaLiga",
    "osasuna": "LaLiga", "girona": "LaLiga", "rayo": "LaLiga",
    "mallorca": "LaLiga", "cadiz": "LaLiga", "almeria": "LaLiga",

    # 🏴 Premier League
    "manchester united": "PremierLeague", "man united": "PremierLeague",
    "manchester city": "PremierLeague", "man city": "PremierLeague",
    "arsenal": "PremierLeague", "chelsea": "PremierLeague",
    "liverpool": "PremierLeague", "tottenham": "PremierLeague",
    "newcastle": "PremierLeague", "brighton": "PremierLeague",
    "aston villa": "PremierLeague", "west ham": "PremierLeague",
    "everton": "PremierLeague", "leicester": "PremierLeague",
    "wolves": "PremierLeague", "fulham": "PremierLeague",
    "crystal palace": "PremierLeague", "brentford": "PremierLeague",
    "nottingham": "PremierLeague", "bournemouth": "PremierLeague",

    # 🇮🇹 Serie A
    "juventus": "SerieA", "juve": "SerieA",
    "inter": "SerieA", "milan": "SerieA", "ac milan": "SerieA",
    "napoli": "SerieA", "roma": "SerieA", "as roma": "SerieA",
    "lazio": "SerieA", "atalanta": "SerieA",
    "fiorentina": "SerieA", "torino": "SerieA",
    "bologna": "SerieA", "udinese": "SerieA",
    "genoa": "SerieA", "lecce": "SerieA", "empoli": "SerieA",
    "hellas verona": "SerieA", "cagliari": "SerieA",

    # 🇩🇪 Bundesliga
    "bayern": "Bundesliga", "münchen": "Bundesliga", "munich": "Bundesliga",
    "dortmund": "Bundesliga", "leipzig": "Bundesliga",
    "leverkusen": "Bundesliga", "bayer": "Bundesliga",
    "wolfsburg": "Bundesliga", "stuttgart": "Bundesliga",
    "frankfurt": "Bundesliga", "union berlin": "Bundesliga",
    "freiburg": "Bundesliga", "gladbach": "Bundesliga",
    "mönchengladbach": "Bundesliga", "köln": "Bundesliga",
    "mainz": "Bundesliga", "augsburg": "Bundesliga",
    "hoffenheim": "Bundesliga", "bochum": "Bundesliga",

    # 🇫🇷 Ligue 1
    "psg": "Ligue1", "paris": "Ligue1", "paris saint-germain": "Ligue1",
    "saint-germain": "Ligue1",
    "marseille": "Ligue1", "om": "Ligue1",
    "lyon": "Ligue1", "ol": "Ligue1",
    "lille": "Ligue1", "losc": "Ligue1",
    "monaco": "Ligue1", "nice": "Ligue1",
    "toulouse": "Ligue1", "reims": "Ligue1", 
    "rennes": "Ligue1", "lens": "Ligue1",
    "strasbourg": "Ligue1", "montpellier": "Ligue1",
    "nantes": "Ligue1", "brest": "Ligue1",
    "lorient": "Ligue1", "clermont": "Ligue1",
    "saint-étienne": "Ligue1", "saint-etienne": "Ligue1",
    "bordeaux": "Ligue1", "metz": "Ligue1",

    # 🇵🇹 Primeira Liga
    "benfica": "PrimeiraLiga", "porto": "PrimeiraLiga", "fc porto": "PrimeiraLiga",
    "sporting": "PrimeiraLiga", "sporting cp": "PrimeiraLiga",
    "braga": "PrimeiraLiga", "guimaraes": "PrimeiraLiga",
    "guimarães": "PrimeiraLiga", "boavista": "PrimeiraLiga",
    "gil vicente": "PrimeiraLiga", "vitoria": "PrimeiraLiga",

    # 🇫🇷 Ligue 2
    "ajaccio": "Ligue2", "amiens": "Ligue2", "bastia": "Ligue2",
    "troyes": "Ligue2", "auxerre": "Ligue2", "sochaux": "Ligue2",
    "angers": "Ligue2", "caen": "Ligue2", "grenoble": "Ligue2",
    "guingamp": "Ligue2", "laval": "Ligue2", "pau": "Ligue2",
    "rodez": "Ligue2", "valenciennes": "Ligue2",
    "dunkerque": "Ligue2", "quevilly": "Ligue2",
    "annecy": "Ligue2", "concarneau": "Ligue2",
    "paris fc": "Ligue2",

    # 🇳🇱 Eredivisie
    "ajax": "Eredivisie", "ajax amsterdam": "Eredivisie",
    "psv": "Eredivisie", "psv eindhoven": "Eredivisie",
    "feyenoord": "Eredivisie", "az": "Eredivisie", "az alkmaar": "Eredivisie",
    "twente": "Eredivisie", "fc twente": "Eredivisie",
    "utrecht": "Eredivisie", "fc utrecht": "Eredivisie",
    "vitesse": "Eredivisie", "groningen": "Eredivisie",
    "heerenveen": "Eredivisie", "go ahead": "Eredivisie",

    # 🌍 Champions League
    "galatasaray": "ChampionsLeague", "red star": "ChampionsLeague",
    "crvena zvezda": "ChampionsLeague", "zvezda": "ChampionsLeague",
    "shakhtar": "ChampionsLeague", "olympiacos": "ChampionsLeague",
    "copenhagen": "ChampionsLeague", "celtic": "ChampionsLeague",
    "young boys": "ChampionsLeague", "salzburg": "ChampionsLeague",
    "club brugge": "ChampionsLeague", "antwerp": "ChampionsLeague",

    # 🌍 Europa League
    "fenerbahce": "EuropaLeague", "fenerbahçe": "EuropaLeague",
    "rangers": "EuropaLeague", "slavia": "EuropaLeague",
    "sparta": "EuropaLeague", "qarabag": "EuropaLeague",
    "paok": "EuropaLeague", "olympiakos": "EuropaLeague"
}

# --- FONCTIONS UTILES ---
def detect_league(team_name: str) -> str:
    """Détecte la ligue à partir du nom d'équipe"""
    if not team_name:
        return "Unknown"
    
    name = team_name.lower().strip()
    
    # Recherche exacte puis partielle
    for key, league in TEAM_LEAGUE_MAP.items():
        if key in name:
            return league
    
    return "Unknown"

def parse_score(score_str: str):
    """Parse un score au format X-Y"""
    if not score_str or "-" not in score_str:
        return (0, 0)
    try:
        parts = score_str.split("-")
        home = int(parts[0].strip())
        away = int(parts[1].strip())
        return (home, away)
    except:
        return (0, 0)

# --- MIGRATION ---
def migrate_learning_data(input_path, output_path):
    """
    Migre les données de l'ancien format vers le format UFA
    """
    if not os.path.exists(input_path):
        print(f"❌ Fichier introuvable : {input_path}")
        return
    
    print("=" * 70)
    print("🔄 MIGRATION LEARNING PHASE 1 → UFA")
    print("=" * 70)
    print()
    
    migrated = []
    stats = {
        "total": 0,
        "by_league": {},
        "unknown": 0
    }
    
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                match = json.loads(line)
                
                # Extraire les données
                home = match.get("home") or match.get("home_team") or "Unknown"
                away = match.get("away") or match.get("away_team") or "Unknown"
                real = match.get("real") or match.get("result") or "0-0"
                timestamp = match.get("iso") or match.get("timestamp") or datetime.now().isoformat()
                match_id = match.get("match_id", f"migrated_{stats['total']}")
                
                # Détecter la ligue (priorité : home, puis away)
                league = detect_league(home)
                if league == "Unknown":
                    league = detect_league(away)
                
                # Parser le score réel
                home_goals, away_goals = parse_score(real)
                
                # Créer l'entrée migrée
                migrated_entry = {
                    "timestamp": timestamp,
                    "match_id": match_id,
                    "league": league,
                    "home_team": home,
                    "away_team": away,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "source": "migration_phase1"
                }
                
                migrated.append(migrated_entry)
                
                # Stats
                stats["total"] += 1
                stats["by_league"][league] = stats["by_league"].get(league, 0) + 1
                if league == "Unknown":
                    stats["unknown"] += 1
                
            except Exception as e:
                print(f"⚠️ Erreur migration ligne: {e}")
                continue
    
    # Sauvegarder les données migrées
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in migrated:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # Afficher le résumé
    print(f"✅ Migration terminée : {stats['total']} matchs convertis.")
    print(f"📂 Fichier de sortie : {output_path}")
    print()
    print("📊 Répartition par ligue:")
    for league, count in sorted(stats["by_league"].items(), key=lambda x: -x[1]):
        percentage = (count / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"   {league:20s} : {count:3d} matchs ({percentage:5.1f}%)")
    print()
    
    if stats["unknown"] > 0:
        print(f"⚠️  {stats['unknown']} matchs avec ligue 'Unknown' (non détectée)")
        print("   Ces matchs seront inclus dans le training UFA mais sans")
        print("   spécificité de ligue pour les coefficients.")
    
    print()
    print("=" * 70)
    
    return migrated, stats


if __name__ == "__main__":
    # Exécuter la migration
    migrated_data, statistics = migrate_learning_data(
        "/app/data/learning_events.jsonl",
        "/app/data/ufa_learning_events.jsonl"
    )
    
    print()
    print("🎯 Prochaines étapes:")
    print("   1. Fusionner avec real_scores.jsonl existant (optionnel)")
    print("   2. Lancer le training UFA: python3 ufa/training/trainer.py")
    print("   3. Vérifier l'état: cat /app/backend/ufa/training/state.json")

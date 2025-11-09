#!/usr/bin/env python3
# /app/backend/utils/migrate_old_analyses.py
"""
Migration des anciennes analyses vers le cache unifié UFA.
Fusionne : analyzer_uefa.jsonl, production_cache.jsonl → analysis_cache.jsonl
Évite les doublons automatiquement.
Génère un rapport statistique détaillé.
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE = Path("/app/data")
TARGET = BASE / "analysis_cache.jsonl"
OLD_FILES = [
    BASE / "analyzer_uefa.jsonl",
    BASE / "production_cache.jsonl",
    BASE / "uefa_analysis_cache.jsonl",
    BASE / "matches_memory.json"  # Ancien cache JSON
]

def read_jsonl(path):
    """Lit un fichier JSONL et retourne une liste d'objets"""
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception as e:
                print(f"⚠️  Ligne ignorée dans {path.name}: {e}")
                continue
    return out

def read_json(path):
    """Lit un fichier JSON et retourne un objet ou liste"""
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Erreur lecture {path.name}: {e}")
        return None

def write_jsonl(path, data):
    """Écrit une liste d'objets dans un fichier JSONL"""
    with path.open("w", encoding="utf-8") as f:
        for d in data:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

def normalize_entry(entry, source_file):
    """Normalise une entrée d'analyse pour le nouveau format"""
    # Format cible : celui de unified_analyzer
    normalized = {
        "timestamp": entry.get("timestamp", datetime.utcnow().isoformat()),
        "source": entry.get("source", f"migrated_from_{source_file}"),
        "home_team": entry.get("home_team") or entry.get("homeTeam"),
        "away_team": entry.get("away_team") or entry.get("awayTeam"),
        "league": entry.get("league") or entry.get("competition") or "Unknown",
        "home_goals_detected": entry.get("home_goals") or entry.get("home_goals_detected"),
        "away_goals_detected": entry.get("away_goals") or entry.get("away_goals_detected"),
        "raw_text": entry.get("raw_text", ""),
        "prediction": entry.get("prediction", {})
    }
    
    # Si pas de prédiction structurée, essayer de la construire
    if not normalized["prediction"] or not isinstance(normalized["prediction"], dict):
        normalized["prediction"] = {
            "status": "migrated",
            "most_probable": entry.get("mostProbableScore") or entry.get("predicted_score", "N/A"),
            "probabilities": entry.get("probabilities", {}),
            "confidence": entry.get("confidence", 0.0),
            "league_coeffs_applied": entry.get("leagueCoeffsApplied", False),
            "top3": entry.get("top3", [])
        }
    
    return normalized

def generate_key(entry):
    """Génère une clé unique pour détecter les doublons"""
    home = str(entry.get("home_team", "?")).lower().strip()
    away = str(entry.get("away_team", "?")).lower().strip()
    league = str(entry.get("league", "?")).lower().strip()
    timestamp = entry.get("timestamp", "?")
    
    # Clé basée sur équipes + ligue + date (ignorer heure pour détecter doublons du même jour)
    date_part = timestamp[:10] if timestamp and len(timestamp) >= 10 else "?"
    return f"{home}-{away}-{league}-{date_part}"

def migrate():
    """Fonction principale de migration"""
    print("=" * 60)
    print("🔄 MIGRATION DES ANALYSES VERS LE CACHE UNIFIÉ UFA")
    print("=" * 60)
    print()
    
    combined = []
    seen_keys = set()
    stats = {
        "total_read": 0,
        "duplicates": 0,
        "migrated": 0
    }
    
    # Lire les anciens fichiers
    for f in OLD_FILES:
        if not f.exists():
            print(f"⏭️  {f.name} n'existe pas, ignoré")
            continue
        
        print(f"📖 Lecture de {f.name}...")
        
        if f.suffix == ".json":
            # Fichier JSON classique
            data = read_json(f)
            if data is None:
                continue
            
            # Si c'est un dict, essayer d'extraire les entrées
            if isinstance(data, dict):
                entries = list(data.values()) if data else []
            elif isinstance(data, list):
                entries = data
            else:
                print(f"   ⚠️  Format non reconnu, ignoré")
                continue
        else:
            # Fichier JSONL
            entries = read_jsonl(f)
        
        stats["total_read"] += len(entries)
        print(f"   ✅ {len(entries)} entrées trouvées")
        
        for e in entries:
            # Normaliser l'entrée
            normalized = normalize_entry(e, f.stem)
            
            # Générer clé pour détection doublons
            key = generate_key(normalized)
            
            if key in seen_keys:
                stats["duplicates"] += 1
                continue
            
            combined.append(normalized)
            seen_keys.add(key)
            stats["migrated"] += 1
    
    # Ajouter ceux déjà dans le nouveau cache (éviter écrasement)
    if TARGET.exists():
        print(f"📖 Lecture du cache actuel {TARGET.name}...")
        current = read_jsonl(TARGET)
        stats["total_read"] += len(current)
        print(f"   ✅ {len(current)} entrées existantes")
        
        for e in current:
            key = generate_key(e)
            if key not in seen_keys:
                combined.append(e)
                seen_keys.add(key)
                stats["migrated"] += 1
            else:
                stats["duplicates"] += 1
    
    # Écrire le fichier final
    write_jsonl(TARGET, combined)
    
    print()
    print("=" * 60)
    print("✅ MIGRATION TERMINÉE")
    print("=" * 60)
    print(f"📊 Statistiques :")
    print(f"   • Entrées lues au total : {stats['total_read']}")
    print(f"   • Doublons détectés : {stats['duplicates']}")
    print(f"   • Entrées migrées : {stats['migrated']}")
    print(f"   • Fichier de sortie : {TARGET}")
    print()
    
    # Afficher un aperçu
    if combined:
        print("📋 Aperçu des 5 premières analyses :")
        for i, entry in enumerate(combined[:5], 1):
            home = entry.get("home_team", "?")
            away = entry.get("away_team", "?")
            league = entry.get("league", "?")
            score = entry.get("prediction", {}).get("most_probable", "?")
            print(f"   {i}. {home} vs {away} ({league}) → {score}")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ Erreur fatale : {e}")
        import traceback
        traceback.print_exc()

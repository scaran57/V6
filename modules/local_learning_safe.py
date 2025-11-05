# app/modules/local_learning_safe.py
"""
Module de lecture/écriture sécurisé pour l'apprentissage
Utilise un log append-only comme source de vérité immuable
"""
import json
import os
import time
from datetime import datetime

DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

LEARNING_LOG = os.path.join(DATA_DIR, "learning_events.jsonl")   # append-only log
TEAMS_FILE = os.path.join(DATA_DIR, "teams_data.json")          # last-N per team
META_FILE  = os.path.join(DATA_DIR, "learning_meta.json")       # diffExpected, schema_version
MEMORY_FILE = os.path.join(DATA_DIR, "matches_memory.json")     # existing matches saved

SCHEMA_VERSION = 2
DEFAULT_KEEP_LAST = 5   # nombre par défaut (modifiable)

# --- Helpers atomiques ---
def _atomic_write_json(path, obj):
    """Écriture atomique avec tmp + rename"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def _append_jsonl(path, obj):
    """Append JSON line atomic-ish on POSIX"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

# --- Initialisation files si manquants ---
def _ensure_files():
    """S'assure que tous les fichiers nécessaires existent"""
    if not os.path.exists(TEAMS_FILE):
        _atomic_write_json(TEAMS_FILE, {})
    if not os.path.exists(META_FILE):
        _atomic_write_json(META_FILE, {"diffExpected": 2.0, "schema_version": SCHEMA_VERSION})
    if not os.path.exists(LEARNING_LOG):
        open(LEARNING_LOG, "a").close()
    if not os.path.exists(MEMORY_FILE):
        _atomic_write_json(MEMORY_FILE, {})

_ensure_files()

# --- Fonctions principales ---
def load_meta():
    """Charge les métadonnées (diffExpected, schema_version)"""
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"diffExpected": 2.0, "schema_version": SCHEMA_VERSION}

def save_meta(meta):
    """Sauvegarde les métadonnées de manière atomique"""
    meta["schema_version"] = SCHEMA_VERSION
    _atomic_write_json(META_FILE, meta)

def load_teams():
    """Charge les données des équipes"""
    try:
        with open(TEAMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_teams(d):
    """Sauvegarde les données des équipes de manière atomique"""
    _atomic_write_json(TEAMS_FILE, d)

def record_learning_event(match_id, home_team, away_team, predicted, real, agent_id=None, keep_last=DEFAULT_KEEP_LAST):
    """
    Enregistre un événement d'apprentissage dans le log append-only,
    met à jour teams_data.json en conservant les `keep_last` derniers résultats par équipe,
    et met à jour diffExpected selon la règle 60/40.
    
    Args:
        match_id: Identifiant unique du match
        home_team: Nom de l'équipe à domicile
        away_team: Nom de l'équipe à l'extérieur
        predicted: Score prédit (format "X-Y")
        real: Score réel (format "X-Y")
        agent_id: ID de l'agent qui enregistre (optionnel)
        keep_last: Nombre de matchs à conserver par équipe (défaut: 5)
    
    Returns:
        (bool, dict/str): (succès, event ou message d'erreur)
    """
    ts = time.time()
    event = {
        "ts": ts,
        "iso": datetime.utcfromtimestamp(ts).isoformat() + "Z",
        "match_id": match_id,
        "home": home_team,
        "away": away_team,
        "predicted": predicted,
        "real": real,
        "agent_id": agent_id,
        "schema_version": SCHEMA_VERSION
    }

    # Append to log (immutable)
    _append_jsonl(LEARNING_LOG, event)

    # Update per-team last-N
    teams = load_teams()
    
    # Parse real score
    try:
        rh, ra = map(int, real.split("-"))
    except:
        return False, "format real score invalide"

    # Ajouter le résultat pour l'équipe domicile
    teams.setdefault(home_team, []).append([rh, ra])
    teams[home_team] = teams[home_team][-keep_last:]
    
    # Ajouter le résultat pour l'équipe extérieur (inversé)
    teams.setdefault(away_team, []).append([ra, rh])
    teams[away_team] = teams[away_team][-keep_last:]

    save_teams(teams)

    # Update diffExpected meta (60/40)
    meta = load_meta()
    old = meta.get("diffExpected", 2.0)
    
    try:
        ph, pa = map(int, predicted.split("-"))
        diff_pred = abs(pa - ph)
    except:
        diff_pred = old
    
    diff_real = abs(ra - rh)
    new_diff = (old * 3 + diff_real * 2) / 5.0
    meta["diffExpected"] = round(new_diff, 3)
    save_meta(meta)
    
    return True, event

def export_learning_log(path_out):
    """Copie le log complet pour backup/export"""
    with open(LEARNING_LOG, "rb") as src, open(path_out, "wb") as dst:
        dst.write(src.read())
    return path_out

def check_schema_compatibility():
    """Vérifie la compatibilité du schéma"""
    meta = load_meta()
    return meta.get("schema_version") == SCHEMA_VERSION

def get_learning_stats():
    """Retourne des statistiques sur l'apprentissage"""
    try:
        with open(LEARNING_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        total_events = len(lines)
        teams_data = load_teams()
        meta = load_meta()
        
        return {
            "total_learning_events": total_events,
            "teams_count": len(teams_data),
            "diffExpected": meta.get("diffExpected"),
            "schema_version": meta.get("schema_version"),
            "log_file_exists": os.path.exists(LEARNING_LOG),
            "teams_file_exists": os.path.exists(TEAMS_FILE),
            "meta_file_exists": os.path.exists(META_FILE)
        }
    except Exception as e:
        return {"error": str(e)}

#!/usr/bin/env python3
"""
UFA v3 Diagnostic Tool
Vérifie l'état complet du système : fichiers, modules, données, logs
"""
import os
import json
import datetime
import importlib
import sys

# Ajouter le backend au path
sys.path.insert(0, '/app/backend')

REPORT = {
    "datetime": str(datetime.datetime.utcnow()),
    "checks": {},
    "errors": []
}

def log(section, msg, ok=True):
    REPORT["checks"].setdefault(section, []).append(
        ("✅ " if ok else "❌ ") + msg
    )

def test_file_exists(path, section):
    if os.path.exists(path):
        log(section, f"Fichier trouvé : {path}")
        return True
    else:
        log(section, f"Fichier manquant : {path}", ok=False)
        REPORT["errors"].append(path)
        return False

def test_import(module_name, section):
    try:
        importlib.import_module(module_name)
        log(section, f"Module {module_name} importé avec succès")
        return True
    except Exception as e:
        log(section, f"Échec import {module_name} → {e}", ok=False)
        REPORT["errors"].append(module_name)
        return False

def read_json(path, section):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log(section, f"Lecture OK ({len(data)} entrées)")
        return data
    except Exception as e:
        log(section, f"Erreur lecture {path} → {e}", ok=False)
        REPORT["errors"].append(path)
        return None

# === 1️⃣ Vérification des dossiers de base ===
section = "Structure de projet"
for p in ["/app/data", "/app/models", "/app/backend", "/app/logs"]:
    test_file_exists(p, section)

# === 2️⃣ Vérification des fichiers clés ===
section = "Fichiers essentiels"
essential_files = [
    "/app/data/league_coefficients.json",
    "/app/data/world_coeffs.json",
    "/app/data/real_scores.jsonl",
    "/app/models/ufa_model_v3.pt"
]
for f in essential_files:
    test_file_exists(f, section)

# === 3️⃣ Vérification modules Python ===
section = "Modules Python"
modules = [
    "ufa.world_coeffs_updater",
    "ufa.ufa_v3_for_emergent",
    "league_scheduler",
    "ocr_parser",
    "score_predictor"
]
for m in modules:
    test_import(m, section)

# === 4️⃣ Vérification contenus JSON ===
section = "Contenu Coefficients"
if os.path.exists("/app/data/league_coefficients.json"):
    data = read_json("/app/data/league_coefficients.json", section)
    if data:
        log(section, f"Ligues disponibles : {', '.join(data.keys())}")

if os.path.exists("/app/data/world_coeffs.json"):
    data = read_json("/app/data/world_coeffs.json", section)
    if data:
        if "teams" in data:
            log(section, f"Équipes internationales : {len(data['teams'])}")
        else:
            log(section, f"Équipes internationales : {len(data)}")

# === 5️⃣ Vérification métadonnées modèle UFAv3 ===
section = "Modèle UFAv3"
meta_path = "/app/models/ufa_model_v3_meta.json"
if test_file_exists(meta_path, section):
    meta = read_json(meta_path, section)
    if meta:
        log(section, f"Teams dans vocabulaire : {len(meta.get('team2idx', {}))}")
        log(section, f"Ligues dans vocabulaire : {len(meta.get('league2idx', {}))}")
        log(section, f"Dernière formation : {meta.get('last_trained', 'N/A')}")

model_path = "/app/models/ufa_model_v3.pt"
if test_file_exists(model_path, section):
    size_mb = os.path.getsize(model_path) / (1024 * 1024)
    log(section, f"Taille du modèle : {size_mb:.2f} MB")

# === 6️⃣ Vérification logs récents ===
section = "Scheduler & Logs"
log_files = [
    "/var/log/supervisor/backend.err.log",
    "/var/log/supervisor/backend.out.log"
]
for lf in log_files:
    if test_file_exists(lf, section):
        try:
            with open(lf, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-20:]
            found_scheduler = any("Planificateur" in l or "Scheduler" in l for l in lines)
            found_ufa = any("UFA" in l or "ufa" in l for l in lines)
            found_fifa = any("FIFA" in l for l in lines)
            
            activities = []
            if found_scheduler:
                activities.append("scheduler")
            if found_ufa:
                activities.append("UFA")
            if found_fifa:
                activities.append("FIFA")
            
            activity_str = ", ".join(activities) if activities else "aucune"
            log(section, f"Log {os.path.basename(lf)} → activité: {activity_str}")
        except Exception as e:
            log(section, f"Erreur lecture log {lf}: {e}", ok=False)

# === 7️⃣ Vérification taille des datasets ===
section = "Datasets"

def count_lines(path):
    if not os.path.exists(path):
        return 0
    try:
        return sum(1 for _ in open(path, "r", encoding="utf-8", errors="ignore"))
    except Exception:
        return 0

cache = count_lines("/app/data/analysis_cache.jsonl")
real = count_lines("/app/data/real_scores.jsonl")
train = count_lines("/app/data/training_set.jsonl")

log(section, f"Analysis cache: {cache} lignes")
log(section, f"Real scores: {real} lignes")
log(section, f"Training set: {train} lignes")

# === 8️⃣ Test API endpoints (optionnel) ===
section = "API Endpoints"
try:
    import requests
    
    # Test status endpoint
    try:
        r = requests.get("http://localhost:8001/api/ufa/v3/status", timeout=2)
        if r.status_code == 200:
            data = r.json()
            log(section, f"API /api/ufa/v3/status → available: {data.get('available')}")
            log(section, f"API → {data.get('num_teams')} teams, {data.get('num_leagues')} leagues")
        else:
            log(section, f"API status code: {r.status_code}", ok=False)
    except Exception as e:
        log(section, f"API non accessible: {e}", ok=False)
        
except ImportError:
    log(section, "Module requests non disponible (skip tests API)")

# === 9️⃣ Vérification scheduler status ===
section = "État du Scheduler"
try:
    # Vérifier si le processus backend tourne
    import subprocess
    result = subprocess.run(
        ["supervisorctl", "status", "backend"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if "RUNNING" in result.stdout:
        log(section, "Backend supervisord → RUNNING")
    else:
        log(section, f"Backend status: {result.stdout.strip()}", ok=False)
except Exception as e:
    log(section, f"Impossible de vérifier supervisord: {e}", ok=False)

# === Résumé final ===
print("\n" + "="*60)
print("🧠 RAPPORT DE DIAGNOSTIC UFA V3")
print("="*60)
print(f"📅 Date: {REPORT['datetime']}")
print("="*60)

for section, messages in REPORT["checks"].items():
    print(f"\n🔹 {section}")
    for msg in messages:
        print("  " + msg)

print("\n" + "="*60)
if REPORT["errors"]:
    print(f"⚠️  {len(REPORT['errors'])} problèmes détectés :")
    for e in REPORT["errors"]:
        print("  - " + e)
else:
    print("✅ Aucun problème détecté. Le système est complet et fonctionnel.")
print("="*60 + "\n")

# Sauvegarder le rapport
try:
    report_file = "/app/logs/ufa_v3_diagnostic_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=2, ensure_ascii=False)
    print(f"📄 Rapport sauvegardé dans: {report_file}\n")
except Exception as e:
    print(f"⚠️  Impossible de sauvegarder le rapport: {e}\n")

#!/usr/bin/env python3
"""
UFA Backend Diagnostic
Diagnostic automatique complet du backend UFAv3
"""
import os
import json
import psutil
import time
from datetime import datetime

LOG_PATHS = [
    "/var/log/supervisor/backend.out.log",
    "/var/log/supervisor/backend.err.log",
    "/app/logs/keep_alive.log",
    "/app/logs/odds_integration.log",
    "/app/logs/ufa_v3_training.log"
]

def tail(file_path, lines=20):
    """Lit les N dernières lignes d'un fichier"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.readlines()
        return "".join(data[-lines:])
    except Exception as e:
        return f"❌ Impossible de lire {file_path}: {e}"

def check_backend_process():
    """Vérifie si les processus backend sont actifs"""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
        try:
            cmdline = " ".join(p.info.get("cmdline", []))
            if "uvicorn" in cmdline or "server.py" in cmdline:
                procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs

def check_files():
    """Vérifie l'existence des fichiers importants"""
    files_to_check = {
        "Modèle UFAv3": "/app/models/ufa_model_v3.pt",
        "Métadonnées UFAv3": "/app/models/ufa_model_v3_meta.json",
        "Cotes marché": "/app/data/odds_data.jsonl",
        "Scores réels": "/app/data/real_scores.jsonl",
        "Training set": "/app/data/training_set.jsonl",
        "Coefficients FIFA": "/app/data/world_coeffs.json",
        "Coefficients UEFA": "/app/data/league_coefficients.json"
    }
    
    results = {}
    for name, path in files_to_check.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            results[name] = {"exists": True, "size_kb": round(size / 1024, 2)}
        else:
            results[name] = {"exists": False, "size_kb": 0}
    
    return results

def check_api_endpoints():
    """Teste rapidement quelques endpoints"""
    import requests
    
    endpoints = {
        "Health": "http://localhost:8001/api/health",
        "UFAv3 Status": "http://localhost:8001/api/ufa/v3/status",
        "Odds Stats": "http://localhost:8001/api/ufa/v3/odds-stats",
        "Dashboard": "http://localhost:8001/api/ufa/v3/dashboard-status"
    }
    
    results = {}
    for name, url in endpoints.items():
        try:
            r = requests.get(url, timeout=3)
            results[name] = {
                "status": r.status_code,
                "ok": r.status_code == 200,
                "response_size": len(r.text)
            }
        except Exception as e:
            results[name] = {"status": "error", "ok": False, "error": str(e)}
    
    return results

def main():
    print("=" * 70)
    print("=== 🔍 DIAGNOSTIC BACKEND UFAv3 ===")
    print("=" * 70)
    print()
    
    status = {
        "timestamp": datetime.now().isoformat(),
        "processes": [],
        "files": {},
        "endpoints": {},
        "logs": {}
    }

    # 1. Vérifier les processus actifs
    print("📊 1. PROCESSUS BACKEND")
    print("-" * 70)
    procs = check_backend_process()
    if procs:
        print(f"✅ {len(procs)} processus backend détecté(s):")
        for p in procs:
            cmdline = " ".join(p['cmdline'][:5]) if p.get('cmdline') else "N/A"
            print(f"   - PID {p['pid']}: {cmdline}")
            print(f"     CPU: {p.get('cpu_percent', 0):.1f}% | RAM: {p.get('memory_percent', 0):.1f}%")
        status["processes"] = procs
    else:
        print("❌ Aucun processus backend actif détecté.")
    
    # 2. Vérifier les fichiers
    print("\n📁 2. FICHIERS IMPORTANTS")
    print("-" * 70)
    files = check_files()
    for name, info in files.items():
        icon = "✅" if info["exists"] else "❌"
        size_str = f"{info['size_kb']} KB" if info["exists"] else "N/A"
        print(f"{icon} {name:30} {size_str:>15}")
    status["files"] = files
    
    # 3. Tester les endpoints
    print("\n🌐 3. ENDPOINTS API")
    print("-" * 70)
    endpoints = check_api_endpoints()
    for name, result in endpoints.items():
        icon = "✅" if result.get("ok") else "❌"
        status_code = result.get("status", "error")
        print(f"{icon} {name:30} Status: {status_code}")
    status["endpoints"] = endpoints
    
    # 4. Lire les logs
    print("\n📋 4. LOGS RÉCENTS")
    print("-" * 70)
    for path in LOG_PATHS:
        if os.path.exists(path):
            content = tail(path, 30)
            status["logs"][path] = content
            
            # Chercher les erreurs
            errors = [line for line in content.split('\n') if 'ERROR' in line or 'Exception' in line or 'Traceback' in line]
            if errors:
                print(f"⚠️  {os.path.basename(path)}: {len(errors)} erreur(s) détectée(s)")
            else:
                print(f"✅ {os.path.basename(path)}: Aucune erreur récente")
        else:
            status["logs"][path] = "Fichier introuvable."
            print(f"❌ {os.path.basename(path)}: Fichier introuvable")
    
    # Sauvegarde JSON
    out_path = "/app/logs/ufa_backend_diagnostic.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print(f"🗂️  Rapport complet sauvegardé dans : {out_path}")
    print("=" * 70)
    
    # Afficher les dernières lignes du log backend
    print("\n📝 DERNIÈRES LIGNES BACKEND.ERR.LOG :")
    print("-" * 70)
    backend_log = status["logs"].get("/var/log/supervisor/backend.err.log", "Aucun log.")
    print(backend_log[-2000:])  # Derniers 2000 caractères
    
    # Résumé final
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ")
    print("=" * 70)
    
    total_files = len(files)
    files_ok = sum(1 for f in files.values() if f["exists"])
    print(f"Fichiers : {files_ok}/{total_files} présents")
    
    total_endpoints = len(endpoints)
    endpoints_ok = sum(1 for e in endpoints.values() if e.get("ok"))
    print(f"Endpoints : {endpoints_ok}/{total_endpoints} fonctionnels")
    
    print(f"Processus : {len(procs)} actif(s)")
    
    if len(procs) > 0 and files_ok >= total_files * 0.8 and endpoints_ok >= total_endpoints * 0.7:
        print("\n✅ SYSTÈME OPÉRATIONNEL")
    else:
        print("\n⚠️  PROBLÈMES DÉTECTÉS - Vérifier les logs ci-dessus")

if __name__ == "__main__":
    main()

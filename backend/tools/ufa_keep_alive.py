#!/usr/bin/env python3
"""
UFA Keep-Alive Daemon
Maintient le backend actif même quand Emergent entre en veille.
Vérifie le scheduler, le modèle et relance si nécessaire.
"""

import os
import time
import json
import datetime
import subprocess

LOG_PATH = "/app/logs/keep_alive.log"
STATUS_API = "http://127.0.0.1:8001/api/ufa/v3/status"  # Port corrigé à 8001
SCHEDULER_SCRIPT = "/app/backend/league_scheduler.py"
CHECK_INTERVAL = 10800  # 3h en secondes

def log(message: str):
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")
    print(f"[keep_alive] {message}")

def is_scheduler_active():
    """Vérifie si le scheduler tourne"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "league_scheduler"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception:
        return False

def check_api_status():
    """Teste l'endpoint UFAv3"""
    try:
        import requests
        r = requests.get(STATUS_API, timeout=10)
        if r.status_code == 200:
            data = r.json()
            num_leagues = data.get("num_leagues", 0)
            num_teams = data.get("num_teams", 0)
            available = data.get("available", False)
            return True, f"API OK - {num_leagues} ligues, {num_teams} équipes, available={available}"
        return False, f"API status: {r.status_code}"
    except ImportError:
        return None, "Module requests non disponible (skip)"
    except Exception as e:
        return False, f"API error: {str(e)}"

def check_backend_running():
    """Vérifie si le backend supervisord tourne"""
    try:
        result = subprocess.run(
            ["supervisorctl", "status", "backend"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if "RUNNING" in result.stdout:
            return True, "Backend supervisord RUNNING"
        else:
            return False, f"Backend status: {result.stdout.strip()}"
    except Exception as e:
        return False, f"Erreur vérification backend: {e}"

RESTART_CMD = "/app/backend/start_production_backend.sh"

def restart_backend():
    """Redémarre le backend via le script de production"""
    try:
        subprocess.run(
            ["bash", RESTART_CMD],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        log(f"Backend redémarré via {RESTART_CMD}")
        time.sleep(5)  # Attendre que le backend démarre
    except Exception as e:
        log(f"Erreur redémarrage backend: {e}")

def main():
    log("=== UFA Keep-Alive démarré ===")
    log(f"Intervalle de vérification: {CHECK_INTERVAL}s ({CHECK_INTERVAL/3600}h)")
    
    while True:
        try:
            log("--- Début cycle de vérification ---")
            
            # Vérifier le backend supervisord
            backend_ok, backend_msg = check_backend_running()
            log(f"Backend: {backend_msg}")
            
            if not backend_ok:
                log("⚠️  Backend inactif → tentative de redémarrage...")
                restart_backend()
                continue
            
            # Vérifier l'API
            api_ok, api_msg = check_api_status()
            if api_ok is not None:  # Si requests est disponible
                log(f"API: {api_msg}")
                
                if not api_ok:
                    log("⚠️  API non accessible → redémarrage backend...")
                    restart_backend()
                    continue
            
            # Vérifier le scheduler (implicite via backend)
            if is_scheduler_active():
                log("Scheduler: Actif ✅")
            else:
                log("Scheduler: Inactif (mais intégré au backend)")
            
            log("✅ Système opérationnel")
            
        except Exception as e:
            log(f"❌ Erreur dans cycle: {e}")
        
        log(f"Cycle terminé, veille {CHECK_INTERVAL/3600}h...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()

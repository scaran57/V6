# /app/backend/api/dashboard_status.py
"""
Dashboard Status API
Fournit l'état complet du système UFAv3 : processus, coefficients, modèle, performance, logs
"""
import os
import json
import datetime
import psutil
from fastapi import APIRouter

router = APIRouter()

LOG_PATH = "/app/logs/keep_alive.log"
PERF_PATH = "/app/logs/performance_summary.json"
PERF_HISTORY = "/app/logs/performance_history.jsonl"
COEFF_FIFA = "/app/data/world_coeffs.json"
COEFF_UEFA = "/app/data/league_coefficients.json"
MODEL_PATH = "/app/models/ufa_model_v3.pt"


@router.get("/api/ufa/v3/dashboard-status")
def get_dashboard_status():
    """
    Retourne l'état complet du système UFAv3.
    
    Returns:
        dict: Status complet avec processus, coefficients, modèle, performance, logs, historique
    """
    status = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "scheduler": "unknown",
        "keep_alive": "unknown",
        "backend": "unknown",
        "coeffs": {"fifa_teams": 0, "uefa_leagues": 0},
        "model": {"exists": False, "size_kb": 0},
        "performance": {"accuracy": None, "matches": 0},
        "logs": [],
        "history": []
    }

    # --- Process Check ---
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "league_scheduler.py" in cmd or "league_scheduler" in cmd:
                    status["scheduler"] = "running"
                if "ufa_keep_alive.py" in cmd:
                    status["keep_alive"] = "running"
                if "uvicorn" in cmd or "server.py" in cmd:
                    status["backend"] = "running"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"Erreur vérification processus: {e}")

    # --- Coefficients FIFA ---
    if os.path.exists(COEFF_FIFA):
        try:
            with open(COEFF_FIFA, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "teams" in data:
                    status["coeffs"]["fifa_teams"] = len(data["teams"])
                else:
                    status["coeffs"]["fifa_teams"] = len(data)
        except Exception as e:
            print(f"Erreur lecture FIFA coeffs: {e}")

    # --- Coefficients UEFA ---
    if os.path.exists(COEFF_UEFA):
        try:
            with open(COEFF_UEFA, 'r', encoding='utf-8') as f:
                data = json.load(f)
                status["coeffs"]["uefa_leagues"] = len(data)
        except Exception as e:
            print(f"Erreur lecture UEFA coeffs: {e}")

    # --- Modèle ---
    if os.path.exists(MODEL_PATH):
        status["model"]["exists"] = True
        status["model"]["size_kb"] = round(os.path.getsize(MODEL_PATH) / 1024, 2)

    # --- Performance courante ---
    if os.path.exists(PERF_PATH):
        try:
            with open(PERF_PATH, 'r', encoding='utf-8') as f:
                perf = json.load(f)
                status["performance"]["accuracy"] = perf.get("avg_accuracy", None)
                status["performance"]["matches"] = perf.get("matches", 0)
        except Exception as e:
            print(f"Erreur lecture performance: {e}")

    # --- Historique d'évolution du modèle ---
    if os.path.exists(PERF_HISTORY):
        try:
            with open(PERF_HISTORY, 'r', encoding='utf-8') as f:
                history = []
                for line in f.readlines()[-30:]:  # 30 derniers points
                    try:
                        d = json.loads(line)
                        history.append({
                            "date": d.get("date"),
                            "accuracy": d.get("accuracy")
                        })
                    except Exception:
                        continue
                status["history"] = history
        except Exception as e:
            print(f"Erreur lecture historique: {e}")

    # --- Logs récents ---
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()[-5:]
                status["logs"] = [line.strip() for line in lines]
        except Exception as e:
            print(f"Erreur lecture logs: {e}")

    return status

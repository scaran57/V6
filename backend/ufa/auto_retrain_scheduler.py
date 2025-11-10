#!/usr/bin/env python3
# /app/backend/ufa/auto_retrain_scheduler.py
"""
Scheduler automatique de réentraînement du modèle UFA.

Vérifie quotidiennement le besoin de réentraînement, lance le processus
complet (réentraînement + évaluation + ajustement coefficients), et
maintient un historique.

Usage:
    python3 /app/backend/ufa/auto_retrain_scheduler.py
    
    Ou comme daemon/service background
"""
import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le backend au path
sys.path.insert(0, '/app/backend')

from ufa.force_retrain_all import main as retrain_all
from ufa.performance_tracker import evaluate_model
from league_coeff import update_league_coefficients

LOG_FILE = "/app/logs/retrain_auto.log"
SCHEDULE_FILE = "/app/data/last_retrain.json"

# Créer les dossiers nécessaires
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
Path(SCHEDULE_FILE).parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    """Log un message dans le fichier et la console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")
    print(log_msg)

def should_retrain():
    """
    Détermine si un réentraînement est nécessaire.
    Critères: Plus de 24h depuis le dernier réentraînement.
    
    Returns:
        bool: True si réentraînement nécessaire
    """
    if not os.path.exists(SCHEDULE_FILE):
        log("🆕 Première exécution, réentraînement nécessaire")
        return True
    
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        last_run = datetime.fromisoformat(data.get("last_run"))
        delta = datetime.utcnow() - last_run
        
        if delta > timedelta(hours=24):
            log(f"⏰ Dernier réentraînement il y a {delta.days} jours et {delta.seconds//3600} heures")
            return True
        else:
            log(f"⏳ Dernier réentraînement il y a {delta.seconds//3600}h, pas besoin de réentraîner")
            return False
            
    except Exception as e:
        log(f"⚠️  Erreur lecture schedule: {e}, réentraînement par sécurité")
        return True

def update_schedule():
    """Mise à jour de la date du dernier réentraînement."""
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "last_run": datetime.utcnow().isoformat(),
            "status": "completed"
        }, f, indent=2)
    log(f"📅 Schedule mis à jour: {SCHEDULE_FILE}")

def run_auto_retrain():
    """
    Exécute le cycle complet de réentraînement automatique:
    1. Vérification du besoin
    2. Réentraînement du modèle
    3. Évaluation des performances
    4. Ajustement des coefficients
    """
    log("\n" + "=" * 70)
    log("🚀 CYCLE DE RÉENTRAÎNEMENT AUTOMATIQUE")
    log("=" * 70)
    log(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Étape 1: Vérifier le besoin
    if not should_retrain():
        log("⏳ Réentraînement non nécessaire aujourd'hui.")
        log("=" * 70)
        return
    
    # Étape 2: Réentraînement global
    log("=" * 70)
    log("🔁 ÉTAPE 1/3: Réentraînement global du modèle")
    log("=" * 70)
    try:
        retrain_all()
        log("✅ Réentraînement terminé avec succès")
    except Exception as e:
        log(f"❌ Erreur durant le réentraînement: {e}")
        import traceback
        log(traceback.format_exc())
        return
    
    # Étape 3: Évaluation des performances
    log("=" * 70)
    log("🔁 ÉTAPE 2/3: Évaluation des performances")
    log("=" * 70)
    try:
        perf = evaluate_model("/app/data/training_set.jsonl")
        if perf:
            log(f"✅ Évaluation terminée: {len(perf)} ligues analysées")
        else:
            log("⚠️  Aucune performance à évaluer")
    except Exception as e:
        log(f"❌ Erreur durant l'évaluation: {e}")
        import traceback
        log(traceback.format_exc())
    
    # Étape 4: Ajustement des coefficients
    log("=" * 70)
    log("🔁 ÉTAPE 3/3: Ajustement des coefficients de ligue")
    log("=" * 70)
    try:
        update_league_coefficients("/app/data/performance_summary.json")
        log("✅ Coefficients ajustés selon les performances")
    except Exception as e:
        log(f"❌ Erreur durant l'ajustement des coefficients: {e}")
        import traceback
        log(traceback.format_exc())
    
    # Mise à jour du schedule
    update_schedule()
    
    log("=" * 70)
    log("✅ CYCLE DE RÉENTRAÎNEMENT AUTOMATIQUE TERMINÉ")
    log("=" * 70)

def main_loop():
    """
    Boucle principale du scheduler.
    S'exécute en continu et vérifie chaque jour à 03h05.
    """
    log("=" * 70)
    log("🤖 DÉMARRAGE DU SCHEDULER AUTOMATIQUE UFA")
    log("=" * 70)
    log("⏰ Vérification quotidienne programmée à 03:05 UTC")
    log("📁 Logs: " + LOG_FILE)
    log("📅 Schedule: " + SCHEDULE_FILE)
    
    while True:
        try:
            now = datetime.utcnow()
            
            # Vérifier si c'est l'heure de réentraîner (03h05)
            if now.hour == 3 and 5 <= now.minute < 10:
                log(f"⏰ Heure de réentraînement atteinte: {now.strftime('%H:%M')}")
                run_auto_retrain()
                
                # Attendre 10 minutes pour éviter de relancer
                log("⏸️  Pause de 10 minutes...")
                time.sleep(600)
            else:
                # Vérifier toutes les 5 minutes
                time.sleep(300)
                
        except KeyboardInterrupt:
            log("🛑 Arrêt du scheduler (Ctrl+C)")
            break
        except Exception as e:
            log(f"❌ Erreur dans la boucle principale: {e}")
            import traceback
            log(traceback.format_exc())
            # Attendre 1 minute avant de réessayer
            time.sleep(60)

if __name__ == "__main__":
    # Permettre un mode test avec argument
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        log("🧪 MODE TEST: Lancement immédiat du réentraînement")
        run_auto_retrain()
    else:
        main_loop()

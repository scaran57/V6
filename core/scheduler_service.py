"""
Service de scheduling pour les mises à jour automatiques
Utilise APScheduler pour exécuter les tâches à 3h00 quotidiennement
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
from pathlib import Path
import json
import logging
import sys

logger = logging.getLogger(__name__)

# Ajout du backend au path
sys.path.insert(0, '/app/backend')

# Fichiers de statut
STATUS_DIR = Path("/app/state")
STATUS_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = STATUS_DIR / "scheduler_status.json"
TIMEZONE = "Europe/Paris"

# Instance globale du scheduler
_scheduler_instance = None

def _write_status(active: bool, last_run: str = None, last_error: str = None, next_run: str = None):
    """Écrit le statut du scheduler dans un fichier JSON"""
    try:
        status = {
            "active": active,
            "last_run": last_run,
            "last_error": last_error,
            "next_run": next_run,
            "timezone": TIMEZONE,
            "updated_at": datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        }
        STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False))
        logger.debug(f"📝 Statut scheduler mis à jour: active={active}")
    except Exception as e:
        logger.error(f"❌ Erreur écriture statut scheduler: {e}")

def get_scheduler_status() -> dict:
    """Lit le statut du scheduler depuis le fichier"""
    try:
        if STATUS_FILE.exists():
            return json.loads(STATUS_FILE.read_text())
        else:
            return {"active": False, "error": "Status file not found"}
    except Exception as e:
        logger.error(f"❌ Erreur lecture statut: {e}")
        return {"active": False, "error": str(e)}

def update_all_leagues_job():
    """
    Job principal : Mise à jour de toutes les ligues
    Appelé automatiquement à 3h00 chaque jour
    """
    logger.info("="*70)
    logger.info("🔄 DÉBUT MISE À JOUR AUTOMATIQUE DES LIGUES")
    logger.info("="*70)
    
    start_time = datetime.now(pytz.timezone(TIMEZONE))
    
    try:
        # Importer le système de mise à jour existant
        from league_unified import update_all_leagues
        
        logger.info("📊 Lancement de la mise à jour des ligues...")
        
        # Exécuter la mise à jour
        report = update_all_leagues()
        
        # Log du résumé
        logger.info(f"✅ Mise à jour terminée:")
        logger.info(f"   - Total ligues: {report.get('total_leagues', 0)}")
        logger.info(f"   - Mises à jour: {report.get('leagues_updated', 0)}")
        logger.info(f"   - Fallback: {report.get('leagues_fallback', 0)}")
        logger.info(f"   - Échecs: {report.get('leagues_failed', 0)}")
        
        # Mettre à jour le statut
        _write_status(
            active=True,
            last_run=start_time.isoformat(),
            last_error=None,
            next_run=None  # Sera recalculé après
        )
        
        logger.info("="*70)
        logger.info("✅ MISE À JOUR AUTOMATIQUE COMPLÉTÉE")
        logger.info("="*70)
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Erreur durant la mise à jour automatique: {e}", exc_info=True)
        
        _write_status(
            active=True,
            last_run=start_time.isoformat(),
            last_error=str(e),
            next_run=None
        )
        
        raise

def manual_trigger_update():
    """
    Déclenche manuellement une mise à jour
    Peut être appelé via API
    """
    logger.info("🔄 Mise à jour manuelle déclenchée")
    return update_all_leagues_job()

def start_scheduler():
    """
    Démarre le scheduler en arrière-plan
    Configure le job pour s'exécuter à 3h00 tous les jours
    """
    global _scheduler_instance
    
    if _scheduler_instance is not None:
        logger.warning("⚠️ Scheduler déjà démarré")
        return _scheduler_instance
    
    try:
        logger.info("🚀 Démarrage du scheduler...")
        
        # Créer le scheduler
        scheduler = BackgroundScheduler(timezone=TIMEZONE)
        
        # Configurer le trigger : tous les jours à 3h00
        trigger = CronTrigger(
            hour=3,
            minute=0,
            timezone=pytz.timezone(TIMEZONE)
        )
        
        # Ajouter le job
        scheduler.add_job(
            update_all_leagues_job,
            trigger,
            id="update_all_leagues",
            name="Mise à jour quotidienne des ligues",
            replace_existing=True,
            max_instances=1  # Empêcher les exécutions simultanées
        )
        
        # Démarrer le scheduler
        scheduler.start()
        
        # Calculer la prochaine exécution
        job = scheduler.get_job("update_all_leagues")
        next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
        
        _write_status(active=True, next_run=next_run)
        
        _scheduler_instance = scheduler
        
        logger.info("✅ Scheduler démarré avec succès")
        logger.info(f"⏰ Prochaine exécution: {next_run}")
        logger.info(f"🌍 Timezone: {TIMEZONE}")
        
        return scheduler
        
    except Exception as e:
        logger.error(f"❌ Erreur démarrage scheduler: {e}", exc_info=True)
        _write_status(active=False, last_error=str(e))
        raise

def stop_scheduler(scheduler=None):
    """Arrête le scheduler"""
    global _scheduler_instance
    
    target = scheduler or _scheduler_instance
    
    if target is None:
        logger.warning("⚠️ Aucun scheduler à arrêter")
        return
    
    try:
        logger.info("🛑 Arrêt du scheduler...")
        target.shutdown(wait=False)
        _write_status(active=False)
        _scheduler_instance = None
        logger.info("✅ Scheduler arrêté")
    except Exception as e:
        logger.error(f"❌ Erreur arrêt scheduler: {e}")

def get_scheduler_info():
    """Retourne les informations détaillées sur le scheduler"""
    global _scheduler_instance
    
    if _scheduler_instance is None:
        return {
            "running": False,
            "error": "Scheduler not started"
        }
    
    try:
        job = _scheduler_instance.get_job("update_all_leagues")
        
        if job:
            return {
                "running": True,
                "job_id": job.id,
                "job_name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "timezone": TIMEZONE
            }
        else:
            return {
                "running": True,
                "error": "Job not found"
            }
    except Exception as e:
        logger.error(f"❌ Erreur récupération info scheduler: {e}")
        return {
            "running": False,
            "error": str(e)
        }

# Test du module
if __name__ == "__main__":
    import time
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    print("="*70)
    print("TEST SCHEDULER SERVICE")
    print("="*70)
    
    # Démarrer le scheduler
    print("\n1️⃣ Démarrage du scheduler...")
    scheduler = start_scheduler()
    
    # Afficher les infos
    print("\n2️⃣ Informations scheduler:")
    info = get_scheduler_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    # Lire le statut
    print("\n3️⃣ Statut depuis fichier:")
    status = get_scheduler_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # Test de mise à jour manuelle (commenté par défaut)
    # print("\n4️⃣ Test mise à jour manuelle...")
    # manual_trigger_update()
    
    print("\n5️⃣ Scheduler en attente (Ctrl+C pour arrêter)...")
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print("\n\n🛑 Interruption...")
    
    # Arrêter le scheduler
    print("\n6️⃣ Arrêt du scheduler...")
    stop_scheduler()
    
    print("\n✅ Tests terminés")

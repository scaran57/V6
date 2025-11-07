#!/usr/bin/env python3
"""
Planificateur d'audits automatiques hebdomadaires
Exécute system_audit.py tous les 7 jours
"""
import schedule
import time
import subprocess
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

AUDIT_SCRIPT = "/app/backend/system_audit.py"

def run_audit():
    """Exécute le script d'audit système"""
    try:
        logger.info("=" * 80)
        logger.info("🔍 DÉMARRAGE DE L'AUDIT AUTOMATIQUE HEBDOMADAIRE")
        logger.info("=" * 80)
        
        result = subprocess.run(
            ["python3", AUDIT_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            logger.info("✅ Audit terminé avec succès")
            logger.info(result.stdout)
        else:
            logger.error("❌ Audit échoué")
            logger.error(result.stderr)
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Audit timeout (> 60s)")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'audit: {e}")

def main():
    """Fonction principale du planificateur"""
    logger.info("🚀 Démarrage du planificateur d'audits automatiques")
    logger.info(f"⏰ Planifié: Tous les dimanches à 00:00 UTC")
    
    # Planifier l'audit tous les dimanches à 00:00
    schedule.every().sunday.at("00:00").do(run_audit)
    
    # Exécuter un audit immédiatement au démarrage (optionnel)
    # run_audit()
    
    logger.info("✅ Planificateur initialisé et en attente...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Vérifier toutes les 60 secondes
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du planificateur d'audits")

if __name__ == "__main__":
    main()

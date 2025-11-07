# /app/backend/league_scheduler.py
"""
Planificateur automatique pour les mises à jour quotidiennes des ligues.
Lance un thread en arrière-plan qui met à jour les classements chaque jour.
"""
import threading
import time
import logging
from datetime import datetime, time as dt_time
import sys
sys.path.insert(0, '/app/backend')

import league_updater

logger = logging.getLogger(__name__)

class LeagueScheduler:
    """
    Planificateur qui exécute des mises à jour automatiques des ligues.
    S'exécute dans un thread séparé en arrière-plan.
    """
    
    def __init__(self, update_time_hour=3, update_time_minute=0):
        """
        Initialise le planificateur.
        
        Args:
            update_time_hour: Heure de la mise à jour quotidienne (0-23)
            update_time_minute: Minute de la mise à jour quotidienne (0-59)
        """
        self.update_time = dt_time(update_time_hour, update_time_minute)
        self.is_running = False
        self.thread = None
        self.last_update = None
        
        logger.info(f"🕐 Planificateur initialisé: mise à jour quotidienne à {update_time_hour:02d}:{update_time_minute:02d}")
    
    def start(self):
        """Démarre le planificateur dans un thread séparé"""
        if self.is_running:
            logger.warning("⚠️ Le planificateur est déjà en cours d'exécution")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        logger.info("✅ Planificateur démarré en arrière-plan")
    
    def stop(self):
        """Arrête le planificateur"""
        if not self.is_running:
            logger.warning("⚠️ Le planificateur n'est pas en cours d'exécution")
            return
        
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("✅ Planificateur arrêté")
    
    def _run_loop(self):
        """Boucle principale du planificateur (s'exécute dans un thread)"""
        logger.info("🔄 Boucle de planification démarrée")
        
        # Mise à jour initiale au démarrage (non-bloquante)
        self._perform_initial_update()
        
        while self.is_running:
            try:
                now = datetime.now()
                current_time = now.time()
                
                # Vérifier si c'est l'heure de la mise à jour
                if self._should_update(current_time):
                    logger.info("⏰ Heure de mise à jour atteinte")
                    self._perform_update()
                    
                    # Attendre au moins 2 minutes pour éviter les doubles mises à jour
                    time.sleep(120)
                else:
                    # Vérifier toutes les 60 secondes
                    time.sleep(60)
                    
            except Exception as e:
                logger.error(f"❌ Erreur dans la boucle du planificateur: {e}")
                time.sleep(300)  # Attendre 5 minutes en cas d'erreur
        
        logger.info("🛑 Boucle de planification arrêtée")
    
    def _should_update(self, current_time):
        """
        Détermine si une mise à jour doit être effectuée maintenant.
        
        Args:
            current_time: Heure actuelle
        
        Returns:
            bool: True si mise à jour nécessaire
        """
        # Fenêtre de 2 minutes autour de l'heure cible
        target_minutes = self.update_time.hour * 60 + self.update_time.minute
        current_minutes = current_time.hour * 60 + current_time.minute
        
        time_match = abs(current_minutes - target_minutes) <= 1
        
        # Vérifier si on a déjà fait une mise à jour aujourd'hui
        if time_match and self.last_update:
            last_update_date = self.last_update.date()
            current_date = datetime.now().date()
            already_updated_today = last_update_date == current_date
            
            return not already_updated_today
        
        return time_match
    
    def _perform_initial_update(self):
        """Effectue une mise à jour initiale au démarrage (si nécessaire)"""
        try:
            logger.info("🚀 Vérification des données de ligues au démarrage...")
            
            # Vérifier si les données sont récentes (moins de 24h)
            needs_update = False
            
            for league in league_updater.get_available_leagues():
                info = league_updater.get_league_info(league)
                if not info or not info.get("has_data"):
                    needs_update = True
                    logger.info(f"⚠️ Pas de données pour {league}")
                    break
            
            if needs_update:
                logger.info("🔄 Mise à jour initiale nécessaire...")
                self._perform_update()
            else:
                logger.info("✅ Données de ligues déjà à jour")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la mise à jour initiale: {e}")
    
    def _perform_update(self):
        """Effectue la mise à jour de toutes les ligues"""
        try:
            logger.info("=" * 60)
            logger.info("🔄 DÉBUT DE LA MISE À JOUR AUTOMATIQUE DES LIGUES")
            logger.info("=" * 60)
            
            results = league_updater.update_all_leagues(force=False)
            
            self.last_update = datetime.now()
            
            logger.info("=" * 60)
            logger.info("✅ MISE À JOUR AUTOMATIQUE TERMINÉE")
            logger.info(f"📊 Résumé: {results['summary']['successful']}/{results['summary']['total']} ligues réussies")
            logger.info(f"🕐 Prochaine mise à jour: demain à {self.update_time.hour:02d}:{self.update_time.minute:02d}")
            logger.info("=" * 60)
            
            # Exécuter la validation des prédictions après la mise à jour des ligues
            self._run_validation()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la mise à jour automatique: {e}")
    
    def _run_validation(self):
        """Exécute la validation des prédictions"""
        try:
            logger.info("=" * 60)
            logger.info("🔍 DÉBUT DE LA VALIDATION DES PRÉDICTIONS")
            logger.info("=" * 60)
            
            # Importer ici pour éviter les imports circulaires
            sys.path.insert(0, '/app/backend')
            import prediction_validator
            
            report = prediction_validator.validate_predictions(days_back=7)
            
            if report.get("status") == "success":
                logger.info(f"✅ Validation terminée:")
                logger.info(f"   📊 Matchs testés: {report.get('matches_tested', 0)}")
                logger.info(f"   🎯 Précision exacte: {report.get('accuracy', 0):.1%}")
                logger.info(f"   🎲 Précision résultat (1X2): {report.get('outcome_accuracy', 0):.1%}")
                logger.info(f"   📈 MAE: {report.get('mae', 0):.2f}")
                logger.info(f"   📉 RMSE: {report.get('rmse', 0):.2f}")
            else:
                logger.info(f"ℹ️ Validation: {report.get('message', 'Pas de données')}")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la validation: {e}")
    
    def trigger_manual_update(self):
        """Déclenche une mise à jour manuelle immédiate (non-bloquant)"""
        logger.info("🔧 Mise à jour manuelle déclenchée")
        
        # Lancer dans un thread séparé pour ne pas bloquer
        thread = threading.Thread(target=self._perform_update, daemon=True)
        thread.start()
    
    def get_status(self):
        """
        Retourne le statut actuel du planificateur.
        
        Returns:
            dict: Statut du planificateur
        """
        return {
            "is_running": self.is_running,
            "update_time": f"{self.update_time.hour:02d}:{self.update_time.minute:02d}",
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "next_update": self._get_next_update_time()
        }
    
    def _get_next_update_time(self):
        """Calcule l'heure de la prochaine mise à jour"""
        now = datetime.now()
        next_update = now.replace(
            hour=self.update_time.hour,
            minute=self.update_time.minute,
            second=0,
            microsecond=0
        )
        
        # Si l'heure est déjà passée aujourd'hui, planifier pour demain
        if next_update <= now:
            from datetime import timedelta
            next_update += timedelta(days=1)
        
        return next_update.isoformat()


# Instance globale du planificateur
_scheduler_instance = None

def get_scheduler():
    """
    Récupère l'instance globale du planificateur (singleton).
    
    Returns:
        LeagueScheduler: Instance du planificateur
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = LeagueScheduler(update_time_hour=3, update_time_minute=0)
    return _scheduler_instance

def start_scheduler():
    """Démarre le planificateur global"""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler

def stop_scheduler():
    """Arrête le planificateur global"""
    scheduler = get_scheduler()
    scheduler.stop()

def get_scheduler_status():
    """Récupère le statut du planificateur global"""
    scheduler = get_scheduler()
    return scheduler.get_status()

def trigger_manual_update():
    """Déclenche une mise à jour manuelle via le planificateur"""
    scheduler = get_scheduler()
    scheduler.trigger_manual_update()


if __name__ == "__main__":
    # Test du planificateur
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🔄 Démarrage du planificateur de test...")
    scheduler = start_scheduler()
    
    print(f"✅ Planificateur démarré")
    print(f"📊 Statut: {get_scheduler_status()}")
    
    try:
        # Garder le programme en vie
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du planificateur...")
        stop_scheduler()
        print("✅ Planificateur arrêté")

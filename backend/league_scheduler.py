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
import subprocess
from pathlib import Path

sys.path.insert(0, '/app/backend')

import league_unified

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
        self.last_fifa_update = None  # Pour les mises à jour FIFA hebdomadaires
        self.last_ufa_v3_retrain = None  # Pour les réentraînements UFA v3
        
        logger.info(f"🕐 Planificateur initialisé: mise à jour quotidienne à {update_time_hour:02d}:{update_time_minute:02d}")
        logger.info(f"🌍 Mise à jour FIFA: chaque lundi à 03:05")
        logger.info(f"🤖 Réentraînement UFA v3: quotidien à 03:05")
    
    def start(self):
        """Démarre le planificateur dans un thread séparé"""
        if self.is_running:
            logger.warning("⚠️ Le planificateur est déjà en cours d'exécution")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        logger.info("✅ Planificateur démarré en arrière-plan")
        
        # Lancer le keep-alive automatiquement
        try:
            from league_scheduler import ensure_keep_alive_running
            ensure_keep_alive_running()
        except Exception as e:
            logger.warning(f"Keep-alive non lancé: {e}")
    
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
                
                # Vérifier si c'est l'heure de la mise à jour quotidienne
                if self._should_update(current_time):
                    logger.info("⏰ Heure de mise à jour quotidienne atteinte")
                    self._perform_update()
                    
                    # Attendre au moins 2 minutes pour éviter les doubles mises à jour
                    time.sleep(120)
                
                # Vérifier si c'est l'heure de la mise à jour FIFA hebdomadaire (lundi 03:05)
                elif self._should_update_fifa(now):
                    logger.info("⏰ Heure de mise à jour FIFA hebdomadaire atteinte (lundi)")
                    self._update_fifa_rankings()
                    time.sleep(120)
                
                # Vérifier si c'est l'heure du réentraînement UFA v3 (03:05)
                elif self._should_retrain_ufa_v3(now):
                    logger.info("⏰ Heure de réentraînement UFA v3 atteinte")
                    self._retrain_ufa_v3()
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
    
    def _should_update_fifa(self, now):
        """
        Détermine si une mise à jour FIFA hebdomadaire doit être effectuée.
        Se lance chaque lundi à 03:05.
        
        Args:
            now: datetime actuel
        
        Returns:
            bool: True si mise à jour FIFA nécessaire
        """
        # Vérifier si c'est lundi (weekday() = 0)
        is_monday = now.weekday() == 0
        
        # Vérifier l'heure (03:05)
        is_correct_time = now.hour == 3 and now.minute == 5
        
        if is_monday and is_correct_time:
            # Vérifier si on a déjà fait une mise à jour cette semaine
            if self.last_fifa_update:
                days_since_update = (now - self.last_fifa_update).days
                # Si moins de 6 jours, on a déjà fait la mise à jour cette semaine
                if days_since_update < 6:
                    return False
            
            return True
        
        return False
    
    def _update_fifa_rankings(self):
        """
        Mise à jour des coefficients FIFA pour les matchs internationaux.
        S'exécute au démarrage et de manière hebdomadaire.
        """
        try:
            logger.info("🌍 Mise à jour des coefficients FIFA...")
            
            # Importer et appeler la fonction de mise à jour FIFA
            sys.path.insert(0, '/app/backend')
            from ufa.update_fifa_rankings import update_world_coeffs
            
            result = update_world_coeffs()
            
            if result and "teams" in result:
                num_teams = len(result["teams"])
                logger.info(f"✅ Coefficients FIFA mis à jour: {num_teams} équipes nationales")
                self.last_fifa_update = datetime.now()  # Sauvegarder la date de mise à jour
            else:
                logger.warning("⚠️ Mise à jour FIFA: utilisation du fallback")
                
        except ImportError as e:
            logger.error(f"❌ Erreur import update_fifa_rankings: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour FIFA: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _should_retrain_ufa_v3(self, now):
        """
        Détermine si un réentraînement UFA v3 doit être effectué.
        Se lance quotidiennement à 03:05.
        
        Args:
            now: datetime actuel
        
        Returns:
            bool: True si réentraînement UFA v3 nécessaire
        """
        # Vérifier l'heure (03:05)
        is_correct_time = now.hour == 3 and now.minute == 5
        
        if is_correct_time:
            # Vérifier si on a déjà fait un réentraînement aujourd'hui
            if self.last_ufa_v3_retrain:
                days_since_retrain = (now - self.last_ufa_v3_retrain).days
                # Si c'est le même jour, ne pas ré-entraîner
                if days_since_retrain < 1:
                    return False
            
            return True
        
        return False
    
    def _retrain_ufa_v3(self):
        """
        Réentraînement incrémental du modèle UFA v3.
        S'exécute quotidiennement à 03:05.
        """
        try:
            logger.info("🤖 Démarrage du réentraînement UFA v3...")
            
            sys.path.insert(0, '/app/backend')
            from ufa.ufa_v3_for_emergent import train_model_incremental, TRAINING_SET
            
            # Vérifier que le fichier d'entraînement existe
            import os
            if not os.path.exists(TRAINING_SET):
                logger.warning(f"⚠️ Fichier d'entraînement non trouvé: {TRAINING_SET}")
                return
            
            # Lancer l'entraînement incrémental
            # Paramètres: 5 epochs, wallcap de 45 min (2700 secondes)
            train_model_incremental(
                train_path=TRAINING_SET,
                epochs=5,
                batch_size=64,
                lr=1e-4,
                wallcap_seconds=2700,  # 45 minutes max
                patience=3
            )
            
            logger.info("✅ Réentraînement UFA v3 terminé avec succès")
            self.last_ufa_v3_retrain = datetime.now()
            
            # Ajustement automatique des coefficients FIFA
            try:
                logger.info("🌍 Ajustement automatique des coefficients FIFA...")
                from ufa.world_coeffs_updater import adjust_coeffs_from_results
                
                coeffs = adjust_coeffs_from_results("/app/data/real_scores.jsonl")
                logger.info(f"✅ Coefficients FIFA ajustés automatiquement ({len(coeffs)} équipes)")
            except ImportError as e:
                logger.error(f"❌ Erreur import world_coeffs_updater: {e}")
            except Exception as e:
                logger.error(f"❌ Erreur ajustement coefficients FIFA: {e}")
            
        except ImportError as e:
            logger.error(f"❌ Erreur import ufa_v3_for_emergent: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur réentraînement UFA v3: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _run_migration_cache(self):
        """
        Migration automatique des anciennes analyses (UEFA/Production) vers le cache unifié.
        S'exécute une seule fois au démarrage du scheduler.
        Génère un rapport statistique détaillé.
        """
        try:
            logger.info("🔄 Initialisation UFA System...")
            logger.info("🧩 Migration automatique du cache d'analyse...")
            
            # Importer et appeler la fonction de migration
            sys.path.insert(0, '/app/backend')
            from utils.migrate_old_analyses import migrate_and_report
            
            summary = migrate_and_report()
            
            # Afficher le résumé dans les logs
            logger.info(summary)
            logger.info(f"📁 Fichier final : /app/data/analysis_cache.jsonl")
            
        except ImportError as e:
            logger.error(f"❌ Erreur import script migration : {e}")
        except Exception as e:
            logger.error(f"❌ Erreur migration cache : {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _perform_initial_update(self):
        """Effectue une mise à jour initiale au démarrage (si nécessaire)"""
        try:
            # ÉTAPE 0 : Mise à jour des coefficients FIFA
            self._update_fifa_rankings()
            
            # ÉTAPE 1 : Migration automatique du cache d'analyse
            self._run_migration_cache()
            
            # ÉTAPE 2 : Vérification et mise à jour des ligues
            logger.info("🚀 Vérification des données de ligues au démarrage (système unifié)...")
            
            # Vérifier si le rapport global existe et est récent
            import os
            report_path = "/app/data/leagues/global_update_report.json"
            
            needs_update = False
            if not os.path.exists(report_path):
                logger.info("⚠️ Aucun rapport global trouvé")
                needs_update = True
            else:
                import json
                try:
                    with open(report_path, 'r') as f:
                        report = json.load(f)
                        leagues_updated = report.get('leagues_updated', 0)
                        total_leagues = report.get('total_leagues', 0)
                        
                        if leagues_updated < total_leagues:
                            logger.info(f"⚠️ Seulement {leagues_updated}/{total_leagues} ligues à jour")
                            needs_update = True
                except Exception as e:
                    logger.warning(f"⚠️ Erreur lecture rapport: {e}")
                    needs_update = True
            
            if needs_update:
                logger.info("🔄 Mise à jour initiale nécessaire...")
                self._perform_update()
            else:
                logger.info("✅ Données de ligues déjà à jour")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la mise à jour initiale: {e}")
    
    def _perform_update(self):
        """Effectue la mise à jour de toutes les ligues via le système unifié"""
        try:
            logger.info("=" * 60)
            logger.info("🔄 DÉBUT DE LA MISE À JOUR AUTOMATIQUE - SYSTÈME UNIFIÉ")
            logger.info("=" * 60)
            
            # Mise à jour de TOUTES les ligues via le système unifié
            results = league_unified.update_all_leagues()
            
            self.last_update = datetime.now()
            
            logger.info("=" * 60)
            logger.info("✅ MISE À JOUR AUTOMATIQUE COMPLÈTE")
            logger.info(f"📊 Total: {results['leagues_updated']}/{results['total_leagues']} ligues mises à jour")
            logger.info(f"🕐 Prochaine mise à jour: demain à {self.update_time.hour:02d}:{self.update_time.minute:02d}")
            logger.info("=" * 60)
            
            # Exécuter la validation des prédictions après la mise à jour des ligues
            self._run_validation()
            
            # Exécuter la validation automatique des scores réels (UFA)
            self._run_ufa_auto_validate()
            
            # Exécuter l'entraînement UFA après la validation
            self._run_ufa_training()
            
            # Exécuter la vérification d'équilibre UFA
            self._run_balance_check()
            
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
    
    def _run_ufa_auto_validate(self):
        """Exécute la validation automatique des scores réels depuis Football-Data.org API"""
        try:
            logger.info("=" * 60)
            logger.info("✅ VALIDATION AUTOMATIQUE DES SCORES RÉELS (UFA)")
            logger.info("⚽ Récupération depuis Football-Data.org API...")
            logger.info("=" * 60)
            
            # Importer et appeler la fonction auto_validate_scores
            sys.path.insert(0, '/app/backend')
            from ufa.ufa_auto_validate import auto_validate_scores
            
            auto_validate_scores()
            
            logger.info("=" * 60)
            logger.info("✅ Validation automatique terminée")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la validation automatique: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _run_ufa_training(self):
        """Exécute l'entraînement UFA"""
        try:
            logger.info("=" * 60)
            logger.info("🧠 DÉBUT DE L'ENTRAÎNEMENT UFA")
            logger.info("=" * 60)
            
            # Importer le module de training UFA
            sys.path.insert(0, '/app/backend')
            from ufa.training.trainer import train_from_real_matches
            
            result = train_from_real_matches()
            
            if result.get("status") == "no_data":
                logger.info(f"ℹ️ Training UFA: {result.get('message', 'Pas de données')}")
            else:
                logger.info(f"✅ Training UFA terminé:")
                logger.info(f"   📊 Matchs traités: {result.get('matches_processed', 0)}")
                logger.info(f"   📉 Perte moyenne: {result.get('global_avg_loss', 0):.3f}")
                
                # Afficher les stats par ligue
                league_stats = result.get('league_stats', {})
                for league, stats in league_stats.items():
                    logger.info(f"   🏆 {league}: Loss={stats.get('avg_loss', 0):.3f}, "
                               f"Accuracy={stats.get('accuracy', 0):.1f}%")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du training UFA: {e}")
    
    def _run_balance_check(self):
        """Exécute la vérification d'équilibre UFA"""
        try:
            logger.info("=" * 60)
            logger.info("⚖️  VÉRIFICATION D'ÉQUILIBRE UFA")
            logger.info("=" * 60)
            
            # Importer le module de vérification
            sys.path.insert(0, '/app/backend')
            from ufa.ufa_check_balance import analyze_balance
            
            report = analyze_balance()
            
            if report.get("status") == "error":
                logger.info(f"ℹ️ Balance Check: {report.get('message', 'Erreur')}")
            else:
                logger.info(f"✅ Vérification d'équilibre terminée:")
                logger.info(f"   📊 Total matchs: {report.get('total_matches', 0)}")
                logger.info(f"   🔍 Ratio Unknown: {report.get('unknown_ratio', 0)*100:.1f}%")
                
                # Afficher les alertes
                alerts = report.get('alerts', [])
                if alerts:
                    logger.warning(f"   ⚠️  {len(alerts)} alerte(s) détectée(s):")
                    for alert in alerts:
                        logger.warning(f"      • {alert}")
                else:
                    logger.info(f"   ✅ Aucune alerte - Système équilibré")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification d'équilibre: {e}")
    
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


# === AUTO-INTEGRATION: UFA KEEP-ALIVE SUPPORT ===
import subprocess

KEEP_ALIVE_PATH = "/app/backend/tools/ufa_keep_alive.py"
KEEP_ALIVE_LOG = "/app/logs/keep_alive_auto.log"

def ensure_keep_alive_running():
    """Vérifie si le keep-alive tourne déjà, sinon le démarre"""
    try:
        # Vérifie s'il tourne déjà
        result = subprocess.run(
            ["pgrep", "-f", "ufa_keep_alive.py"],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            # Pas encore lancé, on le démarre
            subprocess.Popen(
                ["nohup", "python3", KEEP_ALIVE_PATH],
                stdout=open(KEEP_ALIVE_LOG, "a"),
                stderr=open(KEEP_ALIVE_LOG, "a"),
            )
            logger.info("[UFA Scheduler] Keep-Alive lancé automatiquement ✅")
        else:
            logger.info("[UFA Scheduler] Keep-Alive déjà actif 🟢")
    except Exception as e:
        logger.warning(f"[UFA Scheduler] Erreur lancement keep-alive: {e}")


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

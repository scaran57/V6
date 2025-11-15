#!/usr/bin/env python3
# /app/backend/tools/league_updater_unified.py
"""
Système Unifié de Mise à Jour des Classements
----------------------------------------------
Combine plusieurs sources de données avec fallback intelligent:
1. Football-Data.org API (priorité 1 - officiel)
2. Données manuelles (priorité 2 - vos screenshots)
3. Cache local (priorité 3 - dernières données connues)

Gestion intelligente des quotas et rate limiting.
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, '/app/backend')

# Import des modules de sources
from tools.football_data_standings import (
    fetch_league_standings as fetch_from_football_data,
    convert_to_internal_format as convert_football_data,
    get_requests_count_today as get_fd_requests_today,
    LEAGUE_IDS as FD_LEAGUE_IDS
)

logger = logging.getLogger(__name__)

# =========================================
# ⚙️ CONFIGURATION
# =========================================

DATA_DIR = "/app/data/leagues"
REPORT_FILE = "/app/data/leagues/unified_update_report.json"

# Stratégie de mise à jour par défaut
DEFAULT_STRATEGY = "football_data_api"  # ou "manual_only"

# Ligues prioritaires (mises à jour automatiquement)
PRIORITY_LEAGUES = [
    "LaLiga",
    "PremierLeague",
    "SerieA",
    "Bundesliga",
    "Ligue1"
]

# Toutes les ligues disponibles
ALL_LEAGUES = [
    "LaLiga",
    "PremierLeague",
    "SerieA",
    "Bundesliga",
    "Ligue1",
    "PrimeiraLiga",
    "Ligue2",
    "ChampionsLeague",
    "EuropaLeague"
]

# =========================================
# 📊 GESTION DES SOURCES
# =========================================

def get_league_file_path(league_name):
    """Retourne le chemin du fichier JSON pour une ligue"""
    return os.path.join(DATA_DIR, f"{league_name}.json")

def load_league_data(league_name):
    """Charge les données locales d'une ligue"""
    file_path = get_league_file_path(league_name)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None

def get_data_age(league_data):
    """Calcule l'âge des données en heures"""
    if not league_data or 'updated' not in league_data:
        return float('inf')
    
    try:
        updated_dt = datetime.fromisoformat(league_data['updated'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        age_hours = (now - updated_dt).total_seconds() / 3600
        return age_hours
    except:
        return float('inf')

def is_data_fresh(league_data, max_age_hours=24):
    """Vérifie si les données sont récentes"""
    age = get_data_age(league_data)
    return age < max_age_hours

# =========================================
# 🔄 STRATÉGIES DE MISE À JOUR
# =========================================

def update_league_from_api(league_name):
    """
    Met à jour une ligue depuis Football-Data.org API
    
    Returns:
        dict: Données mises à jour ou None
    """
    logger.info(f"📡 Tentative de mise à jour {league_name} depuis Football-Data.org API")
    
    # Vérifier si la ligue est supportée
    if league_name not in FD_LEAGUE_IDS:
        logger.warning(f"⚠️ {league_name} non supportée par Football-Data.org")
        return None
    
    # Récupérer depuis l'API
    api_data = fetch_from_football_data(league_name)
    if not api_data:
        logger.error(f"❌ Échec récupération API pour {league_name}")
        return None
    
    # Convertir au format interne
    internal_data = convert_football_data(api_data, league_name)
    if not internal_data:
        logger.error(f"❌ Échec conversion pour {league_name}")
        return None
    
    logger.info(f"✅ {league_name} récupérée depuis API ({len(internal_data['teams'])} équipes)")
    return internal_data

def update_league_smart(league_name, force=False):
    """
    Mise à jour intelligente d'une ligue
    
    Args:
        league_name: Nom de la ligue
        force: Force la mise à jour même si données récentes
    
    Returns:
        dict: Résultat de la mise à jour
    """
    result = {
        "league": league_name,
        "success": False,
        "source": None,
        "action": None,
        "teams_count": 0
    }
    
    # Charger les données locales
    local_data = load_league_data(league_name)
    
    # Vérifier si mise à jour nécessaire
    if not force and local_data and is_data_fresh(local_data, max_age_hours=24):
        age_hours = get_data_age(local_data)
        logger.info(f"ℹ️ {league_name}: données récentes ({age_hours:.1f}h), pas de mise à jour")
        result["action"] = "skipped_fresh_data"
        result["success"] = True
        result["source"] = local_data.get("source", "unknown")
        result["teams_count"] = len(local_data.get("teams", []))
        return result
    
    # Tenter mise à jour depuis API
    updated_data = update_league_from_api(league_name)
    
    if updated_data:
        # Sauvegarder
        file_path = get_league_file_path(league_name)
        
        # Backup si données existantes
        if os.path.exists(file_path):
            backup_path = file_path + ".backup_auto"
            try:
                os.rename(file_path, backup_path)
            except:
                pass
        
        # Sauvegarde atomique
        tmp_path = file_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, file_path)
        
        result["success"] = True
        result["source"] = "football_data_api"
        result["action"] = "updated_from_api"
        result["teams_count"] = len(updated_data["teams"])
        logger.info(f"✅ {league_name} mise à jour depuis API et sauvegardée")
    else:
        # Utiliser les données locales comme fallback
        if local_data:
            age_hours = get_data_age(local_data)
            logger.warning(f"⚠️ {league_name}: échec API, utilisation cache local ({age_hours:.1f}h)")
            result["success"] = True
            result["source"] = local_data.get("source", "cache")
            result["action"] = "fallback_to_cache"
            result["teams_count"] = len(local_data.get("teams", []))
        else:
            logger.error(f"❌ {league_name}: échec complet (pas d'API ni de cache)")
            result["action"] = "failed_no_data"
    
    return result

# =========================================
# 🚀 MISE À JOUR GLOBALE
# =========================================

def update_all_leagues_smart(leagues_list=None, force=False, max_api_calls=10):
    """
    Met à jour plusieurs ligues avec gestion intelligente des quotas
    
    Args:
        leagues_list: Liste des ligues à mettre à jour (None = prioritaires seulement)
        force: Force la mise à jour même si données récentes
        max_api_calls: Nombre maximum d'appels API autorisés
    
    Returns:
        dict: Rapport détaillé
    """
    if leagues_list is None:
        leagues_list = PRIORITY_LEAGUES
    
    logger.info(f"🔄 Mise à jour intelligente de {len(leagues_list)} ligues")
    logger.info(f"📋 Ligues: {', '.join(leagues_list)}")
    logger.info(f"🔢 Limite API: {max_api_calls} appels maximum")
    
    # Vérifier les requêtes déjà effectuées aujourd'hui
    api_requests_today = get_fd_requests_today()
    logger.info(f"📊 Requêtes Football-Data.org aujourd'hui: {api_requests_today}")
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": "smart_update",
        "leagues_processed": [],
        "api_calls_made": 0,
        "api_calls_limit": max_api_calls,
        "api_calls_today_before": api_requests_today,
        "summary": {
            "updated_from_api": 0,
            "skipped_fresh": 0,
            "fallback_to_cache": 0,
            "failed": 0
        }
    }
    
    api_calls_this_session = 0
    
    for league_name in leagues_list:
        # Vérifier limite API
        if api_calls_this_session >= max_api_calls:
            logger.warning(f"⚠️ Limite d'appels API atteinte ({max_api_calls}), arrêt")
            break
        
        result = update_league_smart(league_name, force=force)
        report["leagues_processed"].append(result)
        
        # Compter les appels API
        if result["source"] == "football_data_api":
            api_calls_this_session += 1
        
        # Mise à jour statistiques
        action = result["action"]
        if action == "updated_from_api":
            report["summary"]["updated_from_api"] += 1
        elif action == "skipped_fresh_data":
            report["summary"]["skipped_fresh"] += 1
        elif action == "fallback_to_cache":
            report["summary"]["fallback_to_cache"] += 1
        elif action == "failed_no_data":
            report["summary"]["failed"] += 1
    
    report["api_calls_made"] = api_calls_this_session
    report["api_calls_today_after"] = get_fd_requests_today()
    
    # Sauvegarder le rapport
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Log résumé
    logger.info(f"✅ Mise à jour terminée:")
    logger.info(f"   - Mises à jour API: {report['summary']['updated_from_api']}")
    logger.info(f"   - Données récentes (skip): {report['summary']['skipped_fresh']}")
    logger.info(f"   - Fallback cache: {report['summary']['fallback_to_cache']}")
    logger.info(f"   - Échecs: {report['summary']['failed']}")
    logger.info(f"   - Appels API cette session: {api_calls_this_session}/{max_api_calls}")
    
    return report

# =========================================
# 🧪 TESTS
# =========================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🧪 Test: Mise à jour intelligente des ligues prioritaires")
    report = update_all_leagues_smart(force=False, max_api_calls=5)
    
    print("\n📊 Résumé:")
    print(f"  - Mises à jour API: {report['summary']['updated_from_api']}")
    print(f"  - Données récentes: {report['summary']['skipped_fresh']}")
    print(f"  - Fallback cache: {report['summary']['fallback_to_cache']}")
    print(f"  - Échecs: {report['summary']['failed']}")
    print(f"  - Appels API: {report['api_calls_made']}/{report['api_calls_limit']}")

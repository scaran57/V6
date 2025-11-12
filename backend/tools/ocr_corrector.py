#!/usr/bin/env python3
"""
OCR Corrector - Système de correction automatique des erreurs OCR
Utilise fuzzy-matching avec les données en temps réel des APIs externes
pour corriger les noms d'équipes et ligues mal reconnus.

Architecture multi-source extensible pour supporter plusieurs APIs.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from fuzzywuzzy import process, fuzz

# Import de l'intégration Odds API
from tools.odds_api_integration import (
    load_latest_odds,
    get_ingestion_stats,
    ingest_odds_once
)

# Configuration
DATA_DIR = Path("/app/data")
CORRECTION_LOG_PATH = DATA_DIR / "ocr_corrections.jsonl"
CORRECTION_STATS_PATH = DATA_DIR / "ocr_correction_stats.json"
CACHE_TTL_HOURS = 12  # TTL du cache avant refresh

# Sources de données disponibles (extensible)
SOURCES = ["odds_api"]  # Futur: ["odds_api", "football_data"]

# Seuils de confiance pour les corrections
FUZZY_THRESHOLD_HIGH = 85   # Auto-correction automatique
FUZZY_THRESHOLD_MEDIUM = 70 # Suggestion (log only)
FUZZY_THRESHOLD_LOW = 60    # Alerte manuelle (no action)

# Configuration du logging
logger = logging.getLogger(__name__)
os.makedirs(DATA_DIR, exist_ok=True)


def _write_jsonl(path: Path, obj: dict):
    """Écrit un objet JSON en mode append dans un fichier JSONL"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _load_stats() -> dict:
    """Charge les statistiques de correction depuis le fichier"""
    if not CORRECTION_STATS_PATH.exists():
        return {
            "total_corrections": 0,
            "auto_corrections": 0,
            "suggested_corrections": 0,
            "ignored_corrections": 0,
            "avg_confidence": 0.0,
            "last_update": None
        }
    
    try:
        with open(CORRECTION_STATS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erreur chargement stats: {e}")
        return {}


def _save_stats(stats: dict):
    """Sauvegarde les statistiques de correction"""
    try:
        with open(CORRECTION_STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erreur sauvegarde stats: {e}")


def _update_stats(correction_type: str, confidence: float):
    """Met à jour les statistiques globales de correction"""
    stats = _load_stats()
    
    stats["total_corrections"] = stats.get("total_corrections", 0) + 1
    
    if correction_type == "auto":
        stats["auto_corrections"] = stats.get("auto_corrections", 0) + 1
    elif correction_type == "suggested":
        stats["suggested_corrections"] = stats.get("suggested_corrections", 0) + 1
    else:
        stats["ignored_corrections"] = stats.get("ignored_corrections", 0) + 1
    
    # Moyenne mobile de la confiance
    total = stats["total_corrections"]
    current_avg = stats.get("avg_confidence", 0.0)
    stats["avg_confidence"] = round((current_avg * (total - 1) + confidence) / total, 2)
    stats["last_update"] = datetime.utcnow().isoformat()
    
    _save_stats(stats)


def _log_correction(
    raw_text: str,
    corrected_text: str,
    confidence: float,
    correction_type: str,
    entity_type: str,
    match_hash: Optional[str] = None
):
    """
    Log enrichi d'une correction OCR.
    
    Args:
        raw_text: Texte brut extrait par OCR
        corrected_text: Texte corrigé
        confidence: Score de confiance (0-100)
        correction_type: Type de correction ("auto", "suggested", "ignored")
        entity_type: Type d'entité ("team", "league")
        match_hash: Hash du match pour traçabilité
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "entity_type": entity_type,
        "raw_text": raw_text,
        "corrected_text": corrected_text,
        "confidence_score": round(confidence, 2),
        "correction_type": correction_type,
        "match_hash": match_hash
    }
    
    _write_jsonl(CORRECTION_LOG_PATH, log_entry)
    _update_stats(correction_type, confidence)
    
    logger.info(
        f"📝 Correction OCR [{correction_type.upper()}]: '{raw_text}' → '{corrected_text}' "
        f"(confiance: {confidence:.1f}%)"
    )


def _check_cache_freshness() -> bool:
    """
    Vérifie si le cache Odds API est encore valide (< 12h).
    
    Returns:
        True si le cache est frais, False sinon
    """
    stats = get_ingestion_stats()
    last_update = stats.get("last_update")
    
    if not last_update:
        logger.warning("⚠️ Pas de cache Odds API disponible")
        return False
    
    try:
        last_update_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
        age_hours = (datetime.now(last_update_dt.tzinfo) - last_update_dt).total_seconds() / 3600
        
        if age_hours > CACHE_TTL_HOURS:
            logger.warning(f"⚠️ Cache Odds API obsolète ({age_hours:.1f}h > {CACHE_TTL_HOURS}h)")
            return False
        
        logger.info(f"✅ Cache Odds API frais ({age_hours:.1f}h < {CACHE_TTL_HOURS}h)")
        return True
        
    except Exception as e:
        logger.error(f"Erreur vérification cache: {e}")
        return False


def _refresh_odds_cache_if_needed():
    """
    Rafraîchit le cache Odds API si nécessaire (> 12h).
    """
    if not _check_cache_freshness():
        logger.info("🔄 Rafraîchissement du cache Odds API...")
        try:
            count = ingest_odds_once()
            logger.info(f"✅ Cache rafraîchi: {count} matchs récupérés")
        except Exception as e:
            logger.error(f"❌ Erreur rafraîchissement cache: {e}")


def _get_reference_teams(source: str = "odds_api") -> List[str]:
    """
    Récupère la liste des noms d'équipes de référence depuis une source.
    
    Args:
        source: Source de données ("odds_api", "football_data")
    
    Returns:
        Liste des noms d'équipes normalisés
    """
    if source == "odds_api":
        # Rafraîchir le cache si nécessaire
        _refresh_odds_cache_if_needed()
        
        # Charger les données
        odds_data = load_latest_odds()
        teams = set()
        
        for record in odds_data:
            home = record.get("home_team", "").strip()
            away = record.get("away_team", "").strip()
            if home:
                teams.add(home)
            if away:
                teams.add(away)
        
        logger.info(f"📊 {len(teams)} équipes de référence chargées depuis {source}")
        return list(teams)
    
    # Placeholder pour futures sources
    elif source == "football_data":
        logger.warning("⚠️ Source football_data pas encore implémentée")
        return []
    
    return []


def _get_reference_leagues(source: str = "odds_api") -> List[str]:
    """
    Récupère la liste des noms de ligues de référence depuis une source.
    
    Args:
        source: Source de données ("odds_api", "football_data")
    
    Returns:
        Liste des noms de ligues normalisés
    """
    if source == "odds_api":
        _refresh_odds_cache_if_needed()
        
        odds_data = load_latest_odds()
        leagues = set()
        
        for record in odds_data:
            league = record.get("league_name", "").strip()
            if league:
                leagues.add(league)
        
        logger.info(f"📊 {len(leagues)} ligues de référence chargées depuis {source}")
        return list(leagues)
    
    elif source == "football_data":
        logger.warning("⚠️ Source football_data pas encore implémentée")
        return []
    
    return []


def correct_team_name(
    raw_team: str,
    sources: List[str] = None,
    match_hash: Optional[str] = None
) -> Dict:
    """
    Corrige un nom d'équipe mal reconnu par OCR via fuzzy-matching.
    
    Args:
        raw_team: Nom brut extrait par OCR
        sources: Liste des sources à utiliser (défaut: ["odds_api"])
        match_hash: Hash du match pour traçabilité
    
    Returns:
        Dict avec:
        - corrected: Nom corrigé
        - confidence: Score de confiance (0-100)
        - correction_applied: True si correction appliquée
        - correction_type: "auto", "suggested", "ignored"
        - raw: Nom original
    """
    if sources is None:
        sources = SOURCES
    
    if not raw_team or not raw_team.strip():
        return {
            "corrected": raw_team,
            "confidence": 0.0,
            "correction_applied": False,
            "correction_type": "ignored",
            "raw": raw_team
        }
    
    raw_team_clean = raw_team.strip()
    
    # Agréger les équipes de toutes les sources
    all_teams = []
    for source in sources:
        try:
            teams = _get_reference_teams(source)
            all_teams.extend(teams)
        except Exception as e:
            logger.error(f"Erreur récupération équipes depuis {source}: {e}")
    
    if not all_teams:
        logger.warning("⚠️ Aucune équipe de référence disponible")
        return {
            "corrected": raw_team_clean,
            "confidence": 0.0,
            "correction_applied": False,
            "correction_type": "ignored",
            "raw": raw_team_clean
        }
    
    # Fuzzy matching
    best_match = process.extractOne(raw_team_clean, all_teams, scorer=fuzz.token_sort_ratio)
    
    if not best_match:
        return {
            "corrected": raw_team_clean,
            "confidence": 0.0,
            "correction_applied": False,
            "correction_type": "ignored",
            "raw": raw_team_clean
        }
    
    matched_name, confidence = best_match[0], best_match[1]
    
    # Déterminer le type de correction
    if confidence >= FUZZY_THRESHOLD_HIGH:
        correction_type = "auto"
        corrected = matched_name
        applied = True
    elif confidence >= FUZZY_THRESHOLD_MEDIUM:
        correction_type = "suggested"
        corrected = matched_name
        applied = False  # Log seulement, pas de correction automatique
    else:
        correction_type = "ignored"
        corrected = raw_team_clean
        applied = False
    
    # Logger la correction
    _log_correction(
        raw_text=raw_team_clean,
        corrected_text=corrected,
        confidence=confidence,
        correction_type=correction_type,
        entity_type="team",
        match_hash=match_hash
    )
    
    return {
        "corrected": corrected if applied else raw_team_clean,
        "confidence": confidence,
        "correction_applied": applied,
        "correction_type": correction_type,
        "raw": raw_team_clean,
        "suggested": matched_name if correction_type == "suggested" else None
    }


def correct_league_name(
    raw_league: str,
    sources: List[str] = None,
    match_hash: Optional[str] = None
) -> Dict:
    """
    Corrige un nom de ligue mal reconnu par OCR via fuzzy-matching.
    
    Args:
        raw_league: Nom brut extrait par OCR
        sources: Liste des sources à utiliser (défaut: ["odds_api"])
        match_hash: Hash du match pour traçabilité
    
    Returns:
        Dict avec:
        - corrected: Nom corrigé
        - confidence: Score de confiance (0-100)
        - correction_applied: True si correction appliquée
        - correction_type: "auto", "suggested", "ignored"
        - raw: Nom original
    """
    if sources is None:
        sources = SOURCES
    
    if not raw_league or not raw_league.strip() or raw_league.strip().lower() == "unknown":
        return {
            "corrected": raw_league,
            "confidence": 0.0,
            "correction_applied": False,
            "correction_type": "ignored",
            "raw": raw_league
        }
    
    raw_league_clean = raw_league.strip()
    
    # Agréger les ligues de toutes les sources
    all_leagues = []
    for source in sources:
        try:
            leagues = _get_reference_leagues(source)
            all_leagues.extend(leagues)
        except Exception as e:
            logger.error(f"Erreur récupération ligues depuis {source}: {e}")
    
    if not all_leagues:
        logger.warning("⚠️ Aucune ligue de référence disponible")
        return {
            "corrected": raw_league_clean,
            "confidence": 0.0,
            "correction_applied": False,
            "correction_type": "ignored",
            "raw": raw_league_clean
        }
    
    # Fuzzy matching
    best_match = process.extractOne(raw_league_clean, all_leagues, scorer=fuzz.token_sort_ratio)
    
    if not best_match:
        return {
            "corrected": raw_league_clean,
            "confidence": 0.0,
            "correction_applied": False,
            "correction_type": "ignored",
            "raw": raw_league_clean
        }
    
    matched_name, confidence = best_match[0], best_match[1]
    
    # Déterminer le type de correction
    if confidence >= FUZZY_THRESHOLD_HIGH:
        correction_type = "auto"
        corrected = matched_name
        applied = True
    elif confidence >= FUZZY_THRESHOLD_MEDIUM:
        correction_type = "suggested"
        corrected = matched_name
        applied = False
    else:
        correction_type = "ignored"
        corrected = raw_league_clean
        applied = False
    
    # Logger la correction
    _log_correction(
        raw_text=raw_league_clean,
        corrected_text=corrected,
        confidence=confidence,
        correction_type=correction_type,
        entity_type="league",
        match_hash=match_hash
    )
    
    return {
        "corrected": corrected if applied else raw_league_clean,
        "confidence": confidence,
        "correction_applied": applied,
        "correction_type": correction_type,
        "raw": raw_league_clean,
        "suggested": matched_name if correction_type == "suggested" else None
    }


def correct_match_info(
    home_team: Optional[str],
    away_team: Optional[str],
    league: Optional[str],
    sources: List[str] = None,
    match_hash: Optional[str] = None
) -> Dict:
    """
    Corrige toutes les informations d'un match (équipes + ligue).
    
    Args:
        home_team: Équipe à domicile (OCR brut)
        away_team: Équipe à l'extérieur (OCR brut)
        league: Ligue (OCR brut)
        sources: Liste des sources à utiliser
        match_hash: Hash du match pour traçabilité
    
    Returns:
        Dict avec:
        - home_team: Équipe à domicile corrigée
        - away_team: Équipe à l'extérieur corrigée
        - league: Ligue corrigée
        - corrections_applied: Nombre de corrections appliquées
        - details: Détails de chaque correction
    """
    if sources is None:
        sources = SOURCES
    
    # Corriger chaque entité
    home_result = correct_team_name(home_team, sources, match_hash) if home_team else None
    away_result = correct_team_name(away_team, sources, match_hash) if away_team else None
    league_result = correct_league_name(league, sources, match_hash) if league else None
    
    # Compter les corrections appliquées
    corrections_count = sum([
        home_result.get("correction_applied", False) if home_result else False,
        away_result.get("correction_applied", False) if away_result else False,
        league_result.get("correction_applied", False) if league_result else False
    ])
    
    return {
        "home_team": home_result.get("corrected") if home_result else home_team,
        "away_team": away_result.get("corrected") if away_result else away_team,
        "league": league_result.get("corrected") if league_result else league,
        "corrections_applied": corrections_count,
        "details": {
            "home_team": home_result,
            "away_team": away_result,
            "league": league_result
        }
    }


def get_correction_stats() -> Dict:
    """
    Récupère les statistiques globales de correction.
    
    Returns:
        Dict avec:
        - total_corrections: Nombre total de corrections
        - auto_corrections: Corrections automatiques
        - suggested_corrections: Suggestions (non appliquées)
        - ignored_corrections: Corrections ignorées
        - avg_confidence: Confiance moyenne
        - last_update: Dernière mise à jour
    """
    return _load_stats()


def get_recent_corrections(limit: int = 50) -> List[Dict]:
    """
    Récupère les dernières corrections effectuées.
    
    Args:
        limit: Nombre maximum de corrections à retourner
    
    Returns:
        Liste des corrections récentes
    """
    if not CORRECTION_LOG_PATH.exists():
        return []
    
    corrections = []
    try:
        with open(CORRECTION_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    corrections.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"Erreur lecture log corrections: {e}")
    
    # Retourner les plus récentes en premier
    return corrections[-limit:][::-1]


# Test unitaire simple
if __name__ == "__main__":
    print("=" * 70)
    print("TEST OCR CORRECTOR - Fuzzy Matching")
    print("=" * 70)
    print()
    
    # Test 1: Texte exact (pas de correction)
    print("📝 Test 1: Texte exact")
    result1 = correct_team_name("Real Madrid")
    print(f"   Entrée: 'Real Madrid'")
    print(f"   Résultat: {result1['corrected']}")
    print(f"   Confiance: {result1['confidence']:.1f}%")
    print(f"   Type: {result1['correction_type']}")
    print()
    
    # Test 2: OCR bruité (correction auto)
    print("📝 Test 2: OCR bruité")
    result2 = correct_team_name("Mnachester Untd")
    print(f"   Entrée: 'Mnachester Untd'")
    print(f"   Résultat: {result2['corrected']}")
    print(f"   Confiance: {result2['confidence']:.1f}%")
    print(f"   Type: {result2['correction_type']}")
    print()
    
    # Test 3: Texte hors domaine (pas de correction)
    print("📝 Test 3: Texte hors domaine")
    result3 = correct_team_name("Équipe Inconnue XYZ")
    print(f"   Entrée: 'Équipe Inconnue XYZ'")
    print(f"   Résultat: {result3['corrected']}")
    print(f"   Confiance: {result3['confidence']:.1f}%")
    print(f"   Type: {result3['correction_type']}")
    print()
    
    # Stats
    print("=" * 70)
    print("📊 Statistiques")
    stats = get_correction_stats()
    print(f"   Total corrections: {stats.get('total_corrections', 0)}")
    print(f"   Auto: {stats.get('auto_corrections', 0)}")
    print(f"   Suggested: {stats.get('suggested_corrections', 0)}")
    print(f"   Ignored: {stats.get('ignored_corrections', 0)}")
    print(f"   Confiance moyenne: {stats.get('avg_confidence', 0):.1f}%")
    print("=" * 70)

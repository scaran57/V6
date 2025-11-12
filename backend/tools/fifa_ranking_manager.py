#!/usr/bin/env python3
"""
FIFA Ranking Manager - Gestion du classement FIFA et calcul des coefficients
Système ajustable pour mettre à jour facilement le classement via photos OCR.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from fuzzywuzzy import process, fuzz

logger = logging.getLogger(__name__)

# Chemins des fichiers
FIFA_RANKING_FILE = Path("/app/data/fifa_ranking.json")
FIFA_RANKING_BACKUP = Path("/app/data/fifa_ranking_backup.json")

# Coefficients par tranche de classement
COEFFICIENT_TIERS = [
    (1, 10, 1.5),      # Top 10: Très forte équipe
    (11, 30, 1.3),     # 11-30: Forte équipe
    (31, 60, 1.2),     # 31-60: Équipe moyenne-forte
    (61, 100, 1.1),    # 61-100: Équipe moyenne
    (101, 150, 1.05),  # 101-150: Équipe faible
    (151, 999, 1.0)    # 150+: Très faible équipe
]


def load_fifa_ranking() -> Dict:
    """
    Charge le classement FIFA depuis le fichier JSON.
    
    Returns:
        Dict avec le classement complet
    """
    if not FIFA_RANKING_FILE.exists():
        logger.error(f"❌ Fichier FIFA ranking introuvable : {FIFA_RANKING_FILE}")
        return {"rankings": {}, "name_mappings": {}}
    
    try:
        with open(FIFA_RANKING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ Classement FIFA chargé : {data.get('total_teams', 0)} équipes")
        return data
    
    except Exception as e:
        logger.error(f"❌ Erreur chargement FIFA ranking : {e}")
        return {"rankings": {}, "name_mappings": {}}


def save_fifa_ranking(data: Dict) -> bool:
    """
    Sauvegarde le classement FIFA dans le fichier JSON.
    Crée automatiquement un backup de l'ancien fichier.
    
    Args:
        data: Données du classement à sauvegarder
    
    Returns:
        True si succès, False sinon
    """
    try:
        # Backup de l'ancien fichier
        if FIFA_RANKING_FILE.exists():
            import shutil
            shutil.copy(FIFA_RANKING_FILE, FIFA_RANKING_BACKUP)
            logger.info(f"📦 Backup créé : {FIFA_RANKING_BACKUP}")
        
        # Sauvegarder le nouveau
        with open(FIFA_RANKING_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Classement FIFA sauvegardé : {data.get('total_teams', 0)} équipes")
        return True
    
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde FIFA ranking : {e}")
        return False


def get_team_code(team_name: str, ranking_data: Optional[Dict] = None) -> Optional[str]:
    """
    Récupère le code FIFA d'une équipe via fuzzy matching.
    
    Args:
        team_name: Nom de l'équipe (français ou anglais)
        ranking_data: Données du ranking (optionnel, rechargé si None)
    
    Returns:
        Code FIFA (ex: "FRA", "NOR") ou None si non trouvé
    """
    if not ranking_data:
        ranking_data = load_fifa_ranking()
    
    if not team_name:
        return None
    
    team_name_clean = team_name.strip()
    
    # 1. Recherche exacte dans les mappings
    mappings = ranking_data.get("name_mappings", {})
    if team_name_clean in mappings:
        return mappings[team_name_clean]
    
    # 2. Recherche dans les codes (ex: "FRA" direct)
    rankings = ranking_data.get("rankings", {})
    if team_name_clean.upper() in rankings:
        return team_name_clean.upper()
    
    # 3. Fuzzy matching sur tous les noms possibles
    all_names = list(mappings.keys())
    for code, team_data in rankings.items():
        all_names.append(team_data.get("name", ""))
        all_names.append(team_data.get("name_fr", ""))
    
    match = process.extractOne(team_name_clean, all_names, scorer=fuzz.token_sort_ratio)
    
    if match and match[1] >= 75:  # Seuil de confiance 75%
        matched_name = match[0]
        
        # Trouver le code correspondant
        if matched_name in mappings:
            logger.info(f"🔍 Fuzzy match: '{team_name}' → '{matched_name}' ({match[1]}%)")
            return mappings[matched_name]
        
        # Chercher dans les rankings
        for code, team_data in rankings.items():
            if matched_name in [team_data.get("name"), team_data.get("name_fr")]:
                logger.info(f"🔍 Fuzzy match: '{team_name}' → '{matched_name}' ({match[1]}%)")
                return code
    
    logger.warning(f"⚠️ Équipe non trouvée dans FIFA ranking : '{team_name}'")
    return None


def get_team_rank(team_name: str, ranking_data: Optional[Dict] = None) -> int:
    """
    Récupère le rang FIFA d'une équipe.
    
    Args:
        team_name: Nom de l'équipe
        ranking_data: Données du ranking (optionnel)
    
    Returns:
        Rang FIFA (1-999), ou 999 si non trouvé
    """
    if not ranking_data:
        ranking_data = load_fifa_ranking()
    
    code = get_team_code(team_name, ranking_data)
    
    if code:
        rankings = ranking_data.get("rankings", {})
        team_data = rankings.get(code)
        if team_data:
            return team_data.get("rank", 999)
    
    return 999  # Rang par défaut si non trouvé


def get_team_points(team_name: str, ranking_data: Optional[Dict] = None) -> float:
    """
    Récupère les points FIFA d'une équipe.
    
    Args:
        team_name: Nom de l'équipe
        ranking_data: Données du ranking (optionnel)
    
    Returns:
        Points FIFA, ou 1000.0 si non trouvé
    """
    if not ranking_data:
        ranking_data = load_fifa_ranking()
    
    code = get_team_code(team_name, ranking_data)
    
    if code:
        rankings = ranking_data.get("rankings", {})
        team_data = rankings.get(code)
        if team_data:
            return team_data.get("points", 1000.0)
    
    return 1000.0  # Points par défaut


def calculate_coefficient_from_rank(rank: int) -> float:
    """
    Calcule le coefficient de performance basé sur le rang FIFA.
    
    Tranches:
    - Rang 1-10: 1.5
    - Rang 11-30: 1.3
    - Rang 31-60: 1.2
    - Rang 61-100: 1.1
    - Rang 101-150: 1.05
    - Rang 150+: 1.0
    
    Args:
        rank: Rang FIFA
    
    Returns:
        Coefficient (1.0 à 1.5)
    """
    for min_rank, max_rank, coeff in COEFFICIENT_TIERS:
        if min_rank <= rank <= max_rank:
            return coeff
    
    return 1.0  # Par défaut


def get_team_coefficient(team_name: str, ranking_data: Optional[Dict] = None) -> float:
    """
    Récupère le coefficient FIFA d'une équipe.
    
    Args:
        team_name: Nom de l'équipe
        ranking_data: Données du ranking (optionnel)
    
    Returns:
        Coefficient (1.0 à 1.5)
    """
    rank = get_team_rank(team_name, ranking_data)
    coeff = calculate_coefficient_from_rank(rank)
    
    logger.debug(f"📊 {team_name}: Rang {rank} → Coefficient {coeff}")
    
    return coeff


def get_match_coefficients(
    home_team: str,
    away_team: str,
    ranking_data: Optional[Dict] = None
) -> Tuple[float, float, float]:
    """
    Calcule les coefficients pour un match et le ratio domicile/extérieur.
    
    Args:
        home_team: Équipe à domicile
        away_team: Équipe à l'extérieur
        ranking_data: Données du ranking (optionnel)
    
    Returns:
        Tuple (coeff_home, coeff_away, ratio_home_away)
    """
    if not ranking_data:
        ranking_data = load_fifa_ranking()
    
    coeff_home = get_team_coefficient(home_team, ranking_data)
    coeff_away = get_team_coefficient(away_team, ranking_data)
    
    # Ratio pour ajuster les probabilités
    # ratio > 1 = domicile favorisé
    # ratio < 1 = extérieur favorisé
    ratio = coeff_home / coeff_away if coeff_away > 0 else 1.0
    
    logger.info(f"⚽ Match: {home_team} ({coeff_home:.2f}) vs {away_team} ({coeff_away:.2f}) → Ratio: {ratio:.2f}")
    
    return coeff_home, coeff_away, ratio


def get_all_coefficients(ranking_data: Optional[Dict] = None) -> Dict[str, float]:
    """
    Génère un dictionnaire de tous les coefficients pour toutes les équipes.
    
    Args:
        ranking_data: Données du ranking (optionnel)
    
    Returns:
        Dict {nom_équipe: coefficient}
    """
    if not ranking_data:
        ranking_data = load_fifa_ranking()
    
    coefficients = {}
    
    rankings = ranking_data.get("rankings", {})
    for code, team_data in rankings.items():
        rank = team_data.get("rank", 999)
        coeff = calculate_coefficient_from_rank(rank)
        
        # Ajouter avec différents noms
        name_en = team_data.get("name", "")
        name_fr = team_data.get("name_fr", "")
        
        if name_en:
            coefficients[name_en] = coeff
        if name_fr:
            coefficients[name_fr] = coeff
        coefficients[code] = coeff
    
    logger.info(f"📊 {len(coefficients)} coefficients générés")
    
    return coefficients


def get_ranking_stats() -> Dict:
    """
    Récupère les statistiques du classement FIFA.
    
    Returns:
        Dict avec stats (total équipes, dernière MAJ, etc.)
    """
    ranking_data = load_fifa_ranking()
    
    return {
        "total_teams": ranking_data.get("total_teams", 0),
        "last_updated": ranking_data.get("last_updated", "Unknown"),
        "source": ranking_data.get("source", "Unknown"),
        "file_path": str(FIFA_RANKING_FILE),
        "file_exists": FIFA_RANKING_FILE.exists()
    }


# Test du module
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("TEST FIFA RANKING MANAGER")
    print("=" * 70)
    print()
    
    # Test 1: Chargement
    print("📥 Test 1: Chargement du classement")
    ranking = load_fifa_ranking()
    print(f"   Total équipes: {ranking.get('total_teams', 0)}")
    print()
    
    # Test 2: Recherche d'équipe
    print("🔍 Test 2: Recherche d'équipes")
    teams_to_test = ["France", "Norvège", "Norway", "Estonia", "Estonie", "Spain"]
    for team in teams_to_test:
        code = get_team_code(team, ranking)
        rank = get_team_rank(team, ranking)
        coeff = get_team_coefficient(team, ranking)
        print(f"   {team:15} → Code: {code}, Rang: {rank:3}, Coeff: {coeff:.2f}")
    print()
    
    # Test 3: Match coefficients
    print("⚽ Test 3: Coefficients de match")
    matches = [
        ("France", "Estonie"),
        ("Norvège", "Estonia"),
        ("Spain", "Norway")
    ]
    for home, away in matches:
        coeff_h, coeff_a, ratio = get_match_coefficients(home, away, ranking)
        print(f"   {home} vs {away}: Ratio = {ratio:.2f}")
    print()
    
    # Test 4: Stats
    print("📊 Test 4: Statistiques")
    stats = get_ranking_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print()
    print("=" * 70)

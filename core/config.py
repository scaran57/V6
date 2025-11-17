"""
Module de gestion de configuration des paramètres par ligue
Lecture/écriture thread-safe du fichier leagues_params.json
"""
import json
from pathlib import Path
from threading import RLock
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = Path("/app/config/leagues_params.json")
_lock = RLock()

def _load():
    """Charge la configuration depuis le fichier JSON"""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Configuration par défaut
        default_config = {
            "default": {
                "diffExpected": 2.1380,
                "base_expected": 1.4,
                "coeff_min": 0.85,
                "coeff_max": 1.30,
                "coeff_home": 1.0,
                "coeff_away": 1.0
            }
        }
        CONFIG_FILE.write_text(json.dumps(default_config, indent=2))
        return default_config
    
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        logger.error(f"Erreur lecture config: {e}")
        return {}

def get_league_params(league_name: str) -> dict:
    """
    Récupère les paramètres d'une ligue spécifique
    
    Args:
        league_name: Nom de la ligue (ex: "LaLiga", "PremierLeague")
    
    Returns:
        dict: Paramètres de la ligue ou None si non trouvée
    """
    with _lock:
        data = _load()
        params = data.get(league_name)
        
        if params:
            logger.info(f"📋 Paramètres chargés pour {league_name}: diffExpected={params.get('diffExpected')}")
        else:
            logger.warning(f"⚠️ Aucun paramètre trouvé pour {league_name}, utilisation des valeurs par défaut")
            # Retourner les paramètres par défaut
            params = data.get("default", {
                "diffExpected": 2.1380,
                "base_expected": 1.4,
                "coeff_min": 0.85,
                "coeff_max": 1.30,
                "coeff_home": 1.0,
                "coeff_away": 1.0
            })
        
        return params

def set_league_params(league_name: str, params: dict):
    """
    Définit tous les paramètres d'une ligue
    
    Args:
        league_name: Nom de la ligue
        params: Dictionnaire complet des paramètres
    """
    with _lock:
        data = _load()
        data[league_name] = params
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info(f"✅ Paramètres mis à jour pour {league_name}")

def update_league_param(league_name: str, key: str, value):
    """
    Met à jour un paramètre spécifique d'une ligue
    
    Args:
        league_name: Nom de la ligue
        key: Nom du paramètre (ex: "diffExpected")
        value: Nouvelle valeur
    """
    with _lock:
        data = _load()
        league = data.get(league_name, {})
        
        old_value = league.get(key)
        league[key] = value
        data[league_name] = league
        
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info(f"✅ {league_name}.{key}: {old_value} → {value}")

def get_all_leagues() -> list:
    """Retourne la liste de toutes les ligues configurées"""
    with _lock:
        data = _load()
        return [k for k in data.keys() if k != "default"]

def get_all_params() -> dict:
    """Retourne tous les paramètres de toutes les ligues"""
    with _lock:
        return _load()

def reset_league_to_default(league_name: str):
    """Réinitialise une ligue aux paramètres par défaut"""
    with _lock:
        data = _load()
        default = data.get("default", {})
        data[league_name] = default.copy()
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info(f"🔄 {league_name} réinitialisée aux valeurs par défaut")

# Test du module
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*70)
    print("TEST MODULE CONFIG")
    print("="*70)
    
    # Test 1: Récupérer paramètres LaLiga
    print("\n1. Récupération LaLiga:")
    params = get_league_params("LaLiga")
    print(f"   diffExpected: {params.get('diffExpected')}")
    print(f"   base_expected: {params.get('base_expected')}")
    
    # Test 2: Mettre à jour un paramètre
    print("\n2. Mise à jour diffExpected:")
    update_league_param("LaLiga", "diffExpected", 2.5)
    params = get_league_params("LaLiga")
    print(f"   Nouveau diffExpected: {params.get('diffExpected')}")
    
    # Test 3: Lister toutes les ligues
    print("\n3. Toutes les ligues:")
    leagues = get_all_leagues()
    print(f"   {len(leagues)} ligues: {', '.join(leagues[:5])}...")
    
    # Test 4: Réinitialiser
    print("\n4. Réinitialisation LaLiga:")
    reset_league_to_default("LaLiga")
    params = get_league_params("LaLiga")
    print(f"   diffExpected après reset: {params.get('diffExpected')}")

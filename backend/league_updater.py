# /app/backend/league_updater.py
"""
Orchestrateur pour la mise à jour de toutes les ligues.
Gère la mise à jour séquentielle de tous les classements.
"""
import logging
import sys
sys.path.insert(0, '/app/backend')

import league_fetcher
import league_coeff

logger = logging.getLogger(__name__)

def update_all_leagues(force=False):
    """
    Met à jour tous les classements de toutes les ligues disponibles.
    
    Args:
        force: Si True, force la mise à jour même si le cache est valide
    
    Returns:
        dict: Résultats de mise à jour pour chaque ligue
    """
    logger.info("🔄 Début de la mise à jour de toutes les ligues...")
    
    results = {}
    all_leagues = list(league_fetcher.LEAGUE_CONFIG.keys())
    
    for league in all_leagues:
        try:
            logger.info(f"📊 Mise à jour de {league}...")
            standings = league_fetcher.update_league(league, force=force)
            
            if standings:
                results[league] = {
                    "success": True,
                    "teams_count": len(standings),
                    "message": f"✅ {league} mis à jour avec {len(standings)} équipes"
                }
                logger.info(results[league]["message"])
            else:
                results[league] = {
                    "success": False,
                    "teams_count": 0,
                    "message": f"⚠️ {league} - Aucune donnée récupérée"
                }
                logger.warning(results[league]["message"])
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la mise à jour de {league}: {e}")
            results[league] = {
                "success": False,
                "error": str(e),
                "message": f"❌ {league} - Erreur: {e}"
            }
    
    # Vider le cache des coefficients pour forcer le recalcul
    try:
        league_coeff.clear_cache()
        logger.info("✅ Cache des coefficients vidé - les nouveaux classements seront utilisés")
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors du vidage du cache des coefficients: {e}")
    
    # Résumé
    successful = sum(1 for r in results.values() if r.get("success"))
    failed = len(results) - successful
    
    logger.info(f"✅ Mise à jour terminée: {successful} ligues réussies, {failed} échouées")
    
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "successful": successful,
            "failed": failed
        }
    }

def update_single_league(league_name, force=False):
    """
    Met à jour une seule ligue.
    
    Args:
        league_name: Nom de la ligue à mettre à jour
        force: Si True, force la mise à jour même si le cache est valide
    
    Returns:
        dict: Résultat de la mise à jour
    """
    try:
        logger.info(f"🔄 Mise à jour de {league_name}...")
        standings = league_fetcher.update_league(league_name, force=force)
        
        if standings:
            # Vider le cache des coefficients pour cette ligue
            try:
                league_coeff.clear_cache()
                logger.info("✅ Cache des coefficients vidé")
            except Exception as e:
                logger.warning(f"⚠️ Erreur vidage cache: {e}")
            
            return {
                "success": True,
                "league": league_name,
                "teams_count": len(standings),
                "message": f"✅ {league_name} mis à jour avec {len(standings)} équipes"
            }
        else:
            return {
                "success": False,
                "league": league_name,
                "teams_count": 0,
                "message": f"⚠️ {league_name} - Aucune donnée récupérée"
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour {league_name}: {e}")
        return {
            "success": False,
            "league": league_name,
            "error": str(e),
            "message": f"❌ {league_name} - Erreur: {e}"
        }

def get_available_leagues():
    """
    Retourne la liste des ligues disponibles.
    
    Returns:
        list: Liste des noms de ligues
    """
    return list(league_fetcher.LEAGUE_CONFIG.keys())

def get_league_info(league_name):
    """
    Récupère les informations d'une ligue.
    
    Args:
        league_name: Nom de la ligue
    
    Returns:
        dict: Informations de la ligue (URL, méthode, etc.)
    """
    config = league_fetcher.LEAGUE_CONFIG.get(league_name)
    if not config:
        return None
    
    # Charger les données actuelles
    data = league_fetcher.load_league_data(league_name)
    
    return {
        "name": league_name,
        "url": config["url"],
        "method": config["method"],
        "data_file": config["fallback_file"],
        "has_data": data is not None,
        "teams_count": len(data.get("teams", [])) if data else 0,
        "last_update": data.get("updated") if data else None
    }

if __name__ == "__main__":
    # Test de mise à jour
    import argparse
    
    parser = argparse.ArgumentParser(description="Met à jour les classements des ligues")
    parser.add_argument("--league", type=str, help="Nom de la ligue à mettre à jour (ou 'all')")
    parser.add_argument("--force", action="store_true", help="Forcer la mise à jour")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.league and args.league.lower() != "all":
        result = update_single_league(args.league, force=args.force)
        print(result["message"])
    else:
        results = update_all_leagues(force=args.force)
        print("\n=== RÉSUMÉ ===")
        for league, result in results["results"].items():
            print(result["message"])
        print(f"\nTotal: {results['summary']['successful']}/{results['summary']['total']} réussies")

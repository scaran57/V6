"""
Système d'apprentissage automatique pour l'ajustement des paramètres
Ajuste diffExpected par ligue en fonction des résultats réels
"""
import logging
from typing import List, Dict, Tuple
import statistics
from datetime import datetime, timedelta
import sys

logger = logging.getLogger(__name__)

sys.path.insert(0, '/app/backend')

from core.models import SessionLocal, AnalysisResult, LearningEvent
from core.config import get_league_params, update_league_param

def calculate_score_difference(score: str) -> int:
    """
    Calcule la différence de buts dans un score
    
    Args:
        score: Format "2-1" ou "1-1"
    
    Returns:
        int: Différence absolue de buts
    """
    try:
        home, away = map(int, score.split('-'))
        return abs(home - away)
    except:
        return 0

def calculate_adjustment(predicted_score: str, real_score: str) -> float:
    """
    Calcule l'ajustement nécessaire pour diffExpected
    
    Logique:
    - Si réel > prédit → augmenter diffExpected
    - Si réel < prédit → diminuer diffExpected
    - Si égal → légère réduction (régularisation)
    
    Args:
        predicted_score: Score prédit (ex: "2-1")
        real_score: Score réel (ex: "3-0")
    
    Returns:
        float: Ajustement à appliquer
    """
    try:
        pred_diff = calculate_score_difference(predicted_score)
        real_diff = calculate_score_difference(real_score)
        
        # Écart entre réel et prédit
        error = real_diff - pred_diff
        
        # Facteur d'apprentissage progressif
        learning_rate = 0.1
        
        # Ajustement proportionnel à l'erreur
        adjustment = error * learning_rate
        
        logger.debug(f"📊 Calcul ajustement: prédit={predicted_score} (diff={pred_diff}), "
                    f"réel={real_score} (diff={real_diff}) → ajustement={adjustment:.4f}")
        
        return adjustment
        
    except Exception as e:
        logger.error(f"❌ Erreur calcul ajustement: {e}")
        return 0.0

def learn_from_match(
    league: str,
    predicted_score: str,
    real_score: str,
    home_team: str = None,
    away_team: str = None,
    analysis_id: int = None,
    source: str = "manual"
) -> Dict:
    """
    Apprend d'un match et ajuste diffExpected pour la ligue
    
    Args:
        league: Nom de la ligue
        predicted_score: Score prédit
        real_score: Score réel
        home_team: Équipe domicile (optionnel)
        away_team: Équipe extérieur (optionnel)
        analysis_id: ID de l'analyse associée (optionnel)
        source: Source de l'apprentissage ('manual', 'automatic')
    
    Returns:
        dict: Résultat de l'apprentissage
    """
    logger.info(f"🎓 Apprentissage: {league} - {predicted_score} vs {real_score}")
    
    try:
        # Récupérer les paramètres actuels
        params = get_league_params(league)
        if not params:
            logger.error(f"❌ Paramètres non trouvés pour {league}")
            return {"success": False, "error": "League parameters not found"}
        
        current_diff = params.get('diffExpected', 2.1380)
        
        # Calculer l'ajustement
        adjustment = calculate_adjustment(predicted_score, real_score)
        
        # Nouvelle valeur avec contraintes
        new_diff = current_diff + adjustment
        
        # Limites pour éviter des valeurs extrêmes
        new_diff = max(0.5, min(new_diff, 5.0))
        
        # Mettre à jour le paramètre
        update_league_param(league, 'diffExpected', new_diff)
        
        # Enregistrer l'événement d'apprentissage en DB
        db = SessionLocal()
        try:
            event = LearningEvent(
                analysis_id=analysis_id,
                league=league,
                home_team=home_team,
                away_team=away_team,
                predicted_score=predicted_score,
                real_score=real_score,
                diff_expected_before=current_diff,
                diff_expected_after=new_diff,
                adjustment=adjustment,
                source=source
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            
            logger.info(f"✅ Apprentissage enregistré: {current_diff:.4f} → {new_diff:.4f} (Δ={adjustment:+.4f})")
            
            return {
                "success": True,
                "league": league,
                "diff_expected_before": current_diff,
                "diff_expected_after": new_diff,
                "adjustment": adjustment,
                "event_id": event.id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur apprentissage: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def batch_learning(matches: List[Dict]) -> Dict:
    """
    Apprentissage par batch sur plusieurs matchs
    
    Args:
        matches: Liste de dicts avec keys: league, predicted_score, real_score, home_team, away_team
    
    Returns:
        dict: Résumé de l'apprentissage par ligue
    """
    logger.info(f"🎓 Apprentissage batch: {len(matches)} matchs")
    
    results = {}
    
    for match in matches:
        league = match.get('league')
        predicted = match.get('predicted_score')
        real = match.get('real_score')
        
        if not (league and predicted and real):
            logger.warning(f"⚠️ Match incomplet, ignoré: {match}")
            continue
        
        result = learn_from_match(
            league=league,
            predicted_score=predicted,
            real_score=real,
            home_team=match.get('home_team'),
            away_team=match.get('away_team'),
            analysis_id=match.get('analysis_id'),
            source=match.get('source', 'batch')
        )
        
        if result.get('success'):
            if league not in results:
                results[league] = {
                    'count': 0,
                    'total_adjustment': 0,
                    'final_diff': None
                }
            
            results[league]['count'] += 1
            results[league]['total_adjustment'] += result.get('adjustment', 0)
            results[league]['final_diff'] = result.get('diff_expected_after')
    
    logger.info(f"✅ Apprentissage batch terminé: {len(results)} ligues mises à jour")
    
    return results

def update_learning_from_confirmed_matches(days_back: int = 7):
    """
    Met à jour l'apprentissage depuis les analyses confirmées
    Parcourt les analyses récentes avec scores réels confirmés
    
    Args:
        days_back: Nombre de jours à regarder en arrière
    
    Returns:
        dict: Résumé de la mise à jour
    """
    logger.info(f"🔍 Recherche analyses confirmées ({days_back} derniers jours)...")
    
    db = SessionLocal()
    try:
        # Date limite
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Récupérer analyses avec scores réels confirmés
        analyses = db.query(AnalysisResult)\
            .filter(AnalysisResult.real_score_confirmed == True)\
            .filter(AnalysisResult.created_at >= cutoff_date)\
            .all()
        
        logger.info(f"📊 {len(analyses)} analyses confirmées trouvées")
        
        if not analyses:
            return {"success": True, "count": 0, "message": "Aucune analyse confirmée"}
        
        # Préparer les matchs pour apprentissage batch
        matches = []
        
        for analysis in analyses:
            # Vérifier si déjà utilisé pour apprentissage
            existing_event = db.query(LearningEvent)\
                .filter(LearningEvent.analysis_id == analysis.id)\
                .first()
            
            if existing_event:
                logger.debug(f"⏭️ Analyse {analysis.id} déjà utilisée pour apprentissage, ignorée")
                continue
            
            # Extraire les infos de l'analyse
            league = analysis.league_used
            predicted = analysis.most_probable_score
            real = analysis.real_score
            
            # Essayer de récupérer les équipes depuis les images liées
            home_team = None
            away_team = None
            if analysis.images:
                img = analysis.images[0]
                home_team = img.home_team
                away_team = img.away_team
            
            if league and predicted and real:
                matches.append({
                    'league': league,
                    'predicted_score': predicted,
                    'real_score': real,
                    'home_team': home_team,
                    'away_team': away_team,
                    'analysis_id': analysis.id,
                    'source': 'automatic'
                })
        
        logger.info(f"🎯 {len(matches)} nouveaux matchs pour apprentissage")
        
        if not matches:
            return {"success": True, "count": 0, "message": "Aucun nouveau match à apprendre"}
        
        # Lancer l'apprentissage batch
        results = batch_learning(matches)
        
        return {
            "success": True,
            "count": len(matches),
            "leagues_updated": len(results),
            "details": results
        }
        
    finally:
        db.close()

def get_learning_stats(league: str = None, days: int = 30) -> Dict:
    """
    Récupère les statistiques d'apprentissage
    
    Args:
        league: Filtrer par ligue (optionnel)
        days: Nombre de jours à analyser
    
    Returns:
        dict: Statistiques d'apprentissage
    """
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(LearningEvent)\
            .filter(LearningEvent.created_at >= cutoff_date)
        
        if league:
            query = query.filter(LearningEvent.league == league)
        
        events = query.all()
        
        if not events:
            return {"count": 0, "message": "Aucun événement d'apprentissage"}
        
        # Statistiques globales
        adjustments = [e.adjustment for e in events if e.adjustment is not None]
        
        stats = {
            "count": len(events),
            "period_days": days,
            "avg_adjustment": statistics.mean(adjustments) if adjustments else 0,
            "total_adjustment": sum(adjustments) if adjustments else 0,
            "by_league": {}
        }
        
        # Stats par ligue
        leagues = set(e.league for e in events)
        for lg in leagues:
            lg_events = [e for e in events if e.league == lg]
            lg_adjustments = [e.adjustment for e in lg_events if e.adjustment is not None]
            
            if lg_adjustments:
                stats["by_league"][lg] = {
                    "count": len(lg_events),
                    "avg_adjustment": statistics.mean(lg_adjustments),
                    "total_adjustment": sum(lg_adjustments),
                    "current_diff": get_league_params(lg).get('diffExpected', 0)
                }
        
        return stats
        
    finally:
        db.close()

# Test du module
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    print("="*70)
    print("TEST SYSTÈME D'APPRENTISSAGE")
    print("="*70)
    
    # Test 1: Apprentissage simple
    print("\n1️⃣ Test apprentissage simple:")
    result = learn_from_match(
        league="LaLiga",
        predicted_score="2-1",
        real_score="3-0",
        home_team="Real Madrid",
        away_team="Barcelona",
        source="test"
    )
    print(f"   Succès: {result.get('success')}")
    print(f"   Avant: {result.get('diff_expected_before')}")
    print(f"   Après: {result.get('diff_expected_after')}")
    print(f"   Ajustement: {result.get('adjustment'):+.4f}")
    
    # Test 2: Apprentissage batch
    print("\n2️⃣ Test apprentissage batch:")
    matches = [
        {"league": "PremierLeague", "predicted_score": "1-1", "real_score": "2-2"},
        {"league": "PremierLeague", "predicted_score": "2-0", "real_score": "1-1"},
        {"league": "SerieA", "predicted_score": "1-0", "real_score": "2-1"}
    ]
    batch_result = batch_learning(matches)
    print(f"   Ligues mises à jour: {len(batch_result)}")
    for league, info in batch_result.items():
        print(f"   - {league}: {info['count']} matchs, diffExpected final={info['final_diff']:.4f}")
    
    # Test 3: Statistiques
    print("\n3️⃣ Statistiques d'apprentissage:")
    stats = get_learning_stats(days=30)
    print(f"   Total événements: {stats.get('count')}")
    print(f"   Ajustement moyen: {stats.get('avg_adjustment', 0):+.4f}")
    
    print("\n✅ Tests terminés")

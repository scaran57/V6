# /app/backend/api/predict_with_odds.py
"""
API endpoint pour prédictions UFAv3 enrichies avec les cotes du marché
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import time
import sys

sys.path.insert(0, '/app/backend')

router = APIRouter()


class PredictWithOddsRequest(BaseModel):
    home_team: str
    away_team: str
    league: str
    home_coeff: float
    away_coeff: float
    topk: int = 10


@router.post("/api/ufa/v3/predict-with-odds")
def predict_with_odds(req: PredictWithOddsRequest):
    """
    Prédiction UFAv3 enrichie avec comparaison aux cotes du marché.
    
    Args:
        req: Requête de prédiction
    
    Returns:
        Prédictions + cotes marché + delta (confidence)
    """
    t0 = time.time()
    
    try:
        from ufa.ufa_v3_for_emergent import predict_single_with_odds
        
        res = predict_single_with_odds(
            req.home_team,
            req.away_team,
            req.league,
            req.home_coeff,
            req.away_coeff,
            topk=req.topk
        )
        
        return {
            "model": "ufa_v3_with_market_odds",
            "duration_sec": round(time.time() - t0, 3),
            **res
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Model not trained. Please train the model first."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction error: {str(e)}"
        )


@router.get("/api/ufa/v3/odds-stats")
def get_odds_stats():
    """
    Retourne des statistiques sur les cotes récupérées.
    
    Returns:
        Statistiques des cotes (total, dernière màj, ligues)
    """
    try:
        from tools.odds_api_integration import get_ingestion_stats
        
        stats = get_ingestion_stats()
        return {
            "status": "ok",
            **stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching stats: {str(e)}"
        )

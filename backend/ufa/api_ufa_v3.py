#!/usr/bin/env python3
# /app/backend/ufa/api_ufa_v3.py
"""
Endpoints FastAPI pour UFA v3 (PyTorch).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import time
import os

router = APIRouter()

class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    league: str
    home_coeff: float = 1.0
    away_coeff: float = 1.0
    topk: int = 10
    metadata: Optional[Dict] = {}

class ScoreProb(BaseModel):
    score: str
    probability: float
    odds: Optional[float] = None

class PredictResponse(BaseModel):
    top: List[ScoreProb]
    model: str
    version: str
    duration_sec: float
    home_team: str
    away_team: str
    league: str

class ModelStatus(BaseModel):
    available: bool
    version: str
    last_trained: Optional[str]
    total_samples: int
    num_teams: int
    num_leagues: int
    device: str


@router.post('/api/ufa/v3/predict', response_model=PredictResponse)
def ufa_v3_predict(req: PredictRequest):
    """
    Prédiction de scores avec UFA v3 (PyTorch).
    
    Args:
        req: Requête de prédiction
    
    Returns:
        Top K scores avec probabilités
    """
    t0 = time.time()
    
    try:
        # Import du module UFA v3
        from ufa.ufa_v3_for_emergent import predict_single
        
        # Prédiction (retourne liste de dicts)
        results = predict_single(
            req.home_team,
            req.away_team,
            req.league,
            req.home_coeff,
            req.away_coeff
        )
        
        # Prendre top K
        top_results = results[:req.topk]
        
        # Convertir en réponse
        top = []
        for result in top_results:
            home_score = result['home_score']
            away_score = result['away_score']
            prob = result['probability']
            score = f"{home_score}-{away_score}"
            
            # Calculer cotes (odds = 1/probability)
            odds = round(1.0 / prob, 2) if prob > 0 else 999.0
            top.append({
                'score': score,
                'probability': round(prob, 4),
                'odds': odds
            })
        
        return {
            'top': top,
            'model': 'ufa_v3_pytorch',
            'version': '3.0',
            'duration_sec': round(time.time() - t0, 3),
            'home_team': req.home_team,
            'away_team': req.away_team,
            'league': req.league
        }
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f'UFA v3 model not available: {str(e)}'
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Prediction error: {str(e)}'
        )


@router.get('/api/ufa/v3/status', response_model=ModelStatus)
def ufa_v3_status():
    """
    Status du modèle UFA v3.
    
    Returns:
        Informations sur le modèle
    """
    import torch
    from ufa.ufa_v3_for_emergent import get_model_status
    
    # Utiliser la fonction de status du module
    status = get_model_status()
    
    if not status.get('model_exists', False):
        return {
            'available': False,
            'version': '3.0',
            'last_trained': None,
            'total_samples': 0,
            'num_teams': 0,
            'num_leagues': 0,
            'device': 'none'
        }
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    return {
        'available': True,
        'version': status.get('version', '3.0'),
        'last_trained': status.get('last_trained'),
        'total_samples': status.get('total_samples', 0),
        'num_teams': status.get('num_teams', 0),
        'num_leagues': status.get('num_leagues', 0),
        'device': device
    }


@router.post('/api/ufa/v3/retrain')
def ufa_v3_trigger_retrain(walltime_minutes: int = 60):
    """
    Déclenche un réentraînement manuel.
    
    Args:
        walltime_minutes: Limite de temps
    
    Returns:
        Message de confirmation
    """
    try:
        from ufa.ufa_v3_for_emergent import auto_retrain
        import threading
        
        # Lancer en arrière-plan
        thread = threading.Thread(
            target=auto_retrain,
            args=(walltime_minutes,)
        )
        thread.daemon = True
        thread.start()
        
        return {
            'status': 'started',
            'message': f'Retraining started in background (walltime: {walltime_minutes}min)',
            'check_logs': '/app/logs/ufa_v3_training.log'
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Failed to start retraining: {str(e)}'
        )

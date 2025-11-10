#!/usr/bin/env python3
# /app/backend/ufa/api_world_coeffs.py
from fastapi import APIRouter
from .world_coeffs import load_world_coeffs

router = APIRouter()

@router.get("/api/league/world-coeffs")
def list_world_coeffs():
    """
    Endpoint pour consulter tous les coefficients mondiaux FIFA.
    
    Returns:
        {
            "count": int,
            "teams": {
                "France": {"rank": 2, "coeff": 1.28},
                "Brazil": {"rank": 1, "coeff": 1.30},
                ...
            }
        }
    """
    teams = load_world_coeffs()
    return {"count": len(teams), "teams": teams}

@router.get("/api/league/world-coeffs/{team_name}")
def get_team_world_coeff(team_name: str):
    """
    Endpoint pour obtenir le coefficient d'une équipe spécifique.
    
    Args:
        team_name: Nom de l'équipe nationale
        
    Returns:
        {
            "team": str,
            "rank": int,
            "coeff": float,
            "found": bool
        }
    """
    from .world_coeffs import get_world_coeff, get_world_rank
    
    coeff = get_world_coeff(team_name)
    rank = get_world_rank(team_name)
    
    return {
        "team": team_name,
        "rank": rank,
        "coeff": coeff,
        "found": rank is not None
    }

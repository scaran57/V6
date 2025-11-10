#!/usr/bin/env python3
# /app/backend/ufa/world_coeffs.py
import json
from pathlib import Path
import os

OUT_FILE = Path(os.getenv("WORLD_COEFF_FILE", "/app/data/world_coeffs.json"))

def load_world_coeffs():
    """Charge les coefficients mondiaux depuis le fichier JSON."""
    if not OUT_FILE.exists():
        return {}
    with OUT_FILE.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except:
            return {}
    return data.get("teams", {})

def get_world_coeff(team_name):
    """
    Retourne le coefficient mondial pour une équipe nationale.
    Utilise plusieurs stratégies de matching:
    1. Match exact
    2. Match case-insensitive
    3. Match partiel (substring)
    
    Retourne 1.0 par défaut si aucune correspondance.
    """
    teams = load_world_coeffs()
    if not teams:
        return 1.0
    
    # Direct exact match
    if team_name in teams:
        return float(teams[team_name].get("coeff", 1.0))
    
    # Case-insensitive match
    for t in teams:
        if t.lower() == (team_name or "").lower():
            return float(teams[t].get("coeff", 1.0))
    
    # Try partial match (substring)
    for t in teams:
        if (team_name or "").lower() in t.lower() or t.lower() in (team_name or "").lower():
            return float(teams[t].get("coeff", 1.0))
    
    return 1.0

def get_world_rank(team_name):
    """Retourne le rang mondial d'une équipe."""
    teams = load_world_coeffs()
    if not teams:
        return None
    
    # Direct exact match
    if team_name in teams:
        return teams[team_name].get("rank")
    
    # Case-insensitive match
    for t in teams:
        if t.lower() == (team_name or "").lower():
            return teams[t].get("rank")
    
    return None

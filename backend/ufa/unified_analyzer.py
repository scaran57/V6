#!/usr/bin/env python3
# /app/backend/ufa/unified_analyzer.py
"""
UEFA Unified Analyzer
- Single endpoint that replaces both Analyzer UEFA and Mode Production.
- Applies league coefficients, saves analysis to cache, and optionally persists real scores.
- Compatible with existing pipeline (ocr_parser, analyzer_integration, ufa_auto_validate, train scripts).
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import OCR parser
from ocr_parser import extract_match_info

# Import predictor
from score_predictor import calculate_probabilities
from learning import get_diff_expected

# Paths
UPLOADS = Path("/app/uploads/unified")
ANALYSIS_CACHE = Path("/app/data/analysis_cache.jsonl")   # analyses (pre-match predictions)
REAL_SCORES = Path("/app/data/real_scores.jsonl")        # confirmed real scores (for training)
TEAM_MAP_FILE = Path("/app/data/team_map.json")          # generated team map
LOGS_DIR = Path("/app/logs")

# Ensure directories
LOGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS.mkdir(parents=True, exist_ok=True)
ANALYSIS_CACHE.parent.mkdir(parents=True, exist_ok=True)
REAL_SCORES.parent.mkdir(parents=True, exist_ok=True)

# Helpers
def append_jsonl(path: Path, obj: dict):
    """Append a JSON object to a JSONL file"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def read_jsonl(path: Path):
    """Read all entries from a JSONL file"""
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except:
                    continue
    return out

def make_analysis_entry(info: dict, prediction: dict, source: str = "ocr_unified"):
    """Create an analysis entry for the cache"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "home_team": info.get("home_team"),
        "away_team": info.get("away_team"),
        "league": info.get("league"),
        "home_goals_detected": info.get("home_goals"),
        "away_goals_detected": info.get("away_goals"),
        "raw_text": info.get("raw_text", ""),
        "prediction": prediction
    }

def predict_with_coeffs(home: Optional[str], away: Optional[str], league: str, scores: list):
    """
    Make a prediction using league coefficients
    
    Args:
        home: Home team name
        away: Away team name
        league: League name
        scores: List of score dictionaries from OCR
    
    Returns:
        Dictionary with prediction results
    """
    try:
        diff_expected = get_diff_expected()
        
        # Use the calculate_probabilities function with league coefficients
        result = calculate_probabilities(
            scores=scores,
            diff_expected=diff_expected,
            home_team=home,
            away_team=away,
            league=league,
            use_league_coeff=True
        )
        
        return {
            "status": "success",
            "most_probable": result.get("mostProbableScore", "N/A"),
            "probabilities": result.get("probabilities", {}),
            "confidence": result.get("confidence", 0.0),
            "league_coeffs_applied": result.get("league_coeffs_applied", False),
            "top3": sorted(
                [{"score": s, "probability": p} for s, p in result.get("probabilities", {}).items()],
                key=lambda x: x["probability"],
                reverse=True
            )[:3]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "most_probable": "N/A",
            "probabilities": {},
            "confidence": 0.0,
            "league_coeffs_applied": False
        }

def analyze_image(
    file_path: str,
    manual_home: Optional[str] = None,
    manual_away: Optional[str] = None,
    manual_league: Optional[str] = None,
    persist_cache: bool = True
) -> dict:
    """
    Main analysis function
    
    Args:
        file_path: Path to the image file
        manual_home: Manual override for home team
        manual_away: Manual override for away team
        manual_league: Manual override for league
        persist_cache: Whether to save to analysis cache
    
    Returns:
        Dictionary with analysis results
    """
    try:
        # Extract via OCR parser (uses auto-mapping)
        info = extract_match_info(file_path, manual_home, manual_away, manual_league)
        
        # Get teams and league
        home = info.get("home_team")
        away = info.get("away_team")
        league = info.get("league") or "Unknown"
        
        # Extract odds/scores if available (for now, create a dummy list if not present)
        # In real implementation, you'd need to call extract_odds from ocr_engine
        # For now, we'll assume scores are extracted
        from ocr_engine import extract_odds
        scores = extract_odds(file_path)
        
        if not scores:
            return {
                "status": "error",
                "error": "No scores detected in image",
                "info": info
            }
        
        # Make prediction using league-aware predictor
        prediction = predict_with_coeffs(home, away, league, scores)
        
        # Assemble analysis entry
        entry = make_analysis_entry(info, prediction, source="ocr_unified")
        
        # Persist analysis cache (always if persist_cache True)
        if persist_cache:
            append_jsonl(ANALYSIS_CACHE, entry)
        
        # If OCR detected an actual score (rare pre-match), save to real_scores for training pipeline
        if info.get("home_goals") is not None and info.get("away_goals") is not None:
            # Format similar to real_scores entries expected by pipeline
            real_entry = {
                "league": info.get("league", "Unknown"),
                "home_team": info.get("home_team") or "Unknown",
                "away_team": info.get("away_team") or "Unknown",
                "home_goals": info.get("home_goals"),
                "away_goals": info.get("away_goals"),
                "date": info.get("timestamp"),
                "timestamp": info.get("timestamp"),
                "source": "ocr_unified",
                "validated": True,
                "validated_at": datetime.utcnow().isoformat()
            }
            append_jsonl(REAL_SCORES, real_entry)
            entry["saved_to_real_scores"] = True
        
        # Response
        return {
            "status": "ok",
            "analysis": entry,
            "info": info,
            "prediction": prediction
        }
    
    except Exception as e:
        tb = traceback.format_exc()
        return {
            "status": "error",
            "error": str(e),
            "trace": tb
        }

# For direct import and use
__all__ = ['analyze_image', 'ANALYSIS_CACHE', 'REAL_SCORES']

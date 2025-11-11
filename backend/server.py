from fastapi import FastAPI, APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone
import shutil
import subprocess
import hashlib

# Import des modules de prédiction de score
from ocr_engine import extract_odds, extract_match_info as extract_match_info_legacy
from ocr_parser import extract_match_info as extract_match_info_advanced
from score_predictor import calculate_probabilities, calculate_probabilities_v2
from learning import update_model, get_diff_expected

# Import du router des coefficients FIFA
from ufa.api_world_coeffs import router as world_coeffs_router
# Import du router UFA v3 (PyTorch)
from ufa.api_ufa_v3 import router as ufa_v3_router
from api.dashboard_status import router as dashboard_router
from api.predict_with_odds import router as predict_odds_router
from matches_memory import (
    analyze_match_stable, 
    get_match_result, 
    generate_match_id,
    get_all_matches,
    delete_match,
    clear_all_matches,
    generate_system_report
)

# Import des modules de classement de ligues
import league_fetcher
import league_coeff
import league_scheduler
import prediction_validator

# Import du unified analyzer
from ufa.unified_analyzer import analyze_image, ANALYSIS_CACHE, REAL_SCORES


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Score Predictor API")

# Installer Tesseract au démarrage de l'app
@app.on_event("startup")
async def startup_event():
    """Installation automatique de Tesseract et démarrage du scheduler au démarrage"""
    try:
        result = subprocess.run(['which', 'tesseract'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("✅ Tesseract déjà installé")
        else:
            logger.warning("⚠️ Installation automatique de Tesseract...")
            subprocess.run(['apt-get', 'update', '-qq'], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            subprocess.run(['apt-get', 'install', '-y', '-qq', 
                           'tesseract-ocr', 'tesseract-ocr-fra', 
                           'tesseract-ocr-eng', 'tesseract-ocr-spa'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            logger.info("✅ Tesseract installé automatiquement")
    except Exception as e:
        logger.error(f"❌ Erreur installation Tesseract: {e}")
    
    # Démarrer le planificateur de mises à jour automatiques des ligues
    try:
        logger.info("🔄 Démarrage du planificateur de mises à jour des ligues...")
        league_scheduler.start_scheduler()
        status = league_scheduler.get_scheduler_status()
        logger.info(f"✅ Planificateur démarré: mise à jour quotidienne à {status['update_time']}")
    except Exception as e:
        logger.error(f"❌ Erreur démarrage planificateur: {e}")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Dossier pour les uploads temporaires
UPLOAD_DIR = "/app/backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# ========== ENDPOINTS PRÉDICTION DE SCORE ==========

@api_router.get("/health")
async def health():
    """Vérification de santé de l'API"""
    return {"status": "ok", "message": "API de prédiction de score en ligne ✅"}

@api_router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    disable_cache: bool = Query(default=False, description="Force un nouveau calcul (ignore le cache)"),
    use_combined_algo: bool = Query(default=False, description="Utiliser l'algorithme combiné (Poisson + ImpliedOdds)"),
    disable_league_coeff: bool = Query(default=False, description="Désactiver les coefficients de ligue"),
    league: str = Query(default=None, description="Ligue (LaLiga, PremierLeague, etc.) - auto-détecté si non spécifié")
):
    """
    Analyse une image de bookmaker et prédit le score le plus probable.
    
    Args:
        file: Image du bookmaker à analyser
        disable_cache: Si True, force un nouveau calcul même si le match existe en mémoire (défaut: False)
        use_combined_algo: Si True, utilise l'algorithme combiné avancé (défaut: False)
        disable_league_coeff: Si True, désactive les coefficients de ligue (défaut: False)
        league: Nom de la ligue (optionnel, auto-détecté si possible)
    
    Usage:
        curl -X POST "http://localhost:8001/api/analyze?disable_cache=true" -F "file=@image.jpg"
        curl -X POST "http://localhost:8001/api/analyze?disable_league_coeff=true" -F "file=@image.jpg"
        curl -X POST "http://localhost:8001/api/analyze?league=LaLiga" -F "file=@image.jpg"
    """
    try:
        # Sauvegarder l'image temporairement
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Image reçue: {file.filename}")
        
        # Calculer le hash MD5 de l'image pour garantir l'unicité
        with open(file_path, "rb") as f:
            image_hash = hashlib.md5(f.read()).hexdigest()
        
        logger.info(f"Hash de l'image: {image_hash}")
        
        # Utiliser le nouveau parser avancé pour extraire les informations du match
        logger.info("🔍 Extraction avancée des informations de match avec ocr_parser...")
        advanced_info = extract_match_info_advanced(file_path)
        
        home_team = advanced_info.get("home_team")
        away_team = advanced_info.get("away_team")
        detected_league = advanced_info.get("league", "Unknown")
        
        # Construire le match_name à partir des équipes détectées
        if home_team and away_team:
            match_name = f"{home_team} - {away_team}"
            logger.info(f"✅ Équipes détectées: {home_team} vs {away_team}")
            logger.info(f"✅ Ligue détectée: {detected_league}")
        else:
            match_name = "Match non détecté"
            logger.warning(f"⚠️ Aucune équipe détectée par le parser avancé")
        
        # Fallback sur l'ancien système pour le bookmaker
        legacy_info = extract_match_info_legacy(file_path)
        bookmaker = legacy_info.get("bookmaker", "Bookmaker inconnu")
        
        # Générer un ID unique pour ce match (basé sur le hash de l'image)
        match_id = generate_match_id(match_name, bookmaker, image_hash=image_hash)
        
        # Vérifier si ce match a déjà été analysé (sauf si cache désactivé)
        if not disable_cache:
            existing_result = get_match_result(match_id)
            if existing_result:
                logger.info(f"✅ CACHE HIT - Match {match_id} récupéré depuis le cache (pas de recalcul)")
                os.remove(file_path)
                
                return JSONResponse({
                    "success": True,
                    "fromMemory": True,
                    "matchId": match_id,
                    "matchName": existing_result["match_name"],
                    "bookmaker": existing_result["bookmaker"],
                    "extractedScores": existing_result["extracted_scores"],
                    "mostProbableScore": existing_result["top3"][0]["score"] if existing_result["top3"] else "N/A",
                    "probabilities": existing_result["probabilities"],
                    "confidence": existing_result["confidence"],
                    "top3": existing_result["top3"],
                    "analyzedAt": existing_result.get("analyzed_at"),
                    "debug": "Résultat récupéré du cache - OCR et calculs non effectués"
                })
            else:
                logger.info(f"🆕 CACHE MISS - Nouveau match {match_id}, calcul complet requis")
        else:
            logger.info(f"🔄 CACHE DÉSACTIVÉ - Nouveau calcul forcé pour {match_id} (OCR + prédiction)")
        
        # Extraire les cotes via OCR
        logger.info(f"🔍 OCR en cours pour {match_id}...")
        scores = extract_odds(file_path)
        
        if not scores:
            os.remove(file_path)
            return JSONResponse({
                "error": "Aucune cote détectée dans l'image",
                "mostProbableScore": "Aucune donnée",
                "probabilities": {}
            })
        
        logger.info(f"✅ OCR terminé: {len(scores)} scores extraits")
        
        # Obtenir la diffExpected pour le calcul
        diff_expected = get_diff_expected()
        
        # Utiliser la ligue détectée par le parser avancé
        # Priorité: paramètre manuel > détection avancée > Unknown
        if league:
            detected_league = league
            logger.info(f"🎯 Ligue spécifiée manuellement: {detected_league}")
        elif detected_league and detected_league != "Unknown":
            logger.info(f"✅ Ligue détectée automatiquement par parser avancé: {detected_league}")
        else:
            # Fallback sur Unknown si aucune détection
            detected_league = "Unknown"
            logger.warning(f"⚠️ Ligue non détectée - coefficients ne seront pas appliqués")
        
        # Prédire le score avec l'algorithme choisi
        use_league_coeff = not disable_league_coeff
        logger.info(f"🧮 Calcul des probabilités avec diffExpected={diff_expected}, league={detected_league}, use_league_coeff={use_league_coeff}...")
        
        if use_combined_algo:
            result = calculate_probabilities_v2(
                scores, 
                diff_expected, 
                use_combined=True,
                teamA_name=home_team,
                teamB_name=away_team
            )
        else:
            result = calculate_probabilities(
                scores, 
                diff_expected,
                home_team=home_team,
                away_team=away_team,
                league=detected_league,
                use_league_coeff=use_league_coeff
            )
        
        # Nettoyer le fichier temporaire
        os.remove(file_path)
        
        logger.info(f"✅ Prédiction terminée: {result['mostProbableScore']} (confiance: {result.get('confidence', 0)*100:.1f}%)")
        
        # Calculer le top 3 pour le retour
        sorted_probs = sorted(result['probabilities'].items(), key=lambda x: x[1], reverse=True)
        top3 = [{"score": s, "probability": p} for s, p in sorted_probs[:3]]
        
        # Sauvegarder dans la mémoire (seulement si cache activé)
        algo_name = "Algorithme Combiné (Poisson + ImpliedOdds + Smoothing)" if use_combined_algo else "Algorithme Classique"
        debug_message = ""
        if not disable_cache:
            saved_result = analyze_match_stable(
                match_id=match_id,
                scores_data=scores,
                probabilities=result['probabilities'],
                confidence=result.get('confidence', 0.0),
                top3=top3,
                bookmaker=bookmaker,
                match_name=match_name
            )
            logger.info(f"💾 Résultat sauvegardé dans le cache pour les prochaines utilisations")
            debug_message = f"Nouveau calcul effectué avec {algo_name} et sauvegardé dans le cache"
        else:
            logger.info(f"⚠️ Cache désactivé - résultat NON sauvegardé (sera recalculé à chaque fois)")
            debug_message = f"Nouveau calcul effectué avec {algo_name} mais NON sauvegardé - sera recalculé à chaque analyse"
        
        return JSONResponse({
            "success": True,
            "fromMemory": False,
            "cacheDisabled": disable_cache,
            "algorithmUsed": algo_name,
            "league": detected_league,
            "leagueCoeffsApplied": result.get('league_coeffs_applied', False),
            "matchId": match_id,
            "matchName": match_name,
            "bookmaker": bookmaker,
            "extractedScores": scores,
            "mostProbableScore": result['mostProbableScore'],
            "probabilities": result['probabilities'],
            "confidence": result.get('confidence', 0.0),
            "top3": top3,
            "debug": debug_message
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur lors de l'analyse: {str(e)}"}, 
            status_code=500
        )

@api_router.post("/unified/analyze")
async def unified_analyze(
    file: UploadFile = File(...),
    manual_home: str = Form(None),
    manual_away: str = Form(None),
    manual_league: str = Form(None),
    persist_cache: bool = Form(True)
):
    """
    Unified analyzer endpoint - Replaces both Analyzer UEFA and Mode Production.
    
    - Applies league coefficients automatically
    - Saves analysis to cache (analysis_cache.jsonl)
    - Saves real scores if detected (real_scores.jsonl)
    - Compatible with UFA pipeline
    
    Args:
        file: Image file from bookmaker
        manual_home: Manual override for home team (optional)
        manual_away: Manual override for away team (optional)
        manual_league: Manual override for league (optional)
        persist_cache: Whether to save analysis to cache (default: True)
    
    Returns:
        JSON with analysis results including:
        - Detected teams and league
        - Prediction with league coefficients applied
        - Top 3 most probable scores
        - Confidence level
    """
    try:
        # Save uploaded file
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"📸 Unified Analyzer - Image reçue: {file.filename}")
        
        # Analyze using unified analyzer
        result = analyze_image(
            file_path=file_path,
            manual_home=manual_home,
            manual_away=manual_away,
            manual_league=manual_league,
            persist_cache=persist_cache
        )
        
        # Clean up temporary file
        os.remove(file_path)
        
        if result.get("status") == "ok":
            analysis = result.get("analysis", {})
            prediction = result.get("prediction", {})
            info = result.get("info", {})
            
            logger.info(f"✅ Unified Analyzer - Analyse terminée")
            logger.info(f"   Équipes: {info.get('home_team')} vs {info.get('away_team')}")
            logger.info(f"   Ligue: {info.get('league')}")
            logger.info(f"   Score probable: {prediction.get('most_probable')}")
            logger.info(f"   Coefficients appliqués: {prediction.get('league_coeffs_applied')}")
            logger.info(f"   Sauvegardé: {persist_cache}")
            
            return JSONResponse({
                "success": True,
                "matchName": f"{info.get('home_team', 'Unknown')} - {info.get('away_team', 'Unknown')}",
                "league": info.get("league", "Unknown"),
                "leagueCoeffsApplied": prediction.get("league_coeffs_applied", False),
                "mostProbableScore": prediction.get("most_probable", "N/A"),
                "probabilities": prediction.get("probabilities", {}),
                "confidence": prediction.get("confidence", 0.0),
                "top3": prediction.get("top3", []),
                "savedToCache": persist_cache,
                "timestamp": analysis.get("timestamp"),
                "info": {
                    "home_team": info.get("home_team"),
                    "away_team": info.get("away_team"),
                    "league": info.get("league"),
                    "home_goals_detected": info.get("home_goals"),
                    "away_goals_detected": info.get("away_goals")
                }
            })
        else:
            logger.error(f"❌ Unified Analyzer - Erreur: {result.get('error')}")
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "trace": result.get("trace", "")
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"❌ Unified Analyzer - Exception: {str(e)}")
        import traceback
        return JSONResponse({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc()
        }, status_code=500)

@api_router.get("/unified/health")
async def unified_health():
    """Health check for unified analyzer"""
    return JSONResponse({
        "status": "ok",
        "analysis_cache": str(ANALYSIS_CACHE),
        "real_scores": str(REAL_SCORES),
        "cache_entries": len(open(ANALYSIS_CACHE).readlines()) if ANALYSIS_CACHE.exists() else 0,
        "real_scores_entries": len(open(REAL_SCORES).readlines()) if REAL_SCORES.exists() else 0
    })

@api_router.post("/learn")
async def learn(
    predicted: str = Form(...), 
    real: str = Form(...),
    home_team: str = Form(None),
    away_team: str = Form(None)
):
    """
    Ajuste le modèle de prédiction avec le score prédit vs score réel.
    Utilise le système sécurisé avec log append-only.
    Optionnel: Noms des équipes pour apprentissage contextuel.
    """
    try:
        # Utiliser le système sécurisé
        import sys
        sys.path.insert(0, '/app')
        from modules.local_learning_safe import record_learning_event, load_meta
        
        # Générer un match_id
        import time
        match_id = f"learn_{int(time.time())}"
        
        # Enregistrer l'événement d'apprentissage
        success, result = record_learning_event(
            match_id=match_id,
            home_team=home_team or "Unknown",
            away_team=away_team or "Unknown",
            predicted=predicted,
            real=real,
            agent_id="api_learn_endpoint",
            keep_last=5  # Garder les 5 derniers
        )
        
        if success:
            meta = load_meta()
            diff = meta.get("diffExpected")
            logger.info(f"✅ Apprentissage sécurisé: {predicted} → {real}, nouvelle diff: {diff}")
            
            # Aussi mettre à jour l'ancien système pour compatibilité
            update_model(predicted, real, home_team, away_team)
            
            return {
                "success": True,
                "message": f"Modèle ajusté avec le score réel: {real} ✅",
                "newDiffExpected": diff,
                "event": result
            }
        else:
            return JSONResponse(
                {"error": f"Erreur d'enregistrement: {result}"}, 
                status_code=400
            )
            
    except Exception as e:
        logger.error(f"Erreur lors de l'apprentissage: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.post("/save-real-score")
async def save_real_score_endpoint(
    match_id: str = Form(...),
    league: str = Form(...),
    home_team: str = Form(...),
    away_team: str = Form(...),
    home_goals: int = Form(...),
    away_goals: int = Form(...)
):
    """
    Enregistre un score réel pour l'apprentissage UFA.
    Utilisé par le Mode Production (Phase 1).
    Aucun apprentissage n'est effectué ici - juste sauvegarde.
    """
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from production_phase1.save_real_score import save_real_score
        
        entry = save_real_score(
            match_id=match_id,
            league=league,
            home_team=home_team,
            away_team=away_team,
            home_goals=home_goals,
            away_goals=away_goals
        )
        
        logger.info(f"✅ Score réel enregistré (Phase 1): {home_team} {home_goals}-{away_goals} {away_team}")
        
        return {
            "success": True,
            "message": f"Score réel enregistré: {home_team} {home_goals}-{away_goals} {away_team}",
            "entry": entry,
            "note": "L'apprentissage UFA sera effectué automatiquement lors de la prochaine mise à jour nocturne"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du score réel: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/ufa/balance")
async def get_ufa_balance():
    """
    Retourne le rapport d'équilibre UFA le plus récent.
    """
    try:
        import os
        report_path = "/app/data/ufa_balance_report.json"
        
        if not os.path.exists(report_path):
            return {
                "success": False,
                "message": "Aucun rapport d'équilibre disponible. Lancez d'abord l'analyse."
            }
        
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        
        return {
            "success": True,
            "report": report
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du rapport d'équilibre: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.post("/ufa/balance/run")
async def run_ufa_balance_check():
    """
    Lance manuellement une vérification d'équilibre UFA.
    """
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from ufa.ufa_check_balance import analyze_balance
        
        logger.info("🔄 Lancement manuel de la vérification d'équilibre UFA")
        report = analyze_balance()
        
        return {
            "success": True,
            "message": "Vérification d'équilibre terminée",
            "report": report
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification d'équilibre: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.post("/ufa/ocr/upload")
async def upload_score_image(
    file: UploadFile = File(...),
    home_team: str = Form("Unknown"),
    away_team: str = Form("Unknown"),
    league: str = Form("Unknown")
):
    """
    Upload une image de score et extrait automatiquement le résultat via OCR.
    """
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from ufa.ufa_ocr_importer import process_image
        
        # Créer le dossier d'upload
        upload_dir = "/app/uploads/fdj_captures"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Sauvegarder l'image
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"📸 Image reçue: {file.filename}")
        
        # Traiter l'image
        result = process_image(file_path, home_team, away_team, league)
        
        if result["success"]:
            logger.info(f"✅ Score détecté: {result['score']}")
            return {
                "success": True,
                "message": f"Score détecté et ajouté: {result['score']}",
                "score": result['score'],
                "entry": result['entry']
            }
        else:
            logger.warning(f"⚠️ Aucun score détecté dans {file.filename}")
            return {
                "success": False,
                "message": "Aucun score détecté dans l'image",
                "error": result.get("error"),
                "text_detected": result.get("text")
            }
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement OCR: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.post("/ufa/ocr/upload-v2")
async def upload_score_image_v2(file: UploadFile = File(...)):
    """
    Upload une image et détecte automatiquement : Score + Équipes + Ligue (v2).
    """
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from ufa.ufa_ocr_importer_v2 import process_image
        
        # Créer le dossier d'upload
        upload_dir = "/app/uploads/fdj_captures"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Sauvegarder l'image
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"📸 Image reçue (v2): {file.filename}")
        
        # Traiter l'image avec v2 (détection automatique)
        result = process_image(file_path)
        
        if result["success"]:
            logger.info(f"✅ Détecté: {result.get('teams', [])} - {result['score']} - {result.get('league', 'Unknown')}")
            return {
                "success": True,
                "message": f"Détection complète réussie",
                "score": result['score'],
                "teams": result.get('teams', []),
                "league": result.get('league', 'Unknown'),
                "entry": result['entry']
            }
        else:
            logger.warning(f"⚠️ Échec détection dans {file.filename}")
            return {
                "success": False,
                "message": result.get("error", "Échec de détection"),
                "error": result.get("error"),
                "text_detected": result.get("text")
            }
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement OCR v2: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.post("/ufa/ocr/upload-autotrain")
async def upload_score_image_autotrain(
    file: UploadFile = File(...),
    auto_train: bool = Form(True)
):
    """
    Upload une image avec détection automatique ET training immédiat (v3).
    """
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from ufa.ufa_ocr_importer_autotrain import process_image, train_now
        
        # Créer le dossier d'upload
        upload_dir = "/app/uploads/fdj_captures"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Sauvegarder l'image
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"📸 Image reçue (v3 auto-train): {file.filename}")
        
        # Traiter l'image
        result = process_image(file_path)
        
        if not result["success"]:
            return {
                "success": False,
                "message": result.get("error", "Échec de détection"),
                "error": result.get("error")
            }
        
        logger.info(f"✅ Détecté: {result.get('teams', [])} - {result['score']} - {result.get('league')}")
        
        # Training automatique si demandé
        training_success = False
        if auto_train:
            logger.info("🧠 Lancement du training UFA...")
            training_success = train_now()
        
        return {
            "success": True,
            "message": "Détection complète et training effectué" if training_success else "Détection complète",
            "score": result['score'],
            "teams": result.get('teams', []),
            "league": result.get('league', 'Unknown'),
            "training_executed": training_success
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement OCR v3: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.post("/ufa/ocr/process-folder")
async def process_folder_ocr(
    folder_path: str = Form("/app/uploads/fdj_captures"),
    home_team: str = Form("Unknown"),
    away_team: str = Form("Unknown"),
    league: str = Form("Unknown")
):
    """
    Traite toutes les images d'un dossier via OCR.
    """
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from ufa.ufa_ocr_importer import process_folder
        
        logger.info(f"🔄 Traitement du dossier: {folder_path}")
        
        report = process_folder(folder_path, home_team, away_team, league)
        
        if report.get("success"):
            return {
                "success": True,
                "message": f"Dossier traité: {report['detected']}/{report['total']} scores détectés",
                "report": report
            }
        else:
            return {
                "success": False,
                "message": report.get("error", "Erreur inconnue"),
                "report": report
            }
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du dossier: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/diff")
async def get_diff():
    """
    Récupère la différence de buts attendue (utilisée par l'algorithme).
    """
    try:
        diff = get_diff_expected()
        return {"diffExpected": diff}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la diff: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/teams/stats")
async def get_teams_stats():
    """
    Récupère les statistiques de toutes les équipes.
    """
    try:
        from score_predictor import get_all_teams_stats, get_team_stats
        
        teams_data = get_all_teams_stats()
        
        # Enrichir avec les moyennes
        stats = {}
        for team, matches in teams_data.items():
            gf, ga = get_team_stats(team)
            stats[team] = {
                "matches_count": len(matches),
                "avg_goals_for": gf,
                "avg_goals_against": ga,
                "recent_matches": matches
            }
        
        return {"teams": stats, "total_teams": len(stats)}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/teams/{team_name}")
async def get_team_stats_by_name(team_name: str):
    """
    Récupère les statistiques d'une équipe spécifique.
    """
    try:
        from score_predictor import get_team_stats, _load_data
        
        gf, ga = get_team_stats(team_name)
        data = _load_data()
        
        if team_name not in data:
            return {
                "team": team_name,
                "found": False,
                "message": "Aucune donnée pour cette équipe"
            }
        
        return {
            "team": team_name,
            "found": True,
            "avg_goals_for": gf,
            "avg_goals_against": ga,
            "matches_count": len(data[team_name]),
            "recent_matches": data[team_name]
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats pour {team_name}: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/matches/memory")
async def get_matches_memory():
    """
    Récupère tous les matchs en mémoire.
    """
    try:
        matches = get_all_matches()
        return {
            "success": True,
            "total_matches": len(matches),
            "matches": matches
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la mémoire: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/matches/{match_id}")
async def get_match_by_id(match_id: str):
    """
    Récupère un match spécifique par son ID.
    """
    try:
        result = get_match_result(match_id)
        if result:
            return {
                "success": True,
                "match": result
            }
        else:
            return JSONResponse(
                {"error": f"Match {match_id} non trouvé"}, 
                status_code=404
            )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du match {match_id}: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.delete("/matches/{match_id}")
async def delete_match_by_id(match_id: str):
    """
    Supprime un match de la mémoire.
    """
    try:
        deleted = delete_match(match_id)
        if deleted:
            return {
                "success": True,
                "message": f"Match {match_id} supprimé"
            }
        else:
            return JSONResponse(
                {"error": f"Match {match_id} non trouvé"}, 
                status_code=404
            )
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du match {match_id}: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.delete("/matches/memory/clear")
async def clear_matches_memory():
    """
    Supprime tous les matchs de la mémoire.
    """
    try:
        clear_all_matches()
        return {
            "success": True,
            "message": "Mémoire complètement effacée"
        }
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de la mémoire: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/system/report")
async def get_system_report():
    """
    Génère un rapport de suivi automatique du système.
    Inclut statistiques sur les matchs, bookmakers, confiance moyenne, etc.
    """
    try:
        report = generate_system_report()
        return report
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/report")
def report():
    """
    🔎 Endpoint de suivi automatique des matchs analysés.
    Version simplifiée retournant uniquement le rapport textuel.
    """
    try:
        report_data = generate_system_report()
        report_text = report_data.get('report_text', '')
        return {"rapport": report_text or "Aucun rapport généré."}
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport: {str(e)}")
        return {"rapport": f"Erreur: {str(e)}"}

# ========== ENDPOINTS ADMIN - Gestion Apprentissage Sécurisé ==========

@api_router.post("/admin/rebuild-learning")
async def admin_rebuild_learning(keep_last: int = 20):
    """
    🔧 [ADMIN] Reconstruit teams_data.json et learning_meta.json depuis le log append-only.
    Utile pour récupérer l'historique après une corruption ou pour ajuster le nombre de matchs conservés.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "/app/scripts/rebuild_from_learning_log.py", "--keep-last", str(keep_last)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
            "keep_last": keep_last
        }
    except Exception as e:
        logger.error(f"Erreur lors du rebuild: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/admin/learning-stats")
async def admin_learning_stats():
    """
    📊 [ADMIN] Retourne des statistiques sur le système d'apprentissage sécurisé.
    """
    try:
        import sys
        sys.path.insert(0, '/app')
        from modules.local_learning_safe import get_learning_stats
        
        stats = get_learning_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/admin/export-learning-log")
async def admin_export_learning_log():
    """
    💾 [ADMIN] Exporte le log complet d'apprentissage pour backup.
    """
    try:
        import sys
        sys.path.insert(0, '/app')
        from modules.local_learning_safe import export_learning_log
        from fastapi.responses import FileResponse
        
        export_path = "/tmp/learning_backup.jsonl"
        export_learning_log(export_path)
        
        return FileResponse(
            export_path,
            media_type="application/x-ndjson",
            filename="learning_events_backup.jsonl"
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'export: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

# ========== ENDPOINTS DIAGNOSTIC ==========

@api_router.get("/diagnostic/last-analysis")
async def diagnostic_last_analysis():
    """
    🔍 Retourne la dernière analyse effectuée depuis la mémoire des matchs.
    """
    try:
        matches = get_all_matches()
        
        if not matches or len(matches.get('matches', {})) == 0:
            return {
                "success": False,
                "message": "Aucune analyse en mémoire"
            }
        
        # Récupérer le dernier match analysé
        all_matches = matches.get('matches', {})
        last_match_id = list(all_matches.keys())[-1]
        last_match = all_matches[last_match_id]
        
        return {
            "success": True,
            "match_id": last_match_id,
            "analysis": {
                "match_name": last_match.get("match_name"),
                "bookmaker": last_match.get("bookmaker"),
                "analyzed_at": last_match.get("analyzed_at"),
                "confidence": last_match.get("confidence"),
                "top3": last_match.get("top3"),
                "extracted_scores": last_match.get("extracted_scores"),
                "probabilities": last_match.get("probabilities")
            }
        }
    except Exception as e:
        logger.error(f"Erreur diagnostic: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.delete("/admin/clear-analysis-cache")
async def admin_clear_analysis_cache():
    """
    🗑️ [ADMIN] Vide complètement le cache des analyses (matches_memory).
    Utile pour forcer de nouveaux calculs sur tous les matchs.
    """
    try:
        clear_all_matches()
        return {
            "success": True,
            "message": "Cache d'analyse vidé avec succès",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )

@api_router.get("/diagnostic/system-status")
async def diagnostic_system_status():
    """
    📊 Diagnostic complet du système (apprentissage + analyses + santé).
    """
    try:
        import sys
        sys.path.insert(0, '/app')
        from modules.local_learning_safe import get_learning_stats
        
        # Statistiques d'apprentissage
        learning_stats = get_learning_stats()
        
        # Statistiques de mémoire des matchs
        matches = get_all_matches()
        
        # Santé du système
        diff = get_diff_expected()
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "learning_system": {
                "total_events": learning_stats.get("total_learning_events", 0),
                "teams_count": learning_stats.get("teams_count", 0),
                "diffExpected": learning_stats.get("diffExpected", 0),
                "schema_version": learning_stats.get("schema_version", 0),
                "files_ok": all([
                    learning_stats.get("log_file_exists"),
                    learning_stats.get("teams_file_exists"),
                    learning_stats.get("meta_file_exists")
                ])
            },
            "matches_memory": {
                "total_matches_analyzed": matches.get("total_matches", 0),
                "last_match_id": list(matches.get("matches", {}).keys())[-1] if matches.get("matches") else None
            },
            "current_config": {
                "diffExpected": diff
            },
            "status": "operational"
        }
    except Exception as e:
        logger.error(f"Erreur diagnostic système: {str(e)}")
        return JSONResponse(
            {"error": f"Erreur: {str(e)}"}, 
            status_code=500
        )


# ============================================================================
# === ROUTES LEAGUE COEFFICIENT SYSTEM ===
# ============================================================================

@api_router.post("/admin/league/update")
async def api_update_league(
    league: str = Query(..., description="Nom de la ligue à mettre à jour"),
    force: bool = Query(False, description="Forcer la mise à jour (ignorer le cache)")
):
    """
    Met à jour le classement d'une ligue depuis Wikipedia.
    
    Ligues disponibles : LaLiga, PremierLeague, SerieA, Ligue1, Bundesliga, PrimeiraLiga
    """
    try:
        data = league_fetcher.update_league(league, force=force)
        sample = list(data.items())[:8]
        
        return {
            "success": True,
            "league": league,
            "teams_count": len(data),
            "sample": sample,
            "message": f"Classement {league} mis à jour avec succès"
        }
    except Exception as e:
        logger.error(f"Erreur update league {league}: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.post("/admin/league/update-all")
async def api_update_all_leagues(force: bool = Query(False)):
    """
    Met à jour tous les classements de toutes les ligues.
    Peut prendre quelques secondes.
    """
    try:
        res = league_fetcher.update_all(force=force)
        summary = {k: len(v) for k, v in res.items()}
        
        return {
            "success": True,
            "updated": summary,
            "message": "Tous les classements mis à jour"
        }
    except Exception as e:
        logger.error(f"Erreur update all leagues: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.get("/admin/league/list")
async def api_list_leagues():
    """Liste toutes les ligues disponibles"""
    return {
        "success": True,
        "leagues": list(league_fetcher.WIKI_MAP.keys())
    }

@api_router.get("/admin/league/standings")
async def api_get_standings(league: str = Query(...)):
    """Récupère le classement complet d'une ligue"""
    try:
        data = league_fetcher.load_positions().get(league, {})
        
        if not data:
            return {
                "success": False,
                "message": f"Aucun classement disponible pour {league}. Utilisez /admin/league/update d'abord."
            }
        
        # Trier par position
        sorted_teams = sorted(data.items(), key=lambda x: x[1])
        
        return {
            "success": True,
            "league": league,
            "teams_count": len(data),
            "standings": [{"team": team, "position": pos} for team, pos in sorted_teams]
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.get("/league/team-coeff")
async def api_get_team_coeff(
    team: str = Query(...),
    league: str = Query("LaLiga"),
    mode: str = Query("linear", regex="^(linear|exponential)$")
):
    """
    Calcule le coefficient d'une équipe selon son classement avec système de fallback intelligent.
    
    Pour les compétitions européennes (ChampionsLeague, EuropaLeague):
    - Cherche d'abord dans les ligues nationales
    - Si trouvé, retourne le coefficient de la ligue nationale
    - Sinon, retourne un bonus européen (1.05)
    
    Args:
        team: Nom de l'équipe
        league: Nom de la ligue
        mode: linear ou exponential
    """
    try:
        # Utiliser get_team_coeff qui gère le fallback intelligent
        result = league_coeff.get_team_coeff(team, league)
        
        if isinstance(result, dict):
            coef = result["coefficient"]
            source = result["source"]
        else:
            coef = result
            source = league
        
        # Essayer de récupérer la position si dans une ligue avec classement
        pos = None
        try:
            pos = league_fetcher.get_team_position(team, source if source != "european_fallback" else league)
        except:
            pass
        
        return {
            "success": True,
            "team": team,
            "league": league,
            "position": pos,
            "coefficient": coef,
            "source": source,
            "mode": mode,
            "note": "Source indique d'où provient le coefficient (ligue nationale ou fallback)"
        }
    except Exception as e:
        logger.error(f"Erreur calcul coefficient: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.post("/admin/league/clear-cache")
async def api_clear_coeff_cache():
    """Vide le cache des coefficients"""
    try:
        success = league_coeff.clear_cache()
        if success:
            return {"success": True, "message": "Cache des coefficients vidé"}
        else:
            return {"success": False, "message": "Erreur lors du vidage du cache"}
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.get("/admin/league/scheduler-status")
async def api_get_scheduler_status():
    """Récupère le statut du planificateur automatique"""
    try:
        status = league_scheduler.get_scheduler_status()
        return {
            "success": True,
            "scheduler": status
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.post("/admin/league/trigger-update")
async def api_trigger_manual_update():
    """Déclenche une mise à jour manuelle immédiate de toutes les ligues"""
    try:
        league_scheduler.trigger_manual_update()
        return {
            "success": True,
            "message": "Mise à jour manuelle déclenchée en arrière-plan"
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

# ============================================================================
# VALIDATION DES PRÉDICTIONS
# ============================================================================

@api_router.get("/validation/status")
async def api_validation_status():
    """Récupère le dernier rapport de validation"""
    try:
        report = prediction_validator.get_latest_report()
        return {"success": True, **report}
    except Exception as e:
        logger.error(f"Erreur récupération rapport validation: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.post("/validation/run")
async def api_run_validation(days: int = 7):
    """
    Exécute une validation des prédictions
    
    Args:
        days: Nombre de jours à analyser (défaut: 7)
    """
    try:
        report = prediction_validator.validate_predictions(days_back=days)
        return {"success": True, **report}
    except Exception as e:
        logger.error(f"Erreur exécution validation: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.get("/validation/history")
async def api_validation_history(limit: int = 30):
    """
    Récupère l'historique des validations
    
    Args:
        limit: Nombre maximum d'entrées (défaut: 30)
    """
    try:
        history = prediction_validator.get_validation_history(limit=limit)
        return {
            "success": True,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        logger.error(f"Erreur récupération historique: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.post("/validation/add-prediction")
async def api_add_prediction(
    match_id: str,
    home_team: str,
    away_team: str,
    predicted_score: str,
    confidence: float = None,
    league: str = None
):
    """Enregistre une nouvelle prédiction"""
    try:
        prediction_validator.add_prediction(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            predicted_score=predicted_score,
            confidence=confidence,
            league=league
        )
        return {
            "success": True,
            "message": "Prédiction enregistrée"
        }
    except Exception as e:
        logger.error(f"Erreur enregistrement prédiction: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )

@api_router.post("/validation/add-result")
async def api_add_result(
    match_id: str,
    final_score: str,
    home_team: str = None,
    away_team: str = None,
    league: str = None
):
    """Enregistre le résultat réel d'un match"""
    try:
        prediction_validator.add_result(
            match_id=match_id,
            final_score=final_score,
            home_team=home_team,
            away_team=away_team,
            league=league
        )
        return {
            "success": True,
            "message": "Résultat enregistré"
        }
    except Exception as e:
        logger.error(f"Erreur enregistrement résultat: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )


# Include the router in the main app
app.include_router(api_router)
app.include_router(world_coeffs_router)
app.include_router(ufa_v3_router)
app.include_router(dashboard_router)
app.include_router(predict_odds_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
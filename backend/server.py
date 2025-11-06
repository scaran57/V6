from fastapi import FastAPI, APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone
import shutil
import subprocess

# Import des modules de prédiction de score
from ocr_engine import extract_odds, extract_match_info
from score_predictor import calculate_probabilities, calculate_probabilities_v2
from learning import update_model, get_diff_expected
from matches_memory import (
    analyze_match_stable, 
    get_match_result, 
    generate_match_id,
    get_all_matches,
    delete_match,
    clear_all_matches,
    generate_system_report
)


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
    """Installation automatique de Tesseract au démarrage"""
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
    use_combined_algo: bool = Query(default=True, description="Utiliser l'algorithme combiné (Poisson + ImpliedOdds)")
):
    """
    Analyse une image de bookmaker et prédit le score le plus probable.
    
    Args:
        file: Image du bookmaker à analyser
        disable_cache: Si True, force un nouveau calcul même si le match existe en mémoire (défaut: False)
        use_combined_algo: Si True, utilise l'algorithme combiné avancé (défaut: True)
    
    Usage:
        curl -X POST "http://localhost:8001/api/analyze?disable_cache=true" -F "file=@image.jpg"
        curl -X POST "http://localhost:8001/api/analyze?use_combined_algo=false" -F "file=@image.jpg"
    """
    try:
        # Sauvegarder l'image temporairement
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Image reçue: {file.filename}")
        
        # Extraire les informations du match (nom et bookmaker)
        match_info = extract_match_info(file_path)
        match_name = match_info.get("match_name", "Match non détecté")
        bookmaker = match_info.get("bookmaker", "Bookmaker inconnu")
        
        # Générer un ID unique pour ce match
        match_id = generate_match_id(match_name, bookmaker)
        
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
        
        # Prédire le score avec le nouvel algorithme
        logger.info(f"🧮 Calcul des probabilités avec diffExpected={diff_expected}...")
        result = calculate_probabilities(scores, diff_expected)
        
        # Nettoyer le fichier temporaire
        os.remove(file_path)
        
        logger.info(f"✅ Prédiction terminée: {result['mostProbableScore']} (confiance: {result.get('confidence', 0)*100:.1f}%)")
        
        # Calculer le top 3 pour le retour
        sorted_probs = sorted(result['probabilities'].items(), key=lambda x: x[1], reverse=True)
        top3 = [{"score": s, "probability": p} for s, p in sorted_probs[:3]]
        
        # Sauvegarder dans la mémoire (seulement si cache activé)
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
            debug_message = "Nouveau calcul effectué (OCR + prédiction) et sauvegardé dans le cache"
        else:
            logger.info(f"⚠️ Cache désactivé - résultat NON sauvegardé (sera recalculé à chaque fois)")
            debug_message = "Nouveau calcul effectué (OCR + prédiction) mais NON sauvegardé - sera recalculé à chaque analyse"
        
        return JSONResponse({
            "success": True,
            "fromMemory": False,
            "cacheDisabled": disable_cache,
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

# Include the router in the main app
app.include_router(api_router)

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
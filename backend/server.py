from fastapi import FastAPI, APIRouter, UploadFile, File, Form
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
from score_predictor import calculate_probabilities
from learning import update_model, get_diff_expected


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
async def analyze(file: UploadFile = File(...)):
    """
    Analyse une image de bookmaker et prédit le score le plus probable.
    """
    try:
        # Sauvegarder l'image temporairement
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Image reçue: {file.filename}")
        
        # Extraire les informations du match (nom et bookmaker)
        match_info = extract_match_info(file_path)
        
        # Extraire les cotes via OCR
        scores = extract_odds(file_path)
        
        if not scores:
            os.remove(file_path)
            return JSONResponse({
                "error": "Aucune cote détectée dans l'image",
                "mostProbableScore": "Aucune donnée",
                "probabilities": {}
            })
        
        # Obtenir la diffExpected pour le calcul
        diff_expected = get_diff_expected()
        
        # Prédire le score avec le nouvel algorithme
        result = calculate_probabilities(scores, diff_expected)
        
        # Nettoyer le fichier temporaire
        os.remove(file_path)
        
        logger.info(f"Prédiction réussie: {result['mostProbableScore']}")
        
        # Calculer le top 3 pour le retour
        sorted_probs = sorted(result['probabilities'].items(), key=lambda x: x[1], reverse=True)
        top3 = [{"score": s, "probability": p} for s, p in sorted_probs[:3]]
        
        return JSONResponse({
            "success": True,
            "extractedScores": scores,
            "mostProbableScore": result['mostProbableScore'],
            "probabilities": result['probabilities'],
            "confidence": result.get('confidence', 0.0),
            "top3": top3
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
    Optionnel: Noms des équipes pour apprentissage contextuel.
    """
    try:
        result = update_model(predicted, real, home_team, away_team)
        
        # Gérer le cas où c'est un dict (skipped)
        if isinstance(result, dict) and result.get("skipped"):
            logger.info(f"⚠️ Apprentissage ignoré: {result.get('reason')}")
            return {
                "success": True,
                "skipped": True,
                "message": f"⚠️ {result.get('reason')}",
                "newDiffExpected": get_diff_expected()
            }
        
        if result:
            diff = get_diff_expected()
            logger.info(f"✅ Modèle ajusté: {predicted} → {real}, nouvelle diff: {diff}")
            return {
                "success": True,
                "message": f"Modèle ajusté avec le score réel: {real} ✅",
                "newDiffExpected": diff
            }
        else:
            return JSONResponse(
                {"error": "Format de score invalide. Utilisez le format X-Y (ex: 2-1)"}, 
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
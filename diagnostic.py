import os
import json
import asyncio
import importlib
import traceback
from datetime import datetime
import httpx

TEST_IMAGE_PATH = "/app/test_images/sample_ticket.png"  # mettre n'importe laquelle
OCR_ENDPOINT = "http://localhost:8001/ocr-test"
UPLOAD_ENDPOINT = "http://localhost:8001/upload-image"
LEAGUE_PATH = "/app/data/leagues/"
CACHE_PATH = "/app/data/leagues/multi_source_cache.json"
UPLOAD_DIR = "/app/data/uploads/"
SCHEDULER_FLAG = "/app/state/scheduler_status.json"


async def check_file_exists(path):
    return os.path.exists(path), f"Exists: {path}"


async def test_ocr():
    """Test OCR GPT-Vision et Tesseract"""
    # Chercher une image test
    test_image = None
    
    # Essayer différents dossiers
    test_dirs = [
        "/app/test_images",
        "/app/data/bookmaker_images",
        "/app/data/uploads"
    ]
    
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            images = [f for f in os.listdir(test_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
            if images:
                test_image = os.path.join(test_dir, images[0])
                break
    
    if not test_image:
        return False, "Aucune image test trouvée"

    results = {}

    try:
        # Test pipeline OCR
        import sys
        sys.path.insert(0, '/app')
        from core.ocr_pipeline import process_image
        
        # Test GPT-Vision
        try:
            result_gpt = process_image(test_image, prefer_gpt_vision=True)
            results["GPT-Vision"] = {
                "success": result_gpt.get("success", False),
                "engine": result_gpt.get("ocr_engine"),
                "scores_count": len(result_gpt.get("parsed_scores", [])),
                "confidence": result_gpt.get("confidence")
            }
        except Exception as e:
            results["GPT-Vision"] = {"error": str(e)}

        # Test Tesseract
        try:
            result_tess = process_image(test_image, prefer_gpt_vision=False)
            results["Tesseract"] = {
                "success": result_tess.get("success", False),
                "engine": result_tess.get("ocr_engine"),
                "scores_count": len(result_tess.get("parsed_scores", [])),
                "confidence": result_tess.get("confidence")
            }
        except Exception as e:
            results["Tesseract"] = {"error": str(e)}

        return True, results
        
    except Exception as e:
        return False, {"error": str(e), "traceback": traceback.format_exc()}


async def test_league_files():
    """Test l'intégrité des fichiers de ligues"""
    results = {}
    
    if not os.path.exists(LEAGUE_PATH):
        return False, "Dossier leagues inexistant"
    
    for f in os.listdir(LEAGUE_PATH):
        if f.endswith(".json") and not f.startswith("multi"):
            try:
                filepath = os.path.join(LEAGUE_PATH, f)
                with open(filepath, "r", encoding="utf-8") as fp:
                    data = json.load(fp)

                # Vérifier structure
                has_teams = "teams" in data or "table" in data
                has_league = "league" in data
                has_updated = "updated" in data or "updated_at" in data
                
                status = "OK" if (has_teams and has_league) else "INCOMPLETE"
                
                results[f] = {
                    "status": status,
                    "has_teams": has_teams,
                    "has_league": has_league,
                    "has_updated": has_updated,
                    "teams_count": len(data.get("teams", data.get("table", [])))
                }
            except Exception as e:
                results[f] = {"status": "ERROR", "error": str(e)}

    return True, results


async def test_cache():
    """Test le cache multi-sources"""
    if not os.path.exists(CACHE_PATH):
        return False, "Cache absent"
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        leagues_in_cache = [k for k in data.keys() if k.startswith('league:')]
        
        return True, {
            "total_entries": len(data),
            "leagues_cached": len(leagues_in_cache),
            "leagues": leagues_in_cache[:10]
        }
    except Exception as e:
        return False, {"error": str(e)}


async def test_scheduler_flag():
    """Test le statut du scheduler"""
    if not os.path.exists(SCHEDULER_FLAG):
        return False, "scheduler_status.json manquant"

    try:
        with open(SCHEDULER_FLAG, "r") as f:
            data = json.load(f)
        
        last = data.get("last_run", None)
        active = data.get("active", False)
        next_run = data.get("next_run", None)

        return True, {
            "active": active,
            "last_run": last,
            "next_run": next_run,
            "last_error": data.get("last_error")
        }
    except Exception as e:
        return False, {"error": str(e)}


async def test_upload_system():
    """Test le système d'upload"""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        return True, {"status": "Created", "count": 0}

    try:
        files = os.listdir(UPLOAD_DIR)
        return True, {
            "count": len(files),
            "examples": files[:5] if files else []
        }
    except Exception as e:
        return False, {"error": str(e)}


async def test_football_data_api():
    """Test l'API Football-Data.org"""
    KEY = os.environ.get("FOOTBALL_DATA_KEY", None)
    KEY2 = os.environ.get("FOOTBALL_DATA_KEY_2", None)
    
    if not KEY and not KEY2:
        return False, "Aucune clé API configurée"

    url = "https://api.football-data.org/v4/competitions"
    results = {}

    # Test clé 1
    if KEY:
        headers = {"X-Auth-Token": KEY}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
                results["KEY_1"] = {
                    "status": r.status_code,
                    "ok": r.status_code == 200,
                    "message": "OK" if r.status_code == 200 else r.text[:100]
                }
        except Exception as e:
            results["KEY_1"] = {"error": str(e)}

    # Test clé 2
    if KEY2:
        headers = {"X-Auth-Token": KEY2}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
                results["KEY_2"] = {
                    "status": r.status_code,
                    "ok": r.status_code == 200,
                    "message": "OK" if r.status_code == 200 else r.text[:100]
                }
        except Exception as e:
            results["KEY_2"] = {"error": str(e)}

    all_ok = all(r.get("ok", False) for r in results.values())
    return all_ok, results


async def test_config_system():
    """Test le système de configuration"""
    try:
        import sys
        sys.path.insert(0, '/app')
        from core.config import get_all_leagues, get_league_params
        
        leagues = get_all_leagues()
        sample_params = get_league_params(leagues[0]) if leagues else None
        
        return True, {
            "leagues_count": len(leagues),
            "leagues": leagues,
            "sample_league": leagues[0] if leagues else None,
            "sample_params": sample_params
        }
    except Exception as e:
        return False, {"error": str(e), "traceback": traceback.format_exc()}


async def test_database():
    """Test la base de données SQLite"""
    try:
        import sys
        sys.path.insert(0, '/app')
        from core.models import SessionLocal, UploadedImage, AnalysisResult, LearningEvent
        
        db = SessionLocal()
        
        uploads_count = db.query(UploadedImage).count()
        analyses_count = db.query(AnalysisResult).count()
        learning_count = db.query(LearningEvent).count()
        
        db.close()
        
        return True, {
            "uploads": uploads_count,
            "analyses": analyses_count,
            "learning_events": learning_count,
            "db_path": "/app/data/db/emergent.db"
        }
    except Exception as e:
        return False, {"error": str(e), "traceback": traceback.format_exc()}


async def test_learning_system():
    """Test le système d'apprentissage"""
    try:
        import sys
        sys.path.insert(0, '/app')
        from core.learning import get_learning_stats
        
        stats = get_learning_stats(days=30)
        
        return True, stats
    except Exception as e:
        return False, {"error": str(e)}


async def full_diagnostic():
    """Exécute le diagnostic complet"""
    result = {
        "timestamp": str(datetime.utcnow()),
        "system": {}
    }

    # Liste des tests
    tests = [
        ("Config System", test_config_system),
        ("Database", test_database),
        ("League Files", test_league_files),
        ("Cache", test_cache),
        ("Scheduler", test_scheduler_flag),
        ("Uploads", test_upload_system),
        ("FootballData API", test_football_data_api),
        ("Learning System", test_learning_system),
        ("OCR", test_ocr),
    ]

    for name, func in tests:
        try:
            ok, data = await func()
            result["system"][name] = {
                "status": "✅ OK" if ok else "❌ FAIL",
                "data": data
            }
        except Exception as e:
            result["system"][name] = {
                "status": "❌ ERROR",
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    # Résumé
    total = len(tests)
    passed = sum(1 for v in result["system"].values() if "✅" in v["status"])
    
    result["summary"] = {
        "total_tests": total,
        "passed": passed,
        "failed": total - passed,
        "success_rate": f"{(passed/total)*100:.1f}%"
    }

    return result


if __name__ == "__main__":
    import asyncio
    out = asyncio.run(full_diagnostic())
    print(json.dumps(out, indent=4, ensure_ascii=False))

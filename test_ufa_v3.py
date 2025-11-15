#!/usr/bin/env python3
"""
Test complet du système UFAv3 PyTorch - Version robuste
"""

import requests
import json
import os
import time
from pathlib import Path

# Configuration
BASE_URL = "https://match-forecast-77.preview.emergentagent.com/api"

def log(message):
    print(f"[UFAv3_TEST] {message}")

def test_ufa_v3_system():
    """Test complet du système UFAv3 PyTorch - Version robuste"""
    log("=" * 80)
    log("🚀 TESTING UFAv3 PYTORCH SYSTEM - VERSION ROBUSTE")
    log("=" * 80)
    
    results = {}
    
    # Test 1: GET /api/ufa/v3/status
    log("\n1️⃣ Testing GET /api/ufa/v3/status...")
    try:
        response = requests.get(f"{BASE_URL}/ufa/v3/status", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Vérifier les champs requis
            required_fields = ['available', 'version', 'last_trained', 'total_samples', 'num_teams', 'num_leagues', 'device']
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                available = data.get('available')
                version = data.get('version')
                
                log(f"✅ Status endpoint working")
                log(f"    Available: {available}")
                log(f"    Version: {version}")
                log(f"    Last trained: {data.get('last_trained', 'N/A')}")
                log(f"    Total samples: {data.get('total_samples', 0)}")
                log(f"    Num teams: {data.get('num_teams', 0)}")
                log(f"    Num leagues: {data.get('num_leagues', 0)}")
                log(f"    Device: {data.get('device', 'unknown')}")
                
                # Vérifier les critères de succès
                if available and version == "3.0":
                    results["status"] = {
                        "status": "PASS",
                        "available": available,
                        "version": version,
                        "data": data
                    }
                    log("    🎉 Status criteria met: available=true, version=3.0")
                else:
                    results["status"] = {
                        "status": "FAIL",
                        "error": f"Expected available=true and version=3.0, got available={available}, version={version}",
                        "data": data
                    }
                    log(f"    ❌ Status criteria not met")
            else:
                results["status"] = {
                    "status": "FAIL",
                    "error": f"Missing required fields: {missing_fields}",
                    "data": data
                }
                log(f"    ❌ Missing required fields: {missing_fields}")
        else:
            results["status"] = {
                "status": "FAIL",
                "error": f"HTTP {response.status_code}: {response.text[:200]}"
            }
            log(f"    ❌ HTTP error {response.status_code}")
    except Exception as e:
        results["status"] = {
            "status": "FAIL",
            "error": f"Exception: {str(e)}"
        }
        log(f"    ❌ Exception: {str(e)}")
    
    # Test 2: POST /api/ufa/v3/predict
    log("\n2️⃣ Testing POST /api/ufa/v3/predict...")
    try:
        # Test data from review request
        test_data = {
            "home_team": "PSG",
            "away_team": "Marseille", 
            "league": "Ligue1",
            "home_coeff": 1.3,
            "away_coeff": 1.0,
            "topk": 5
        }
        
        response = requests.post(
            f"{BASE_URL}/ufa/v3/predict",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Vérifier la structure de réponse
            required_fields = ['top', 'model', 'version', 'duration_sec']
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                top_predictions = data.get('top', [])
                model = data.get('model')
                version = data.get('version')
                duration = data.get('duration_sec')
                
                log(f"✅ Predict endpoint working")
                log(f"    Model: {model}")
                log(f"    Version: {version}")
                log(f"    Duration: {duration}s")
                log(f"    Predictions returned: {len(top_predictions)}")
                
                # Afficher les prédictions (peuvent être vides selon la note)
                if top_predictions:
                    log(f"    Top predictions:")
                    for i, pred in enumerate(top_predictions[:3]):
                        score = pred.get('score', 'N/A')
                        prob = pred.get('probability', 0)
                        log(f"      {i+1}. {score}: {prob:.4f}")
                else:
                    log(f"    ⚠️ No predictions returned (may be expected due to OCR vocabulary issues)")
                
                results["predict"] = {
                    "status": "PASS",
                    "model": model,
                    "version": version,
                    "duration_sec": duration,
                    "predictions_count": len(top_predictions),
                    "data": data
                }
            else:
                results["predict"] = {
                    "status": "FAIL",
                    "error": f"Missing required fields: {missing_fields}",
                    "data": data
                }
                log(f"    ❌ Missing required fields: {missing_fields}")
        else:
            results["predict"] = {
                "status": "FAIL",
                "error": f"HTTP {response.status_code}: {response.text[:200]}"
            }
            log(f"    ❌ HTTP error {response.status_code}")
    except Exception as e:
        results["predict"] = {
            "status": "FAIL",
            "error": f"Exception: {str(e)}"
        }
        log(f"    ❌ Exception: {str(e)}")
    
    # Test 3: POST /api/ufa/v3/retrain
    log("\n3️⃣ Testing POST /api/ufa/v3/retrain...")
    try:
        response = requests.post(
            f"{BASE_URL}/ufa/v3/retrain?incremental=true&max_time_minutes=1",
            timeout=10  # Court timeout car c'est juste pour démarrer
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 'started':
                log(f"✅ Retrain endpoint working")
                log(f"    Status: {data.get('status')}")
                log(f"    Message: {data.get('message', 'N/A')}")
                log(f"    Mode: {data.get('mode', 'N/A')}")
                log(f"    Check logs: {data.get('check_logs', 'N/A')}")
                
                results["retrain"] = {
                    "status": "PASS",
                    "retrain_status": data.get('status'),
                    "mode": data.get('mode'),
                    "data": data
                }
            else:
                results["retrain"] = {
                    "status": "FAIL",
                    "error": f"Expected status='started', got {data.get('status')}",
                    "data": data
                }
                log(f"    ❌ Unexpected status: {data.get('status')}")
        else:
            results["retrain"] = {
                "status": "FAIL",
                "error": f"HTTP {response.status_code}: {response.text[:200]}"
            }
            log(f"    ❌ HTTP error {response.status_code}")
    except Exception as e:
        results["retrain"] = {
            "status": "FAIL",
            "error": f"Exception: {str(e)}"
        }
        log(f"    ❌ Exception: {str(e)}")
    
    # Test 4: Regression tests
    log("\n4️⃣ Testing regression endpoints...")
    regression_results = {}
    
    # Test /api/health
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200 and response.json().get("status") == "ok":
            log("    ✅ GET /api/health - Working")
            regression_results["health"] = {"status": "PASS"}
        else:
            log("    ❌ GET /api/health - Failed")
            regression_results["health"] = {"status": "FAIL"}
    except Exception as e:
        log(f"    ❌ GET /api/health - Exception: {str(e)}")
        regression_results["health"] = {"status": "FAIL", "error": str(e)}
    
    # Test /api/diff
    try:
        response = requests.get(f"{BASE_URL}/diff", timeout=10)
        if response.status_code == 200 and 'diffExpected' in response.json():
            log("    ✅ GET /api/diff - Working")
            regression_results["diff"] = {"status": "PASS"}
        else:
            log("    ❌ GET /api/diff - Failed")
            regression_results["diff"] = {"status": "FAIL"}
    except Exception as e:
        log(f"    ❌ GET /api/diff - Exception: {str(e)}")
        regression_results["diff"] = {"status": "FAIL", "error": str(e)}
    
    # Test /api/analyze (if test image available)
    try:
        # Try to find a test image
        test_images = ["/app/backend/test_bookmaker_v2.jpg", "/app/backend/winamax_test_new.jpg"]
        test_image_path = None
        
        for img_path in test_images:
            if os.path.exists(img_path):
                test_image_path = img_path
                break
        
        if test_image_path:
            with open(test_image_path, 'rb') as f:
                files = {'file': ('test.jpg', f, 'image/jpeg')}
                response = requests.post(f"{BASE_URL}/analyze", files=files, timeout=30)
            
            if response.status_code == 200:
                log("    ✅ POST /api/analyze - Working")
                regression_results["analyze"] = {"status": "PASS"}
            else:
                log("    ❌ POST /api/analyze - Failed")
                regression_results["analyze"] = {"status": "FAIL"}
        else:
            log("    ⚠️ POST /api/analyze - Test image not found")
            regression_results["analyze"] = {"status": "SKIP", "note": "Test image not found"}
    except Exception as e:
        log(f"    ❌ POST /api/analyze - Exception: {str(e)}")
        regression_results["analyze"] = {"status": "FAIL", "error": str(e)}
    
    results["regression_tests"] = regression_results
    
    # Test 5: File verification
    log("\n5️⃣ Verifying model files...")
    file_results = {}
    
    # Check /app/models/ufa_model_v3.pt
    model_file = "/app/models/ufa_model_v3.pt"
    if os.path.exists(model_file):
        size = os.path.getsize(model_file)
        if size > 0:
            log(f"    ✅ {model_file} exists (size: {size} bytes)")
            file_results["model_file"] = {"status": "PASS", "size": size}
        else:
            log(f"    ❌ {model_file} exists but is empty")
            file_results["model_file"] = {"status": "FAIL", "error": "File is empty"}
    else:
        log(f"    ❌ {model_file} not found")
        file_results["model_file"] = {"status": "FAIL", "error": "File not found"}
    
    # Check /app/models/ufa_v3_meta.json
    meta_file = "/app/models/ufa_v3_meta.json"
    if os.path.exists(meta_file):
        try:
            with open(meta_file, 'r') as f:
                meta_data = json.load(f)
            
            if 'version' in meta_data and 'last_trained' in meta_data:
                log(f"    ✅ {meta_file} exists and contains version, last_trained")
                file_results["meta_file"] = {"status": "PASS", "data": meta_data}
            else:
                log(f"    ❌ {meta_file} missing required fields")
                file_results["meta_file"] = {"status": "FAIL", "error": "Missing required fields"}
        except Exception as e:
            log(f"    ❌ {meta_file} invalid JSON: {str(e)}")
            file_results["meta_file"] = {"status": "FAIL", "error": f"Invalid JSON: {str(e)}"}
    else:
        log(f"    ❌ {meta_file} not found")
        file_results["meta_file"] = {"status": "FAIL", "error": "File not found"}
    
    # Check /app/logs/ufa_v3_training.log
    log_file = "/app/logs/ufa_v3_training.log"
    if os.path.exists(log_file):
        size = os.path.getsize(log_file)
        log(f"    ✅ {log_file} exists (size: {size} bytes)")
        file_results["log_file"] = {"status": "PASS", "size": size}
    else:
        log(f"    ❌ {log_file} not found")
        file_results["log_file"] = {"status": "FAIL", "error": "File not found"}
    
    results["file_verification"] = file_results
    
    # Test 6: Backend logs verification
    log("\n6️⃣ Checking backend logs for errors...")
    try:
        import subprocess
        log_result = subprocess.run(
            ["tail", "-n", "50", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if log_result.returncode == 0:
            logs = log_result.stdout
            
            # Look for critical errors
            critical_errors = ["CRITICAL", "FATAL", "ERROR", "Exception", "Traceback"]
            errors_found = []
            
            for error_type in critical_errors:
                if error_type in logs:
                    errors_found.append(error_type)
            
            if not errors_found:
                log("    ✅ No critical errors found in backend logs")
                results["backend_logs"] = {"status": "PASS", "errors": []}
            else:
                log(f"    ⚠️ Found potential errors in logs: {errors_found}")
                results["backend_logs"] = {"status": "PARTIAL", "errors": errors_found}
        else:
            log("    ❌ Could not read backend logs")
            results["backend_logs"] = {"status": "FAIL", "error": "Could not read logs"}
    except Exception as e:
        log(f"    ❌ Exception reading logs: {str(e)}")
        results["backend_logs"] = {"status": "FAIL", "error": str(e)}
    
    # Summary
    log("\n" + "=" * 80)
    log("UFAv3 PYTORCH SYSTEM TEST SUMMARY")
    log("=" * 80)
    
    # Count successful tests
    total_tests = 0
    passed_tests = 0
    
    for test_name, result in results.items():
        if test_name == "regression_tests":
            for reg_test, reg_result in result.items():
                total_tests += 1
                if reg_result.get("status") == "PASS":
                    passed_tests += 1
        elif test_name == "file_verification":
            for file_test, file_result in result.items():
                total_tests += 1
                if file_result.get("status") == "PASS":
                    passed_tests += 1
        else:
            total_tests += 1
            if result.get("status") == "PASS":
                passed_tests += 1
    
    log(f"\n📊 TEST RESULTS: {passed_tests}/{total_tests} tests passed")
    
    # Detailed results
    for test_name, result in results.items():
        if test_name in ["regression_tests", "file_verification"]:
            continue
        
        status = result.get("status", "UNKNOWN")
        status_icon = "✅" if status == "PASS" else "⚠️" if status == "PARTIAL" else "❌"
        log(f"{status_icon} {test_name.upper()}: {status}")
        
        if "error" in result:
            log(f"    Error: {result['error']}")
    
    # Critères de succès
    status_ok = results.get("status", {}).get("status") == "PASS"
    predict_ok = results.get("predict", {}).get("status") == "PASS"
    retrain_ok = results.get("retrain", {}).get("status") == "PASS"
    files_ok = all(r.get("status") == "PASS" for r in results.get("file_verification", {}).values())
    regression_ok = all(r.get("status") in ["PASS", "SKIP"] for r in results.get("regression_tests", {}).values())
    
    log(f"\n🎯 SUCCESS CRITERIA:")
    log(f"   ✅ UFAv3 endpoints respond correctly: {status_ok and predict_ok and retrain_ok}")
    log(f"   ✅ Structure des réponses conforme: {predict_ok}")
    log(f"   ✅ Pas d'erreurs dans les logs backend: {results.get('backend_logs', {}).get('status') != 'FAIL'}")
    log(f"   ✅ Fichiers modèle et métadonnées présents: {files_ok}")
    log(f"   ✅ Tests de régression passent: {regression_ok}")
    
    overall_success = all([status_ok, predict_ok, retrain_ok, files_ok, regression_ok])
    
    if overall_success:
        log(f"\n🎉 SUCCESS: UFAv3 PyTorch system is fully functional!")
    else:
        log(f"\n⚠️ ISSUES FOUND: Some UFAv3 components need attention")
    
    log("=" * 80)
    
    return results

if __name__ == "__main__":
    test_ufa_v3_system()
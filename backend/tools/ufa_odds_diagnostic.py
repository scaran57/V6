#!/usr/bin/env python3
"""
UFA Odds Diagnostic Script
Teste tous les endpoints liés à l'intégration The Odds API + UFAv3
"""
import requests
import json
import traceback
from datetime import datetime

BASE_URL = "http://localhost:8001/api/ufa/v3"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_endpoint(name, url, method="GET", data=None):
    log(f"🔍 Test de l'endpoint {name} ...")
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=data, timeout=10)
        
        if r.status_code == 200:
            log(f"✅ {name} OK - {len(r.text)} caractères reçus")
            try:
                return r.json()
            except:
                return r.text
        else:
            log(f"❌ {name} renvoie une erreur {r.status_code}")
            log(f"Réponse : {r.text[:500]}")
            return None
    except Exception as e:
        log(f"⚠️ Erreur lors de la requête {name}: {e}")
        traceback.print_exc()
        return None

def test_predict_with_odds():
    log("🚀 Test de /predict-with-odds avec données réelles...")
    
    payload = {
        "home_team": "PSG",
        "away_team": "Marseille",
        "league": "Ligue1",
        "home_coeff": 1.3,
        "away_coeff": 1.0,
        "topk": 5
    }
    
    try:
        r = requests.post(
            f"{BASE_URL}/predict-with-odds",
            json=payload,
            timeout=15
        )
        
        if r.status_code == 200:
            data = r.json()
            log(f"✅ /predict-with-odds fonctionne")
            log(f"   Model: {data.get('model')}")
            log(f"   Duration: {data.get('duration_sec')}s")
            log(f"   Top scores: {len(data.get('top_scores', []))} résultats")
            log(f"   Odds présentes: {data.get('odds') is not None}")
            log(f"   Delta calculé: {data.get('delta') is not None}")
        else:
            log(f"❌ /predict-with-odds renvoie {r.status_code}")
            log("🧾 Contenu de l'erreur :")
            print(r.text[:800])
            
    except Exception as e:
        log("💥 Exception pendant /predict-with-odds")
        traceback.print_exc()

def test_odds_data_file():
    log("📄 Vérification du fichier odds_data.jsonl ...")
    try:
        import os
        odds_file = "/app/data/odds_data.jsonl"
        
        if os.path.exists(odds_file):
            with open(odds_file, 'r') as f:
                lines = f.readlines()
            log(f"✅ Fichier odds_data.jsonl existe - {len(lines)} lignes")
            
            # Afficher un exemple
            if lines:
                sample = json.loads(lines[0])
                log(f"   Exemple : {sample.get('home_team')} vs {sample.get('away_team')}")
                log(f"   Ligue : {sample.get('league_name')}")
        else:
            log(f"❌ Fichier odds_data.jsonl n'existe pas")
            
    except Exception as e:
        log(f"⚠️ Erreur lecture fichier odds: {e}")
        traceback.print_exc()

def test_model_file():
    log("🧠 Vérification du modèle UFAv3 ...")
    try:
        import os
        model_file = "/app/models/ufa_model_v3.pt"
        
        if os.path.exists(model_file):
            size = os.path.getsize(model_file) / 1024
            log(f"✅ Modèle UFAv3 existe - {size:.2f} KB")
        else:
            log(f"❌ Modèle UFAv3 n'existe pas à {model_file}")
            
    except Exception as e:
        log(f"⚠️ Erreur vérification modèle: {e}")

def run_diagnostic():
    log("=" * 70)
    log("===== DÉBUT DU DIAGNOSTIC UFAv3/ODDS =====")
    log("=" * 70)
    
    # Test 1: Status UFAv3
    log("\n📊 TEST 1: Status UFAv3")
    api_status = test_endpoint("UFAv3 Status", f"{BASE_URL}/status")
    if api_status:
        log(f"   - Available: {api_status.get('available')}")
        log(f"   - Teams: {api_status.get('num_teams')}")
        log(f"   - Leagues: {api_status.get('num_leagues')}")
    
    # Test 2: Odds Stats
    log("\n🎲 TEST 2: Odds API Stats")
    odds_stats = test_endpoint("Odds Stats", f"{BASE_URL}/odds-stats")
    if odds_stats:
        log(f"   - Total records: {odds_stats.get('total_records')}")
        log(f"   - Leagues: {', '.join(odds_stats.get('leagues', []))}")
        log(f"   - Last update: {odds_stats.get('last_update')}")
    
    # Test 3: Predict standard
    log("\n🎯 TEST 3: Predict (sans odds)")
    predict_payload = {
        "home_team": "PSG",
        "away_team": "Marseille",
        "league": "Ligue1",
        "home_coeff": 1.3,
        "away_coeff": 1.0,
        "topk": 3
    }
    predict_result = test_endpoint(
        "Predict Standard",
        f"{BASE_URL}/predict",
        method="POST",
        data=predict_payload
    )
    if predict_result:
        log(f"   - Top predictions: {len(predict_result.get('top', []))}")
    
    # Test 4: Predict with odds
    log("\n🎰 TEST 4: Predict with Odds")
    test_predict_with_odds()
    
    # Test 5: Fichiers
    log("\n📁 TEST 5: Vérification des fichiers")
    test_odds_data_file()
    test_model_file()
    
    # Test 6: Import Python
    log("\n🐍 TEST 6: Import des modules Python")
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        
        from tools.odds_api_integration import get_ingestion_stats
        log("✅ Module odds_api_integration importé")
        
        from ufa.ufa_v3_for_emergent import predict_single_with_odds
        log("✅ Fonction predict_single_with_odds importée")
        
    except Exception as e:
        log(f"❌ Erreur import: {e}")
        traceback.print_exc()
    
    log("\n" + "=" * 70)
    log("===== FIN DU DIAGNOSTIC =====")
    log("=" * 70)

if __name__ == "__main__":
    run_diagnostic()

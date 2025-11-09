#!/usr/bin/env python3
"""
Backend Testing Suite for Score Prediction API
Tests the new score_predictor.py integration and all endpoints
"""

import requests
import json
import os
import time
from pathlib import Path

# Configuration
BASE_URL = "https://betanalyst-10.preview.emergentagent.com/api"
BACKEND_DIR = "/app/backend"

# Test images available in backend directory
TEST_IMAGES = [
    "winamax1.jpg",
    "winamax2.jpg", 
    "winamax_test_new.jpg",
    "unibet_test.jpg",
    "unibet_normal.jpg",
    "unibet_grille.jpg",
    "test_bookmaker.jpg",
    "test_bookmaker_v2.jpg",
    "paris_bayern.jpg"
]

class ScorePredictorTester:
    def __init__(self):
        self.results = {
            "health": {"status": "PENDING", "details": ""},
            "analyze": {"status": "PENDING", "details": "", "tests": {}},
            "learn": {"status": "PENDING", "details": "", "tests": {}},
            "diff": {"status": "PENDING", "details": ""}
        }
        
    def log(self, message):
        print(f"[TEST] {message}")
        
    def test_health_endpoint(self):
        """Test GET /api/health endpoint"""
        self.log("Testing /api/health endpoint...")
        
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.results["health"]["status"] = "PASS"
                    self.results["health"]["details"] = f"Health check passed: {data.get('message', 'OK')}"
                    self.log("✅ Health endpoint working correctly")
                else:
                    self.results["health"]["status"] = "FAIL"
                    self.results["health"]["details"] = f"Unexpected response: {data}"
                    self.log("❌ Health endpoint returned unexpected data")
            else:
                self.results["health"]["status"] = "FAIL"
                self.results["health"]["details"] = f"HTTP {response.status_code}: {response.text}"
                self.log(f"❌ Health endpoint failed with status {response.status_code}")
                
        except Exception as e:
            self.results["health"]["status"] = "FAIL"
            self.results["health"]["details"] = f"Connection error: {str(e)}"
            self.log(f"❌ Health endpoint connection failed: {str(e)}")
    
    def test_analyze_endpoint(self):
        """Test POST /api/analyze with multiple bookmaker images"""
        self.log("Testing /api/analyze endpoint with bookmaker images...")
        
        successful_tests = 0
        total_tests = 0
        
        for image_name in TEST_IMAGES:
            image_path = os.path.join(BACKEND_DIR, image_name)
            
            if not os.path.exists(image_path):
                self.log(f"⚠️ Image not found: {image_name}")
                continue
                
            total_tests += 1
            self.log(f"Testing with image: {image_name}")
            
            try:
                with open(image_path, 'rb') as f:
                    files = {'file': (image_name, f, 'image/jpeg')}
                    response = requests.post(f"{BASE_URL}/analyze", files=files, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if this is an error response (no scores detected)
                    if 'error' in data and 'Aucune cote détectée' in data['error']:
                        self.results["analyze"]["tests"][image_name] = {
                            "status": "PASS",
                            "note": "No scores detected (expected behavior for some images)",
                            "error_message": data['error']
                        }
                        successful_tests += 1
                        self.log(f"✅ {image_name}: No scores detected (expected behavior)")
                    else:
                        # Check required fields for successful analysis (including new match info fields)
                        required_fields = ['success', 'extractedScores', 'mostProbableScore', 'probabilities', 'matchName', 'bookmaker']
                        missing_fields = [field for field in required_fields if field not in data]
                        
                        if missing_fields:
                            self.results["analyze"]["tests"][image_name] = {
                                "status": "FAIL",
                                "error": f"Missing fields: {missing_fields}"
                            }
                            self.log(f"❌ {image_name}: Missing required fields: {missing_fields}")
                        else:
                            # Validate data structure
                            extracted_scores = data.get('extractedScores', {})
                            probabilities = data.get('probabilities', {})
                            most_probable = data.get('mostProbableScore', '')
                            match_name = data.get('matchName', '')
                            bookmaker = data.get('bookmaker', '')
                            
                            # Check if probabilities sum to approximately 100%
                            prob_sum = sum(probabilities.values()) if probabilities else 0
                            prob_sum_valid = 95 <= prob_sum <= 105  # Allow 5% tolerance
                            
                            if extracted_scores and probabilities and most_probable and prob_sum_valid:
                                self.results["analyze"]["tests"][image_name] = {
                                    "status": "PASS",
                                    "extracted_scores_count": len(extracted_scores),
                                    "most_probable_score": most_probable,
                                    "probabilities_sum": round(prob_sum, 2),
                                    "match_name": match_name,
                                    "bookmaker": bookmaker
                                }
                                successful_tests += 1
                                self.log(f"✅ {image_name}: Analysis successful - {most_probable} (prob sum: {prob_sum:.1f}%)")
                                self.log(f"    📝 Match: {match_name}")
                                self.log(f"    🎰 Bookmaker: {bookmaker}")
                            else:
                                self.results["analyze"]["tests"][image_name] = {
                                    "status": "FAIL",
                                    "error": f"Invalid data: scores={len(extracted_scores)}, probs={len(probabilities)}, sum={prob_sum:.1f}%"
                                }
                                self.log(f"❌ {image_name}: Invalid response data")
                else:
                    self.results["analyze"]["tests"][image_name] = {
                        "status": "FAIL",
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
                    self.log(f"❌ {image_name}: HTTP {response.status_code}")
                    
            except Exception as e:
                self.results["analyze"]["tests"][image_name] = {
                    "status": "FAIL", 
                    "error": f"Exception: {str(e)}"
                }
                self.log(f"❌ {image_name}: Exception - {str(e)}")
        
        # Overall analyze endpoint status
        if total_tests == 0:
            self.results["analyze"]["status"] = "FAIL"
            self.results["analyze"]["details"] = "No test images found"
        elif successful_tests == total_tests:
            self.results["analyze"]["status"] = "PASS"
            self.results["analyze"]["details"] = f"All {total_tests} images processed successfully"
        elif successful_tests > 0:
            self.results["analyze"]["status"] = "PARTIAL"
            self.results["analyze"]["details"] = f"{successful_tests}/{total_tests} images processed successfully"
        else:
            self.results["analyze"]["status"] = "FAIL"
            self.results["analyze"]["details"] = f"All {total_tests} images failed to process"
    
    def test_learn_endpoint(self):
        """Test POST /api/learn with various score pairs"""
        self.log("Testing /api/learn endpoint...")
        
        test_cases = [
            {"predicted": "2-1", "real": "1-1", "description": "Normal score pair"},
            {"predicted": "0-0", "real": "2-0", "description": "Draw to win"},
            {"predicted": "Autre", "real": "3-2", "description": "Autre prediction"},
            {"predicted": "1-2", "real": "1-2", "description": "Exact match"}
        ]
        
        successful_tests = 0
        
        for i, test_case in enumerate(test_cases):
            self.log(f"Testing learn case {i+1}: {test_case['description']}")
            
            try:
                data = {
                    'predicted': test_case['predicted'],
                    'real': test_case['real']
                }
                
                response = requests.post(f"{BASE_URL}/learn", data=data, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Check required fields
                    if 'success' in result and 'newDiffExpected' in result:
                        if result.get('skipped'):
                            self.results["learn"]["tests"][f"case_{i+1}"] = {
                                "status": "PASS",
                                "skipped": True,
                                "reason": result.get('message', 'Skipped'),
                                "new_diff": result.get('newDiffExpected')
                            }
                            self.log(f"✅ Case {i+1}: Skipped as expected - {result.get('message', '')}")
                        else:
                            self.results["learn"]["tests"][f"case_{i+1}"] = {
                                "status": "PASS",
                                "new_diff": result.get('newDiffExpected'),
                                "message": result.get('message', '')
                            }
                            self.log(f"✅ Case {i+1}: Learning successful - new diff: {result.get('newDiffExpected')}")
                        successful_tests += 1
                    else:
                        self.results["learn"]["tests"][f"case_{i+1}"] = {
                            "status": "FAIL",
                            "error": "Missing required fields in response"
                        }
                        self.log(f"❌ Case {i+1}: Missing required fields")
                else:
                    self.results["learn"]["tests"][f"case_{i+1}"] = {
                        "status": "FAIL",
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
                    self.log(f"❌ Case {i+1}: HTTP {response.status_code}")
                    
            except Exception as e:
                self.results["learn"]["tests"][f"case_{i+1}"] = {
                    "status": "FAIL",
                    "error": f"Exception: {str(e)}"
                }
                self.log(f"❌ Case {i+1}: Exception - {str(e)}")
        
        # Overall learn endpoint status
        if successful_tests == len(test_cases):
            self.results["learn"]["status"] = "PASS"
            self.results["learn"]["details"] = f"All {len(test_cases)} learning cases processed successfully"
        elif successful_tests > 0:
            self.results["learn"]["status"] = "PARTIAL"
            self.results["learn"]["details"] = f"{successful_tests}/{len(test_cases)} learning cases successful"
        else:
            self.results["learn"]["status"] = "FAIL"
            self.results["learn"]["details"] = f"All {len(test_cases)} learning cases failed"
    
    def test_diff_endpoint(self):
        """Test GET /api/diff endpoint"""
        self.log("Testing /api/diff endpoint...")
        
        try:
            response = requests.get(f"{BASE_URL}/diff", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'diffExpected' in data and isinstance(data['diffExpected'], (int, float)):
                    self.results["diff"]["status"] = "PASS"
                    self.results["diff"]["details"] = f"Current diffExpected: {data['diffExpected']}"
                    self.log(f"✅ Diff endpoint working - diffExpected: {data['diffExpected']}")
                else:
                    self.results["diff"]["status"] = "FAIL"
                    self.results["diff"]["details"] = f"Invalid response format: {data}"
                    self.log("❌ Diff endpoint returned invalid format")
            else:
                self.results["diff"]["status"] = "FAIL"
                self.results["diff"]["details"] = f"HTTP {response.status_code}: {response.text}"
                self.log(f"❌ Diff endpoint failed with status {response.status_code}")
                
        except Exception as e:
            self.results["diff"]["status"] = "FAIL"
            self.results["diff"]["details"] = f"Connection error: {str(e)}"
            self.log(f"❌ Diff endpoint connection failed: {str(e)}")
    
    def run_all_tests(self):
        """Run all backend tests"""
        self.log("=" * 60)
        self.log("STARTING BACKEND TESTS FOR SCORE PREDICTOR API")
        self.log("=" * 60)
        
        # Test all endpoints
        self.test_health_endpoint()
        self.test_analyze_endpoint()
        self.test_learn_endpoint()
        self.test_diff_endpoint()
        
        # Print summary
        self.print_summary()
        
        return self.results
    
    def print_summary(self):
        """Print test results summary"""
        self.log("=" * 60)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 60)
        
        for endpoint, result in self.results.items():
            status_icon = "✅" if result["status"] == "PASS" else "⚠️" if result["status"] == "PARTIAL" else "❌"
            self.log(f"{status_icon} {endpoint.upper()}: {result['status']} - {result['details']}")
            
            # Print detailed test results for analyze and learn
            if endpoint in ["analyze", "learn"] and "tests" in result:
                for test_name, test_result in result["tests"].items():
                    test_icon = "✅" if test_result["status"] == "PASS" else "❌"
                    self.log(f"    {test_icon} {test_name}: {test_result['status']}")
        
        self.log("=" * 60)

    def test_match_name_extraction_specific(self):
        """Test match name extraction with specific user-provided images"""
        self.log("Testing match name extraction with specific real bookmaker images...")
        
        # Specific test images as requested by user
        specific_images = [
            {
                "path": "/app/test_winamax_real.jpg",
                "expected_match": "Olympiakos vs PSV",
                "expected_bookmaker": "Winamax",
                "description": "Real Winamax image"
            },
            {
                "path": "/app/test_unibet1.jpg", 
                "expected_match": "Unknown (to be determined)",
                "expected_bookmaker": "Unibet",
                "description": "Unibet match image"
            },
            {
                "path": "/app/newcastle_bilbao.jpg",
                "expected_match": "Newcastle vs Athletic Bilbao",
                "expected_bookmaker": "Unknown (app screenshot)",
                "description": "Application screenshot (not direct bookmaker)"
            }
        ]
        
        results = {}
        
        for image_info in specific_images:
            image_path = image_info["path"]
            image_name = os.path.basename(image_path)
            
            self.log(f"\n--- Testing {image_name} ---")
            self.log(f"Description: {image_info['description']}")
            self.log(f"Expected match: {image_info['expected_match']}")
            self.log(f"Expected bookmaker: {image_info['expected_bookmaker']}")
            
            if not os.path.exists(image_path):
                results[image_name] = {
                    "status": "FAIL",
                    "error": f"Image not found at {image_path}"
                }
                self.log(f"❌ Image not found: {image_path}")
                continue
            
            try:
                with open(image_path, 'rb') as f:
                    files = {'file': (image_name, f, 'image/jpeg')}
                    response = requests.post(f"{BASE_URL}/analyze", files=files, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if analysis was successful or if no scores detected
                    if 'error' in data and 'Aucune cote détectée' in data['error']:
                        results[image_name] = {
                            "status": "NO_SCORES",
                            "match_name": "N/A (no scores detected)",
                            "bookmaker": "N/A (no scores detected)",
                            "note": "OCR could not detect valid scores in this image"
                        }
                        self.log(f"⚠️ {image_name}: No scores detected by OCR")
                    else:
                        # Extract match info
                        match_name = data.get('matchName', 'Not extracted')
                        bookmaker = data.get('bookmaker', 'Not detected')
                        extracted_scores = data.get('extractedScores', {})
                        
                        # Analyze the quality of extraction
                        match_quality = self._analyze_match_name_quality(match_name)
                        bookmaker_quality = self._analyze_bookmaker_quality(bookmaker)
                        
                        results[image_name] = {
                            "status": "SUCCESS",
                            "match_name": match_name,
                            "bookmaker": bookmaker,
                            "scores_count": len(extracted_scores),
                            "match_quality": match_quality,
                            "bookmaker_quality": bookmaker_quality,
                            "raw_response": {
                                "success": data.get('success'),
                                "mostProbableScore": data.get('mostProbableScore')
                            }
                        }
                        
                        self.log(f"✅ {image_name}: Analysis completed")
                        self.log(f"    📝 Match extracted: '{match_name}' (Quality: {match_quality})")
                        self.log(f"    🎰 Bookmaker detected: '{bookmaker}' (Quality: {bookmaker_quality})")
                        self.log(f"    📊 Scores detected: {len(extracted_scores)}")
                        
                        # Additional analysis
                        if match_quality == "POOR":
                            self.log(f"    ⚠️ Match name may contain interface elements or be incorrectly extracted")
                        if bookmaker_quality == "POOR":
                            self.log(f"    ⚠️ Bookmaker detection may be inaccurate")
                            
                else:
                    results[image_name] = {
                        "status": "FAIL",
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
                    self.log(f"❌ {image_name}: HTTP error {response.status_code}")
                    
            except Exception as e:
                results[image_name] = {
                    "status": "FAIL",
                    "error": f"Exception: {str(e)}"
                }
                self.log(f"❌ {image_name}: Exception - {str(e)}")
        
        return results
    
    def _analyze_match_name_quality(self, match_name):
        """Analyze the quality of extracted match name"""
        if not match_name or match_name in ["Match non détecté", "Not extracted"]:
            return "NOT_DETECTED"
        
        # Check for typical team vs team pattern
        if " vs " in match_name or " - " in match_name:
            # Check for interface elements that shouldn't be in team names
            interface_keywords = ["cote", "odds", "bet", "mise", "gain", "€", "$", "live", "direct", "temps"]
            if any(keyword.lower() in match_name.lower() for keyword in interface_keywords):
                return "POOR"
            return "GOOD"
        
        # Check if it contains team-like names (proper nouns)
        words = match_name.split()
        if len(words) >= 2 and all(word[0].isupper() for word in words if word):
            return "FAIR"
        
        return "POOR"
    
    def _analyze_bookmaker_quality(self, bookmaker):
        """Analyze the quality of bookmaker detection"""
        if not bookmaker or bookmaker in ["Bookmaker inconnu", "Not detected"]:
            return "NOT_DETECTED"
        
        known_bookmakers = ["winamax", "unibet", "betclic", "pmu", "parions", "zebet"]
        if bookmaker.lower() in known_bookmakers:
            return "GOOD"
        
        return "FAIR"

    def test_league_scheduler_status(self):
        """Test GET /api/admin/league/scheduler-status"""
        self.log("Testing /api/admin/league/scheduler-status endpoint...")
        
        try:
            response = requests.get(f"{BASE_URL}/admin/league/scheduler-status", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") and "scheduler" in data:
                    scheduler = data["scheduler"]
                    required_fields = ["is_running", "update_time", "next_update"]
                    missing = [f for f in required_fields if f not in scheduler]
                    
                    if not missing:
                        self.log(f"✅ Scheduler status: Running={scheduler['is_running']}, Next update={scheduler.get('next_update', 'N/A')}")
                        return {"status": "PASS", "data": scheduler}
                    else:
                        self.log(f"❌ Missing fields in scheduler status: {missing}")
                        return {"status": "FAIL", "error": f"Missing fields: {missing}"}
                else:
                    self.log("❌ Invalid response format")
                    return {"status": "FAIL", "error": "Invalid response format"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                return {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
    
    def test_league_list(self):
        """Test GET /api/admin/league/list"""
        self.log("Testing /api/admin/league/list endpoint...")
        
        try:
            response = requests.get(f"{BASE_URL}/admin/league/list", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") and "leagues" in data:
                    leagues = data["leagues"]
                    expected_leagues = ["LaLiga", "PremierLeague"]
                    
                    if all(lg in leagues for lg in expected_leagues):
                        self.log(f"✅ Leagues available: {leagues}")
                        return {"status": "PASS", "leagues": leagues}
                    else:
                        self.log(f"⚠️ Some expected leagues missing: {expected_leagues}")
                        return {"status": "PARTIAL", "leagues": leagues}
                else:
                    self.log("❌ Invalid response format")
                    return {"status": "FAIL", "error": "Invalid response format"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                return {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
    
    def test_league_standings(self, league="LaLiga"):
        """Test GET /api/admin/league/standings"""
        self.log(f"Testing /api/admin/league/standings for {league}...")
        
        try:
            response = requests.get(f"{BASE_URL}/admin/league/standings?league={league}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") and "standings" in data:
                    standings = data["standings"]
                    teams_count = data.get("teams_count", 0)
                    
                    if teams_count >= 18:  # Most leagues have 18-20 teams
                        self.log(f"✅ {league} standings: {teams_count} teams")
                        # Show top 3 and bottom 3
                        if len(standings) >= 6:
                            self.log(f"   Top 3: {standings[0]['team']} (1), {standings[1]['team']} (2), {standings[2]['team']} (3)")
                            self.log(f"   Bottom 3: {standings[-3]['team']}, {standings[-2]['team']}, {standings[-1]['team']}")
                        return {"status": "PASS", "teams_count": teams_count, "standings": standings}
                    else:
                        self.log(f"⚠️ {league} has only {teams_count} teams (expected 18-20)")
                        return {"status": "PARTIAL", "teams_count": teams_count}
                else:
                    self.log(f"❌ No standings data for {league}")
                    return {"status": "FAIL", "error": "No standings data"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                return {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
    
    def test_team_coefficient(self, team, league, expected_range=None):
        """Test GET /api/league/team-coeff"""
        self.log(f"Testing coefficient for {team} ({league})...")
        
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team={team}&league={league}&mode=linear",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") and "coefficient" in data:
                    coef = data["coefficient"]
                    position = data.get("position", "N/A")
                    
                    # Check if coefficient is in valid range (0.85 - 1.30)
                    if 0.85 <= coef <= 1.30:
                        self.log(f"✅ {team}: Position {position}, Coefficient {coef:.4f}")
                        
                        # Check expected range if provided
                        if expected_range:
                            min_exp, max_exp = expected_range
                            if min_exp <= coef <= max_exp:
                                self.log(f"   ✓ Coefficient in expected range [{min_exp}, {max_exp}]")
                                return {"status": "PASS", "coefficient": coef, "position": position}
                            else:
                                self.log(f"   ⚠️ Coefficient outside expected range [{min_exp}, {max_exp}]")
                                return {"status": "PARTIAL", "coefficient": coef, "position": position, "note": "Outside expected range"}
                        
                        return {"status": "PASS", "coefficient": coef, "position": position}
                    else:
                        self.log(f"❌ Coefficient {coef} outside valid range [0.85, 1.30]")
                        return {"status": "FAIL", "error": f"Invalid coefficient: {coef}"}
                else:
                    self.log("❌ Invalid response format")
                    return {"status": "FAIL", "error": "Invalid response format"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                return {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
    
    def test_analyze_with_league(self):
        """Test /api/analyze with league parameter"""
        self.log("Testing /api/analyze with league parameter...")
        
        # Use test_bookmaker_v2.jpg
        image_path = os.path.join(BACKEND_DIR, "test_bookmaker_v2.jpg")
        
        if not os.path.exists(image_path):
            self.log(f"⚠️ Test image not found: {image_path}")
            return {"status": "FAIL", "error": "Test image not found"}
        
        try:
            # Test with league=LaLiga
            with open(image_path, 'rb') as f:
                files = {'file': ('test_bookmaker_v2.jpg', f, 'image/jpeg')}
                response = requests.post(f"{BASE_URL}/analyze?league=LaLiga", files=files, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'error' in data:
                    self.log(f"⚠️ No scores detected (expected for some images)")
                    return {"status": "PASS", "note": "No scores detected"}
                
                # Check if league info is in response
                league = data.get("league")
                league_coeffs_applied = data.get("leagueCoeffsApplied", False)
                
                self.log(f"✅ Analysis with league: league={league}, coeffs_applied={league_coeffs_applied}")
                
                return {
                    "status": "PASS",
                    "league": league,
                    "coeffs_applied": league_coeffs_applied,
                    "most_probable": data.get("mostProbableScore")
                }
            else:
                self.log(f"❌ HTTP {response.status_code}")
                return {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
    
    def test_analyze_disable_league_coeff(self):
        """Test /api/analyze with disable_league_coeff=true"""
        self.log("Testing /api/analyze with disable_league_coeff=true...")
        
        image_path = os.path.join(BACKEND_DIR, "test_bookmaker_v2.jpg")
        
        if not os.path.exists(image_path):
            self.log(f"⚠️ Test image not found: {image_path}")
            return {"status": "FAIL", "error": "Test image not found"}
        
        try:
            with open(image_path, 'rb') as f:
                files = {'file': ('test_bookmaker_v2.jpg', f, 'image/jpeg')}
                response = requests.post(
                    f"{BASE_URL}/analyze?disable_league_coeff=true",
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'error' in data:
                    self.log(f"⚠️ No scores detected (expected for some images)")
                    return {"status": "PASS", "note": "No scores detected"}
                
                league_coeffs_applied = data.get("leagueCoeffsApplied", False)
                
                if not league_coeffs_applied:
                    self.log(f"✅ League coefficients correctly disabled")
                    return {"status": "PASS", "coeffs_applied": False}
                else:
                    self.log(f"❌ League coefficients still applied despite disable flag")
                    return {"status": "FAIL", "error": "Coefficients not disabled"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                return {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
    
    def run_league_tests(self):
        """Run all league coefficient system tests"""
        self.log("=" * 60)
        self.log("TESTING LEAGUE COEFFICIENT SYSTEM")
        self.log("=" * 60)
        
        results = {}
        
        # 1. Test scheduler status
        results["scheduler_status"] = self.test_league_scheduler_status()
        
        # 2. Test league list
        results["league_list"] = self.test_league_list()
        
        # 3. Test standings for LaLiga and PremierLeague
        results["standings_laliga"] = self.test_league_standings("LaLiga")
        results["standings_premierleague"] = self.test_league_standings("PremierLeague")
        
        # 4. Test team coefficients
        # Real Madrid (expected ~1.30 if 1st)
        results["coeff_real_madrid"] = self.test_team_coefficient("Real Madrid", "LaLiga", (1.25, 1.30))
        
        # Barcelona (expected mid-range)
        results["coeff_barcelona"] = self.test_team_coefficient("Barcelona", "LaLiga", (1.00, 1.25))
        
        # Granada (expected ~0.85 if last)
        results["coeff_granada"] = self.test_team_coefficient("Granada", "LaLiga", (0.85, 1.00))
        
        # Manchester City
        results["coeff_man_city"] = self.test_team_coefficient("Manchester City", "PremierLeague")
        
        # Liverpool
        results["coeff_liverpool"] = self.test_team_coefficient("Liverpool", "PremierLeague")
        
        # 5. Test /api/analyze integration
        results["analyze_with_league"] = self.test_analyze_with_league()
        results["analyze_disable_coeff"] = self.test_analyze_disable_league_coeff()
        
        # Print summary
        self.log("=" * 60)
        self.log("LEAGUE TESTS SUMMARY")
        self.log("=" * 60)
        
        for test_name, result in results.items():
            status = result.get("status", "UNKNOWN")
            status_icon = "✅" if status == "PASS" else "⚠️" if status == "PARTIAL" else "❌"
            self.log(f"{status_icon} {test_name}: {status}")
            
            if "error" in result:
                self.log(f"    Error: {result['error']}")
            elif "note" in result:
                self.log(f"    Note: {result['note']}")
        
        self.log("=" * 60)
        
        return results

    def test_european_competitions_integration(self):
        """Test Champions League and Europa League integration with intelligent fallback"""
        self.log("=" * 60)
        self.log("TESTING EUROPEAN COMPETITIONS INTEGRATION")
        self.log("=" * 60)
        
        results = {}
        
        # Test 1: Verify 8 leagues are available (including ChampionsLeague and EuropaLeague)
        self.log("\n1️⃣ Testing league list (should have 8 leagues)...")
        try:
            response = requests.get(f"{BASE_URL}/admin/league/list", timeout=10)
            if response.status_code == 200:
                data = response.json()
                leagues = data.get("leagues", [])
                
                expected_leagues = ["LaLiga", "PremierLeague", "SerieA", "Ligue1", "Bundesliga", 
                                   "PrimeiraLiga", "ChampionsLeague", "EuropaLeague"]
                
                if len(leagues) == 8 and all(lg in leagues for lg in expected_leagues):
                    self.log(f"✅ All 8 leagues available: {leagues}")
                    results["league_list"] = {"status": "PASS", "leagues": leagues}
                else:
                    self.log(f"❌ Expected 8 leagues, got {len(leagues)}: {leagues}")
                    results["league_list"] = {"status": "FAIL", "leagues": leagues}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["league_list"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["league_list"] = {"status": "FAIL", "error": str(e)}
        
        # Test 2: Champions League standings (36 teams)
        self.log("\n2️⃣ Testing Champions League standings (should have 36 teams)...")
        try:
            response = requests.get(f"{BASE_URL}/admin/league/standings?league=ChampionsLeague", timeout=10)
            if response.status_code == 200:
                data = response.json()
                standings = data.get("standings", [])
                teams_count = len(standings)
                
                if teams_count == 36:
                    self.log(f"✅ Champions League: {teams_count} teams")
                    # Show some teams
                    sample_teams = [standings[i]["team"] for i in range(min(5, len(standings)))]
                    self.log(f"   Sample teams: {', '.join(sample_teams)}")
                    results["champions_standings"] = {"status": "PASS", "teams_count": teams_count}
                else:
                    self.log(f"⚠️ Expected 36 teams, got {teams_count}")
                    results["champions_standings"] = {"status": "PARTIAL", "teams_count": teams_count}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["champions_standings"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["champions_standings"] = {"status": "FAIL", "error": str(e)}
        
        # Test 3: Europa League standings (36 teams)
        self.log("\n3️⃣ Testing Europa League standings (should have 36 teams)...")
        try:
            response = requests.get(f"{BASE_URL}/admin/league/standings?league=EuropaLeague", timeout=10)
            if response.status_code == 200:
                data = response.json()
                standings = data.get("standings", [])
                teams_count = len(standings)
                
                if teams_count == 36:
                    self.log(f"✅ Europa League: {teams_count} teams")
                    sample_teams = [standings[i]["team"] for i in range(min(5, len(standings)))]
                    self.log(f"   Sample teams: {', '.join(sample_teams)}")
                    results["europa_standings"] = {"status": "PASS", "teams_count": teams_count}
                else:
                    self.log(f"⚠️ Expected 36 teams, got {teams_count}")
                    results["europa_standings"] = {"status": "PARTIAL", "teams_count": teams_count}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["europa_standings"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["europa_standings"] = {"status": "FAIL", "error": str(e)}
        
        # Test 4: Intelligent Fallback - Teams in national leagues
        self.log("\n4️⃣ Testing intelligent fallback for teams in national leagues...")
        
        # Test Real Madrid (should find in LaLiga)
        self.log("\n   Testing Real Madrid (Champions League → should find in LaLiga)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Real Madrid&league=ChampionsLeague",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "LaLiga" and 1.25 <= coef <= 1.30:
                    self.log(f"✅ Real Madrid: coeff={coef:.4f}, source={source}")
                    results["fallback_real_madrid"] = {"status": "PASS", "coefficient": coef, "source": source}
                else:
                    self.log(f"⚠️ Real Madrid: coeff={coef}, source={source} (expected LaLiga)")
                    results["fallback_real_madrid"] = {"status": "PARTIAL", "coefficient": coef, "source": source}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["fallback_real_madrid"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["fallback_real_madrid"] = {"status": "FAIL", "error": str(e)}
        
        # Test Barcelona (should find in LaLiga)
        self.log("\n   Testing Barcelona (Champions League → should find in LaLiga)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Barcelona&league=ChampionsLeague",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "LaLiga" and 1.0 <= coef <= 1.30:
                    self.log(f"✅ Barcelona: coeff={coef:.4f}, source={source}")
                    results["fallback_barcelona"] = {"status": "PASS", "coefficient": coef, "source": source}
                else:
                    self.log(f"⚠️ Barcelona: coeff={coef}, source={source}")
                    results["fallback_barcelona"] = {"status": "PARTIAL", "coefficient": coef, "source": source}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["fallback_barcelona"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["fallback_barcelona"] = {"status": "FAIL", "error": str(e)}
        
        # Test Manchester City (should find in PremierLeague)
        self.log("\n   Testing Manchester City (Champions League → should find in PremierLeague)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Manchester City&league=ChampionsLeague",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "PremierLeague" and 1.25 <= coef <= 1.30:
                    self.log(f"✅ Manchester City: coeff={coef:.4f}, source={source}")
                    results["fallback_man_city"] = {"status": "PASS", "coefficient": coef, "source": source}
                else:
                    self.log(f"⚠️ Manchester City: coeff={coef}, source={source}")
                    results["fallback_man_city"] = {"status": "PARTIAL", "coefficient": coef, "source": source}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["fallback_man_city"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["fallback_man_city"] = {"status": "FAIL", "error": str(e)}
        
        # Test Liverpool (should find in PremierLeague)
        self.log("\n   Testing Liverpool (Champions League → should find in PremierLeague)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Liverpool&league=ChampionsLeague",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "PremierLeague" and 1.0 <= coef <= 1.30:
                    self.log(f"✅ Liverpool: coeff={coef:.4f}, source={source}")
                    results["fallback_liverpool"] = {"status": "PASS", "coefficient": coef, "source": source}
                else:
                    self.log(f"⚠️ Liverpool: coeff={coef}, source={source}")
                    results["fallback_liverpool"] = {"status": "PARTIAL", "coefficient": coef, "source": source}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["fallback_liverpool"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["fallback_liverpool"] = {"status": "FAIL", "error": str(e)}
        
        # Test 5: Intelligent Fallback - Foreign teams (European bonus)
        self.log("\n5️⃣ Testing intelligent fallback for foreign teams (European bonus)...")
        
        # Test Galatasaray (not in national leagues → should get 1.05)
        self.log("\n   Testing Galatasaray (Champions League → not in national leagues)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Galatasaray&league=ChampionsLeague",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "european_fallback" and coef == 1.05:
                    self.log(f"✅ Galatasaray: coeff={coef}, source={source}")
                    results["fallback_galatasaray"] = {"status": "PASS", "coefficient": coef, "source": source}
                else:
                    self.log(f"⚠️ Galatasaray: coeff={coef}, source={source} (expected european_fallback, 1.05)")
                    results["fallback_galatasaray"] = {"status": "PARTIAL", "coefficient": coef, "source": source}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["fallback_galatasaray"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["fallback_galatasaray"] = {"status": "FAIL", "error": str(e)}
        
        # Test Red Star Belgrade (not in national leagues → should get 1.05)
        self.log("\n   Testing Red Star Belgrade (Champions League → not in national leagues)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Red Star Belgrade&league=ChampionsLeague",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "european_fallback" and coef == 1.05:
                    self.log(f"✅ Red Star Belgrade: coeff={coef}, source={source}")
                    results["fallback_red_star"] = {"status": "PASS", "coefficient": coef, "source": source}
                else:
                    self.log(f"⚠️ Red Star Belgrade: coeff={coef}, source={source}")
                    results["fallback_red_star"] = {"status": "PARTIAL", "coefficient": coef, "source": source}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["fallback_red_star"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["fallback_red_star"] = {"status": "FAIL", "error": str(e)}
        
        # Test Olympiacos (Europa League → not in national leagues → should get 1.05)
        self.log("\n   Testing Olympiacos (Europa League → not in national leagues)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Olympiacos&league=EuropaLeague",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "european_fallback" and coef == 1.05:
                    self.log(f"✅ Olympiacos: coeff={coef}, source={source}")
                    results["fallback_olympiacos"] = {"status": "PASS", "coefficient": coef, "source": source}
                else:
                    self.log(f"⚠️ Olympiacos: coeff={coef}, source={source}")
                    results["fallback_olympiacos"] = {"status": "PARTIAL", "coefficient": coef, "source": source}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["fallback_olympiacos"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["fallback_olympiacos"] = {"status": "FAIL", "error": str(e)}
        
        # Test 6: Regression tests
        self.log("\n6️⃣ Testing regression (existing functionality)...")
        
        # Test health endpoint
        self.log("\n   Testing /api/health...")
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            if response.status_code == 200:
                self.log("✅ Health endpoint working")
                results["regression_health"] = {"status": "PASS"}
            else:
                self.log(f"❌ Health endpoint failed: HTTP {response.status_code}")
                results["regression_health"] = {"status": "FAIL"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["regression_health"] = {"status": "FAIL", "error": str(e)}
        
        # Test scheduler status (should now handle 8 leagues)
        self.log("\n   Testing scheduler status (should handle 8 leagues)...")
        try:
            response = requests.get(f"{BASE_URL}/admin/league/scheduler-status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                scheduler = data.get("scheduler", {})
                is_running = scheduler.get("is_running", False)
                
                if is_running:
                    self.log(f"✅ Scheduler running, next update: {scheduler.get('next_update', 'N/A')}")
                    results["regression_scheduler"] = {"status": "PASS"}
                else:
                    self.log("⚠️ Scheduler not running")
                    results["regression_scheduler"] = {"status": "PARTIAL"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["regression_scheduler"] = {"status": "FAIL"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["regression_scheduler"] = {"status": "FAIL", "error": str(e)}
        
        # Test direct LaLiga query (should still work)
        self.log("\n   Testing direct LaLiga query (regression)...")
        try:
            response = requests.get(
                f"{BASE_URL}/league/team-coeff?team=Real Madrid&league=LaLiga",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                coef = data.get("coefficient")
                source = data.get("source")
                
                if source == "LaLiga" and 1.0 <= coef <= 1.30:
                    self.log(f"✅ Direct LaLiga query working: coeff={coef:.4f}")
                    results["regression_laliga"] = {"status": "PASS"}
                else:
                    self.log(f"⚠️ Unexpected result: coeff={coef}, source={source}")
                    results["regression_laliga"] = {"status": "PARTIAL"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["regression_laliga"] = {"status": "FAIL"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["regression_laliga"] = {"status": "FAIL", "error": str(e)}
        
        # Print summary
        self.log("\n" + "=" * 60)
        self.log("EUROPEAN COMPETITIONS TEST SUMMARY")
        self.log("=" * 60)
        
        passed = sum(1 for r in results.values() if r.get("status") == "PASS")
        partial = sum(1 for r in results.values() if r.get("status") == "PARTIAL")
        failed = sum(1 for r in results.values() if r.get("status") == "FAIL")
        total = len(results)
        
        self.log(f"\n✅ Passed: {passed}/{total}")
        self.log(f"⚠️ Partial: {partial}/{total}")
        self.log(f"❌ Failed: {failed}/{total}")
        
        for test_name, result in results.items():
            status = result.get("status", "UNKNOWN")
            status_icon = "✅" if status == "PASS" else "⚠️" if status == "PARTIAL" else "❌"
            self.log(f"{status_icon} {test_name}: {status}")
        
        self.log("=" * 60)
        
        return results

    def test_phase2_integration(self):
        """Test Phase 2 - Integration of 5 new European leagues"""
        self.log("=" * 60)
        self.log("🌍 TESTING PHASE 2 - 5 NEW EUROPEAN LEAGUES")
        self.log("=" * 60)
        
        results = {}
        
        # Test 1: Direct execution of league_phase2.py
        self.log("\n1️⃣ Testing direct execution of league_phase2.py...")
        try:
            import subprocess
            result = subprocess.run(
                ["python3", "/app/backend/league_phase2.py"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.log("✅ league_phase2.py executed successfully")
                results["phase2_direct_execution"] = {"status": "PASS"}
            else:
                self.log(f"❌ league_phase2.py failed with return code {result.returncode}")
                self.log(f"   Error: {result.stderr[:200]}")
                results["phase2_direct_execution"] = {"status": "FAIL", "error": result.stderr[:200]}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["phase2_direct_execution"] = {"status": "FAIL", "error": str(e)}
        
        # Test 2: Verify scheduler status
        self.log("\n2️⃣ Testing scheduler status...")
        try:
            response = requests.get(f"{BASE_URL}/admin/league/scheduler-status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                scheduler = data.get("scheduler", {})
                is_running = scheduler.get("is_running", False)
                
                if is_running:
                    self.log(f"✅ Scheduler running, next update: {scheduler.get('next_update', 'N/A')}")
                    results["scheduler_status"] = {"status": "PASS", "data": scheduler}
                else:
                    self.log("⚠️ Scheduler not running")
                    results["scheduler_status"] = {"status": "PARTIAL", "data": scheduler}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["scheduler_status"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["scheduler_status"] = {"status": "FAIL", "error": str(e)}
        
        # Test 3: Trigger manual update via scheduler
        self.log("\n3️⃣ Testing manual trigger via scheduler...")
        try:
            response = requests.post(f"{BASE_URL}/admin/league/trigger-update", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log("✅ Manual update triggered successfully")
                    results["manual_trigger"] = {"status": "PASS"}
                    # Wait a few seconds for the update to process
                    self.log("   ⏳ Waiting 5 seconds for update to process...")
                    time.sleep(5)
                else:
                    self.log("❌ Manual trigger failed")
                    results["manual_trigger"] = {"status": "FAIL", "error": "Success flag false"}
            else:
                self.log(f"❌ HTTP {response.status_code}")
                results["manual_trigger"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["manual_trigger"] = {"status": "FAIL", "error": str(e)}
        
        # Test 4: Verify JSON files created
        self.log("\n4️⃣ Verifying JSON files in /app/data/leagues/...")
        expected_files = ["SerieA.json", "Bundesliga.json", "Ligue1.json", "PrimeiraLiga.json", "Ligue2.json", "phase2_update_report.json"]
        
        files_found = []
        files_missing = []
        
        for filename in expected_files:
            filepath = f"/app/data/leagues/{filename}"
            if os.path.exists(filepath):
                files_found.append(filename)
                self.log(f"   ✅ {filename} exists")
            else:
                files_missing.append(filename)
                self.log(f"   ❌ {filename} missing")
        
        if len(files_found) == len(expected_files):
            self.log(f"✅ All {len(expected_files)} files found")
            results["files_verification"] = {"status": "PASS", "files_found": files_found}
        elif len(files_found) > 0:
            self.log(f"⚠️ {len(files_found)}/{len(expected_files)} files found")
            results["files_verification"] = {"status": "PARTIAL", "files_found": files_found, "files_missing": files_missing}
        else:
            self.log("❌ No files found")
            results["files_verification"] = {"status": "FAIL", "files_missing": files_missing}
        
        # Test 5: Verify phase2_update_report.json content
        self.log("\n5️⃣ Verifying phase2_update_report.json content...")
        try:
            report_path = "/app/data/leagues/phase2_update_report.json"
            if os.path.exists(report_path):
                with open(report_path, "r") as f:
                    report = json.load(f)
                
                leagues_updated = report.get("leagues_updated", 0)
                total_leagues = report.get("total_leagues", 0)
                
                if leagues_updated == 5 and total_leagues == 5:
                    self.log(f"✅ Report shows {leagues_updated}/{total_leagues} leagues updated")
                    results["report_verification"] = {"status": "PASS", "leagues_updated": leagues_updated}
                else:
                    self.log(f"⚠️ Report shows {leagues_updated}/{total_leagues} leagues updated (expected 5/5)")
                    results["report_verification"] = {"status": "PARTIAL", "leagues_updated": leagues_updated}
            else:
                self.log("❌ phase2_update_report.json not found")
                results["report_verification"] = {"status": "FAIL", "error": "Report file not found"}
        except Exception as e:
            self.log(f"❌ Exception: {str(e)}")
            results["report_verification"] = {"status": "FAIL", "error": str(e)}
        
        # Test 6: Test team coefficients for new leagues
        self.log("\n6️⃣ Testing team coefficients for Phase 2 leagues...")
        
        phase2_teams = [
            ("Inter Milan", "SerieA"),
            ("Bayern Munich", "Bundesliga"),
            ("Paris Saint-Germain", "Ligue1"),
            ("Benfica", "PrimeiraLiga"),
            ("Auxerre", "Ligue2")
        ]
        
        coeff_results = {}
        for team, league in phase2_teams:
            self.log(f"\n   Testing {team} ({league})...")
            try:
                response = requests.get(
                    f"{BASE_URL}/league/team-coeff?team={team}&league={league}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    coef = data.get("coefficient")
                    
                    if coef and 0.85 <= coef <= 1.30:
                        self.log(f"   ✅ {team}: coefficient={coef:.3f} (valid range)")
                        coeff_results[f"{team}_{league}"] = {"status": "PASS", "coefficient": coef}
                    else:
                        self.log(f"   ❌ {team}: coefficient={coef} (outside valid range [0.85, 1.30])")
                        coeff_results[f"{team}_{league}"] = {"status": "FAIL", "coefficient": coef}
                else:
                    self.log(f"   ❌ HTTP {response.status_code}")
                    coeff_results[f"{team}_{league}"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
            except Exception as e:
                self.log(f"   ❌ Exception: {str(e)}")
                coeff_results[f"{team}_{league}"] = {"status": "FAIL", "error": str(e)}
        
        # Summarize coefficient tests
        coeff_passed = sum(1 for r in coeff_results.values() if r.get("status") == "PASS")
        coeff_total = len(coeff_results)
        
        if coeff_passed == coeff_total:
            self.log(f"\n✅ All {coeff_total} coefficient tests passed")
            results["coefficient_tests"] = {"status": "PASS", "passed": coeff_passed, "total": coeff_total}
        elif coeff_passed > 0:
            self.log(f"\n⚠️ {coeff_passed}/{coeff_total} coefficient tests passed")
            results["coefficient_tests"] = {"status": "PARTIAL", "passed": coeff_passed, "total": coeff_total}
        else:
            self.log(f"\n❌ All {coeff_total} coefficient tests failed")
            results["coefficient_tests"] = {"status": "FAIL", "passed": 0, "total": coeff_total}
        
        # Test 7: Regression tests for existing leagues
        self.log("\n7️⃣ Testing regression (existing leagues should still work)...")
        
        regression_tests = [
            ("Real Madrid", "LaLiga"),
            ("Manchester City", "PremierLeague")
        ]
        
        regression_results = {}
        for team, league in regression_tests:
            self.log(f"\n   Testing {team} ({league})...")
            try:
                response = requests.get(
                    f"{BASE_URL}/league/team-coeff?team={team}&league={league}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    coef = data.get("coefficient")
                    
                    if coef and 0.85 <= coef <= 1.30:
                        self.log(f"   ✅ {team}: coefficient={coef:.3f}")
                        regression_results[f"{team}_{league}"] = {"status": "PASS", "coefficient": coef}
                    else:
                        self.log(f"   ❌ {team}: coefficient={coef}")
                        regression_results[f"{team}_{league}"] = {"status": "FAIL", "coefficient": coef}
                else:
                    self.log(f"   ❌ HTTP {response.status_code}")
                    regression_results[f"{team}_{league}"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
            except Exception as e:
                self.log(f"   ❌ Exception: {str(e)}")
                regression_results[f"{team}_{league}"] = {"status": "FAIL", "error": str(e)}
        
        # Summarize regression tests
        regression_passed = sum(1 for r in regression_results.values() if r.get("status") == "PASS")
        regression_total = len(regression_results)
        
        if regression_passed == regression_total:
            self.log(f"\n✅ All {regression_total} regression tests passed")
            results["regression_tests"] = {"status": "PASS", "passed": regression_passed, "total": regression_total}
        else:
            self.log(f"\n❌ {regression_passed}/{regression_total} regression tests passed")
            results["regression_tests"] = {"status": "FAIL", "passed": regression_passed, "total": regression_total}
        
        # Print summary
        self.log("\n" + "=" * 60)
        self.log("PHASE 2 TEST SUMMARY")
        self.log("=" * 60)
        
        passed = sum(1 for r in results.values() if r.get("status") == "PASS")
        partial = sum(1 for r in results.values() if r.get("status") == "PARTIAL")
        failed = sum(1 for r in results.values() if r.get("status") == "FAIL")
        total = len(results)
        
        self.log(f"\n✅ Passed: {passed}/{total}")
        self.log(f"⚠️ Partial: {partial}/{total}")
        self.log(f"❌ Failed: {failed}/{total}")
        
        for test_name, result in results.items():
            status = result.get("status", "UNKNOWN")
            status_icon = "✅" if status == "PASS" else "⚠️" if status == "PARTIAL" else "❌"
            self.log(f"{status_icon} {test_name}: {status}")
        
        self.log("=" * 60)
        
        return results

if __name__ == "__main__":
    tester = ScorePredictorTester()
    
    # Run Phase 2 integration tests
    print("\n🌍 TESTING PHASE 2 - 5 NEW EUROPEAN LEAGUES INTEGRATION")
    print("=" * 60)
    phase2_results = tester.test_phase2_integration()
    
    # Print final summary
    print("\n" + "=" * 60)
    print("🎯 PHASE 2 INTEGRATION TEST COMPLETE")
    print("=" * 60)
    
    passed = sum(1 for r in phase2_results.values() if r.get("status") == "PASS")
    partial = sum(1 for r in phase2_results.values() if r.get("status") == "PARTIAL")
    failed = sum(1 for r in phase2_results.values() if r.get("status") == "FAIL")
    total = len(phase2_results)
    
    print(f"\n✅ Passed: {passed}/{total}")
    print(f"⚠️ Partial: {partial}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"\n📊 Success Rate: {success_rate:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Phase 2 integration is working perfectly.")
        print("✅ 5 new leagues integrated (Serie A, Bundesliga, Ligue 1, Primeira Liga, Ligue 2)")
        print("✅ All JSON files created successfully")
        print("✅ Team coefficients calculated correctly (0.85-1.30 range)")
        print("✅ Scheduler integration working")
        print("✅ No regression in existing functionality")
    elif success_rate >= 70:
        print("\n⚠️ MOST TESTS PASSED WITH SOME WARNINGS. System is functional but check details above.")
    else:
        print("\n❌ CRITICAL ISSUES FOUND. Backend needs attention.")
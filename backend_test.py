#!/usr/bin/env python3
"""
Backend Testing Suite for Score Prediction API
Tests the new score_predictor.py integration and all endpoints
"""

import requests
import json
import os
from pathlib import Path

# Configuration
BASE_URL = "https://predict-match-3.preview.emergentagent.com/api"
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
                    
                    # Check required fields
                    required_fields = ['success', 'extractedScores', 'mostProbableScore', 'probabilities']
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
                        
                        # Check if probabilities sum to approximately 100%
                        prob_sum = sum(probabilities.values()) if probabilities else 0
                        prob_sum_valid = 95 <= prob_sum <= 105  # Allow 5% tolerance
                        
                        if extracted_scores and probabilities and most_probable and prob_sum_valid:
                            self.results["analyze"]["tests"][image_name] = {
                                "status": "PASS",
                                "extracted_scores_count": len(extracted_scores),
                                "most_probable_score": most_probable,
                                "probabilities_sum": round(prob_sum, 2)
                            }
                            successful_tests += 1
                            self.log(f"✅ {image_name}: Analysis successful - {most_probable} (prob sum: {prob_sum:.1f}%)")
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

if __name__ == "__main__":
    tester = ScorePredictorTester()
    results = tester.run_all_tests()
    
    # Print final status
    all_passed = all(r["status"] == "PASS" for r in results.values())
    has_partial = any(r["status"] == "PARTIAL" for r in results.values())
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Backend is working correctly.")
    elif has_partial:
        print("\n⚠️ SOME TESTS PASSED WITH ISSUES. Check details above.")
    else:
        print("\n❌ CRITICAL ISSUES FOUND. Backend needs attention.")
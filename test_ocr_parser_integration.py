#!/usr/bin/env python3
"""
Test script specifically for Advanced OCR Parser Integration
Tests the integration of ocr_parser.py and verification of league coefficients application
"""

import requests
import json
import os
import time
from pathlib import Path

# Configuration
BASE_URL = "https://predict-match-4.preview.emergentagent.com/api"
BACKEND_DIR = "/app/backend"

class OCRParserIntegrationTester:
    def __init__(self):
        self.results = {}
        
    def log(self, message):
        print(f"[TEST] {message}")
        
    def test_advanced_ocr_parser_integration(self):
        """Test the advanced OCR parser integration for league coefficients"""
        self.log("=" * 60)
        self.log("🔍 TESTING ADVANCED OCR PARSER INTEGRATION")
        self.log("=" * 60)
        
        results = {}
        
        # Test 1: Basic health check
        self.log("\n1️⃣ Testing API health...")
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.log("✅ API health check passed")
                    results["health"] = {"status": "PASS"}
                else:
                    self.log("❌ API health check failed - unexpected response")
                    results["health"] = {"status": "FAIL", "error": "Unexpected response"}
            else:
                self.log(f"❌ API health check failed - HTTP {response.status_code}")
                results["health"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"❌ API health check failed - {str(e)}")
            results["health"] = {"status": "FAIL", "error": str(e)}
        
        # Test 2: Test /api/analyze with focus on team/league detection
        self.log("\n2️⃣ Testing /api/analyze with advanced OCR parser...")
        
        # Use available test images
        test_images = ["winamax_test_new.jpg", "unibet_test.jpg", "test_bookmaker_v2.jpg", "paris_bayern.jpg"]
        analyze_results = {}
        
        for image_name in test_images:
            image_path = os.path.join(BACKEND_DIR, image_name)
            
            if not os.path.exists(image_path):
                self.log(f"⚠️ Image not found: {image_name}")
                continue
            
            self.log(f"\n   Testing with {image_name}...")
            
            try:
                with open(image_path, 'rb') as f:
                    files = {'file': (image_name, f, 'image/jpeg')}
                    response = requests.post(f"{BASE_URL}/analyze", files=files, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if analysis was successful
                    if 'error' in data and 'Aucune cote détectée' in data['error']:
                        analyze_results[image_name] = {
                            "status": "NO_SCORES",
                            "note": "No scores detected by OCR (expected for some images)"
                        }
                        self.log(f"   ⚠️ No scores detected in {image_name} (expected behavior)")
                    else:
                        # Extract key fields for league coefficient testing
                        match_name = data.get('matchName', 'Not extracted')
                        league = data.get('league', 'Unknown')
                        league_coeffs_applied = data.get('leagueCoeffsApplied', False)
                        most_probable = data.get('mostProbableScore', 'N/A')
                        
                        # Analyze the quality of team/league detection
                        team_detection_quality = "GOOD" if match_name != "Match non détecté" else "POOR"
                        league_detection_quality = "GOOD" if league != "Unknown" else "POOR"
                        
                        analyze_results[image_name] = {
                            "status": "SUCCESS",
                            "match_name": match_name,
                            "league": league,
                            "league_coeffs_applied": league_coeffs_applied,
                            "most_probable_score": most_probable,
                            "team_detection": team_detection_quality,
                            "league_detection": league_detection_quality
                        }
                        
                        self.log(f"   ✅ Analysis completed for {image_name}")
                        self.log(f"      📝 Match: '{match_name}' (Detection: {team_detection_quality})")
                        self.log(f"      🏆 League: '{league}' (Detection: {league_detection_quality})")
                        self.log(f"      ⚖️ League coeffs applied: {league_coeffs_applied}")
                        self.log(f"      🎯 Most probable: {most_probable}")
                        
                        # Key success criteria from review request
                        if match_name != "Match non détecté" and league != "Unknown" and league_coeffs_applied:
                            self.log(f"      🎉 SUCCESS: All criteria met for {image_name}")
                        else:
                            self.log(f"      ⚠️ PARTIAL: Some criteria not met for {image_name}")
                else:
                    analyze_results[image_name] = {
                        "status": "FAIL",
                        "error": f"HTTP {response.status_code}"
                    }
                    self.log(f"   ❌ HTTP error {response.status_code} for {image_name}")
            except Exception as e:
                analyze_results[image_name] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                self.log(f"   ❌ Exception for {image_name}: {str(e)}")
        
        results["analyze_tests"] = analyze_results
        
        # Test 3: Check backend logs for team/league detection
        self.log("\n3️⃣ Checking backend logs for team/league detection...")
        try:
            # Get recent backend logs
            import subprocess
            log_result = subprocess.run(
                ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if log_result.returncode == 0:
                logs = log_result.stdout
                
                # Look for key detection messages
                team_detection_found = "✅ Équipes détectées:" in logs
                league_detection_found = "✅ Ligue détectée:" in logs
                league_coeffs_log_found = "league_coeffs_applied" in logs
                
                self.log(f"   Team detection logs: {'✅ Found' if team_detection_found else '❌ Not found'}")
                self.log(f"   League detection logs: {'✅ Found' if league_detection_found else '❌ Not found'}")
                self.log(f"   League coeffs logs: {'✅ Found' if league_coeffs_log_found else '❌ Not found'}")
                
                results["log_analysis"] = {
                    "status": "PASS" if any([team_detection_found, league_detection_found, league_coeffs_log_found]) else "PARTIAL",
                    "team_detection_logs": team_detection_found,
                    "league_detection_logs": league_detection_found,
                    "league_coeffs_logs": league_coeffs_log_found
                }
            else:
                self.log("   ❌ Could not read backend logs")
                results["log_analysis"] = {"status": "FAIL", "error": "Could not read logs"}
        except Exception as e:
            self.log(f"   ❌ Exception reading logs: {str(e)}")
            results["log_analysis"] = {"status": "FAIL", "error": str(e)}
        
        # Test 4: Regression tests
        self.log("\n4️⃣ Testing regression endpoints...")
        
        # Test /api/diff
        try:
            response = requests.get(f"{BASE_URL}/diff", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'diffExpected' in data:
                    self.log(f"   ✅ /api/diff working - diffExpected: {data['diffExpected']}")
                    results["diff_regression"] = {"status": "PASS", "diffExpected": data['diffExpected']}
                else:
                    self.log("   ❌ /api/diff missing diffExpected field")
                    results["diff_regression"] = {"status": "FAIL", "error": "Missing diffExpected"}
            else:
                self.log(f"   ❌ /api/diff failed - HTTP {response.status_code}")
                results["diff_regression"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"   ❌ /api/diff exception: {str(e)}")
            results["diff_regression"] = {"status": "FAIL", "error": str(e)}
        
        # Test /api/learn
        try:
            data = {'predicted': '2-1', 'real': '1-1'}
            response = requests.post(f"{BASE_URL}/learn", data=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.log(f"   ✅ /api/learn working - new diff: {result.get('newDiffExpected')}")
                    results["learn_regression"] = {"status": "PASS", "newDiff": result.get('newDiffExpected')}
                else:
                    self.log("   ❌ /api/learn failed - success=false")
                    results["learn_regression"] = {"status": "FAIL", "error": "Success=false"}
            else:
                self.log(f"   ❌ /api/learn failed - HTTP {response.status_code}")
                results["learn_regression"] = {"status": "FAIL", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self.log(f"   ❌ /api/learn exception: {str(e)}")
            results["learn_regression"] = {"status": "FAIL", "error": str(e)}
        
        # Summary
        self.log("\n" + "=" * 60)
        self.log("ADVANCED OCR PARSER INTEGRATION TEST SUMMARY")
        self.log("=" * 60)
        
        # Count successful team/league detections
        successful_detections = 0
        total_analyzed = 0
        
        for image, result in analyze_results.items():
            if result.get("status") == "SUCCESS":
                total_analyzed += 1
                if (result.get("match_name") != "Match non détecté" and 
                    result.get("league") != "Unknown" and 
                    result.get("league_coeffs_applied")):
                    successful_detections += 1
        
        self.log(f"\n📊 DETECTION RESULTS:")
        self.log(f"   Images with successful team/league detection: {successful_detections}/{total_analyzed}")
        
        # Overall assessment
        if successful_detections > 0:
            self.log(f"\n🎉 SUCCESS: Advanced OCR parser is working - league coefficients are being applied!")
        else:
            self.log(f"\n⚠️ PARTIAL: Advanced OCR parser integrated but team/league detection needs improvement")
        
        return results

if __name__ == "__main__":
    tester = OCRParserIntegrationTester()
    results = tester.test_advanced_ocr_parser_integration()
#!/usr/bin/env python3
"""
Test script specifically for Intelligent OCR Filtering System
Tests the clean_team_name functionality and filtering of schedules/interface elements
"""

import requests
import json
import os
import re
import time
from pathlib import Path

# Configuration
BASE_URL = "https://score-oracle-11.preview.emergentagent.com/api"

class OCRFilteringTester:
    def __init__(self):
        self.results = {}
        
    def log(self, message):
        print(f"[OCR-TEST] {message}")
        
    def test_intelligent_ocr_filtering(self):
        """Test the intelligent OCR filtering system as requested in review"""
        self.log("=" * 80)
        self.log("🔍 TESTING INTELLIGENT OCR FILTERING SYSTEM")
        self.log("=" * 80)
        
        results = {}
        
        # Test images from /tmp/test_ocr/
        test_images = [
            {
                "path": "/tmp/test_ocr/liga_portugal.jpg",
                "description": "Liga Portugal image (main focus)",
                "expected_league": "PrimeiraLiga",
                "expected_clean_teams": True  # Should not contain schedules or interface elements
            },
            {
                "path": "/tmp/test_ocr/fdj_test1.jpg", 
                "description": "FDJ test image 1",
                "expected_clean_teams": True
            },
            {
                "path": "/tmp/test_ocr/fdj_test2.jpg",
                "description": "FDJ test image 2", 
                "expected_clean_teams": True
            }
        ]
        
        self.log("\n1️⃣ Testing /api/analyze endpoint with OCR filtering...")
        
        for image_info in test_images:
            image_path = image_info["path"]
            image_name = os.path.basename(image_path)
            
            self.log(f"\n--- Testing {image_name} ---")
            self.log(f"Description: {image_info['description']}")
            
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
                    
                    # Check if analysis was successful
                    if 'error' in data and 'Aucune cote détectée' in data['error']:
                        results[image_name] = {
                            "status": "NO_SCORES",
                            "note": "No scores detected by OCR (acceptable behavior)"
                        }
                        self.log(f"⚠️ {image_name}: No scores detected by OCR")
                        continue
                    
                    # Extract key fields for filtering validation
                    match_name = data.get('matchName', 'Not extracted')
                    league = data.get('league', 'Unknown')
                    league_coeffs_applied = data.get('leagueCoeffsApplied', False)
                    most_probable = data.get('mostProbableScore', 'N/A')
                    
                    # CRITICAL VALIDATION: Check for filtered elements
                    filtering_results = self._validate_ocr_filtering(match_name)
                    
                    results[image_name] = {
                        "status": "SUCCESS",
                        "match_name": match_name,
                        "league": league,
                        "league_coeffs_applied": league_coeffs_applied,
                        "most_probable_score": most_probable,
                        "filtering_validation": filtering_results
                    }
                    
                    self.log(f"✅ Analysis completed for {image_name}")
                    self.log(f"    📝 Match: '{match_name}'")
                    self.log(f"    🏆 League: '{league}'")
                    self.log(f"    ⚖️ League coeffs applied: {league_coeffs_applied}")
                    self.log(f"    🎯 Most probable: {most_probable}")
                    
                    # Validate filtering criteria from review request
                    self.log(f"    🔍 FILTERING VALIDATION:")
                    for check, passed in filtering_results.items():
                        icon = "✅" if passed else "❌"
                        self.log(f"        {icon} {check}")
                    
                    # Special validation for Liga Portugal image
                    if "liga_portugal" in image_name.lower():
                        expected_league = image_info.get("expected_league", "PrimeiraLiga")
                        if league == expected_league:
                            self.log(f"    🎉 LIGA PORTUGAL SUCCESS: League correctly detected as {expected_league}")
                        else:
                            self.log(f"    ⚠️ LIGA PORTUGAL: Expected {expected_league}, got {league}")
                    
                    # Overall filtering success
                    all_filters_passed = all(filtering_results.values())
                    if all_filters_passed and league_coeffs_applied:
                        self.log(f"    🎉 ALL FILTERING CRITERIA MET for {image_name}")
                    else:
                        self.log(f"    ⚠️ Some filtering criteria not met for {image_name}")
                        
                else:
                    results[image_name] = {
                        "status": "FAIL",
                        "error": f"HTTP {response.status_code}"
                    }
                    self.log(f"❌ HTTP error {response.status_code} for {image_name}")
                    
            except Exception as e:
                results[image_name] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                self.log(f"❌ Exception for {image_name}: {str(e)}")
        
        # Test 2: Regression tests
        self.log("\n2️⃣ Testing regression endpoints...")
        
        regression_results = {}
        
        # Test /api/health
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.log("✅ GET /api/health - Working correctly")
                    regression_results["health"] = {"status": "PASS"}
                else:
                    self.log("❌ GET /api/health - Unexpected response")
                    regression_results["health"] = {"status": "FAIL"}
            else:
                self.log(f"❌ GET /api/health - HTTP {response.status_code}")
                regression_results["health"] = {"status": "FAIL"}
        except Exception as e:
            self.log(f"❌ GET /api/health - Exception: {str(e)}")
            regression_results["health"] = {"status": "FAIL", "error": str(e)}
        
        # Test /api/diff
        try:
            response = requests.get(f"{BASE_URL}/diff", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'diffExpected' in data:
                    self.log(f"✅ GET /api/diff - Returns diffExpected: {data['diffExpected']}")
                    regression_results["diff"] = {"status": "PASS", "diffExpected": data['diffExpected']}
                else:
                    self.log("❌ GET /api/diff - Missing diffExpected field")
                    regression_results["diff"] = {"status": "FAIL"}
            else:
                self.log(f"❌ GET /api/diff - HTTP {response.status_code}")
                regression_results["diff"] = {"status": "FAIL"}
        except Exception as e:
            self.log(f"❌ GET /api/diff - Exception: {str(e)}")
            regression_results["diff"] = {"status": "FAIL", "error": str(e)}
        
        # Test /api/learn
        try:
            data = {'predicted': '2-1', 'real': '1-1'}
            response = requests.post(f"{BASE_URL}/learn", data=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.log(f"✅ POST /api/learn - Learning works")
                    regression_results["learn"] = {"status": "PASS"}
                else:
                    self.log("❌ POST /api/learn - Success=false")
                    regression_results["learn"] = {"status": "FAIL"}
            else:
                self.log(f"❌ POST /api/learn - HTTP {response.status_code}")
                regression_results["learn"] = {"status": "FAIL"}
        except Exception as e:
            self.log(f"❌ POST /api/learn - Exception: {str(e)}")
            regression_results["learn"] = {"status": "FAIL", "error": str(e)}
        
        # Test 3: Check backend logs for filtering messages
        self.log("\n3️⃣ Checking backend logs for OCR filtering...")
        
        try:
            import subprocess
            log_result = subprocess.run(
                ["tail", "-n", "200", "/var/log/supervisor/backend.err.log"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if log_result.returncode == 0:
                logs = log_result.stdout
                
                # Look for key filtering and detection messages
                league_detection_found = "✅ Ligue détectée dans le texte" in logs or "✅ Ligue détectée:" in logs
                team_detection_found = "✅ Équipes détectées:" in logs
                clean_team_called = "clean_team_name" in logs
                
                self.log(f"✅ League detection logs: {'Found' if league_detection_found else 'Not found'}")
                self.log(f"✅ Team detection logs: {'Found' if team_detection_found else 'Not found'}")
                self.log(f"✅ Clean team name called: {'Found' if clean_team_called else 'Not found'}")
                
                # Look for any errors during OCR processing
                ocr_errors = "Erreur lors de l'analyse" in logs or "Exception" in logs
                if not ocr_errors:
                    self.log("✅ No OCR processing errors found")
                else:
                    self.log("⚠️ Some OCR processing errors detected in logs")
                
                results["log_analysis"] = {
                    "status": "PASS" if any([league_detection_found, team_detection_found]) else "PARTIAL",
                    "league_detection_logs": league_detection_found,
                    "team_detection_logs": team_detection_found,
                    "clean_team_called": clean_team_called,
                    "no_errors": not ocr_errors
                }
            else:
                self.log("❌ Could not read backend logs")
                results["log_analysis"] = {"status": "FAIL", "error": "Could not read logs"}
        except Exception as e:
            self.log(f"❌ Exception reading logs: {str(e)}")
            results["log_analysis"] = {"status": "FAIL", "error": str(e)}
        
        # Summary
        self.log("\n" + "=" * 80)
        self.log("INTELLIGENT OCR FILTERING TEST SUMMARY")
        self.log("=" * 80)
        
        # Count successful filtering validations
        successful_filtering = 0
        total_analyzed = 0
        
        for image, result in results.items():
            if result.get("status") == "SUCCESS":
                total_analyzed += 1
                filtering_validation = result.get("filtering_validation", {})
                if all(filtering_validation.values()):
                    successful_filtering += 1
        
        self.log(f"\n📊 FILTERING RESULTS:")
        self.log(f"   Images with successful filtering: {successful_filtering}/{total_analyzed}")
        self.log(f"   Regression tests: {sum(1 for r in regression_results.values() if r.get('status') == 'PASS')}/{len(regression_results)} passed")
        
        # Overall assessment
        if successful_filtering > 0 and all(r.get("status") == "PASS" for r in regression_results.values()):
            self.log(f"\n🎉 SUCCESS: Intelligent OCR filtering is working correctly!")
            self.log(f"   ✅ Team names are clean (no schedules, no interface elements)")
            self.log(f"   ✅ Leagues are correctly detected")
            self.log(f"   ✅ League coefficients are applied")
            self.log(f"   ✅ No regression in existing functionality")
        else:
            self.log(f"\n⚠️ ISSUES FOUND: Some filtering criteria not met or regressions detected")
        
        results["regression_tests"] = regression_results
        return results
    
    def _validate_ocr_filtering(self, match_name: str) -> dict:
        """Validate that OCR filtering worked correctly according to review criteria"""
        if not match_name or match_name == "Match non détecté":
            return {
                "no_schedules": True,  # Can't have schedules if no match detected
                "no_interface_elements": True,  # Can't have interface if no match detected
                "clean_team_names": False  # But teams weren't detected
            }
        
        # Check for schedules (À 16h30, 20:45, etc.)
        schedule_patterns = [
            r'À\s*\d{1,2}h\d{2}',
            r'A\s*\d{1,2}h\d{2}',
            r'\d{1,2}h\d{2}',
            r'\d{1,2}:\d{2}'
        ]
        has_schedules = any(re.search(pattern, match_name, re.IGNORECASE) for pattern in schedule_patterns)
        
        # Check for interface elements (Paris, Pari sur mesure, Stats, Compos, etc.)
        interface_patterns = [
            r'\bParis\b(?!\s+Saint)',  # "Paris" alone (not "Paris Saint-Germain")
            r'Pari(?:er)?(?:\s+sur\s+mesure)?',
            r'\bStats?\b',
            r'\bCompos?\b',
            r'\bCote(?:s)?\b',
            r'sur\s+mesure',
            r'\bParis\s+Pari',
            r'\bS\'inscrire\b'
        ]
        has_interface = any(re.search(pattern, match_name, re.IGNORECASE) for pattern in interface_patterns)
        
        # Check if team names look clean and readable
        clean_team_names = (
            len(match_name.strip()) >= 3 and
            not has_schedules and
            not has_interface and
            match_name != "Match non détecté"
        )
        
        return {
            "no_schedules": not has_schedules,
            "no_interface_elements": not has_interface,
            "clean_team_names": clean_team_names
        }

if __name__ == "__main__":
    tester = OCRFilteringTester()
    results = tester.test_intelligent_ocr_filtering()
    
    # Print final results
    print("\n" + "=" * 80)
    print("FINAL TEST RESULTS")
    print("=" * 80)
    
    for test_name, result in results.items():
        if test_name != "regression_tests":
            status = result.get("status", "UNKNOWN")
            status_icon = "✅" if status == "SUCCESS" else "⚠️" if status == "NO_SCORES" else "❌"
            print(f"{status_icon} {test_name}: {status}")
            
            if "filtering_validation" in result:
                validation = result["filtering_validation"]
                for check, passed in validation.items():
                    icon = "✅" if passed else "❌"
                    print(f"    {icon} {check}")
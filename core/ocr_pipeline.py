"""
Pipeline OCR unifié avec priorité GPT-Vision et fallback Tesseract
Intégration avec les systèmes existants
"""
import pytesseract
from PIL import Image
from typing import Dict, Any, List
from pathlib import Path
import logging
import sys

logger = logging.getLogger(__name__)

# Import des modules existants
sys.path.insert(0, '/app/backend')

def call_gpt_vision(image_path: str) -> Dict[str, Any]:
    """
    Appel à GPT-4 Vision via le système existant
    Utilise tools/vision_ocr_scores.py
    """
    try:
        from tools.vision_ocr_scores import extract_odds_from_image
        
        logger.info(f"🤖 GPT-Vision: Analyse de {Path(image_path).name}")
        result = extract_odds_from_image(image_path)
        
        if result and (isinstance(result, list) or (isinstance(result, dict) and result.get('scores'))):
            scores = result if isinstance(result, list) else result.get('scores', [])
            
            logger.info(f"✅ GPT-Vision: {len(scores)} scores extraits")
            return {
                "success": True,
                "parsed_scores": scores,
                "raw_text": "",
                "confidence": 0.95
            }
        else:
            logger.warning("⚠️ GPT-Vision: Aucun score extrait")
            return {"success": False, "parsed_scores": [], "raw_text": ""}
            
    except Exception as e:
        logger.error(f"❌ GPT-Vision error: {e}")
        return {"success": False, "parsed_scores": [], "raw_text": "", "error": str(e)}

def call_tesseract(image_path: str) -> Dict[str, Any]:
    """
    Fallback Tesseract OCR
    Utilise le système existant ocr_engine.py
    """
    try:
        from ocr_engine import extract_odds
        
        logger.info(f"📝 Tesseract: Analyse de {Path(image_path).name}")
        result = extract_odds(image_path)
        
        if result and 'extractedScores' in result:
            scores = result['extractedScores']
            
            # Format unifié
            parsed_scores = []
            for score_data in scores:
                if isinstance(score_data, dict) and 'score' in score_data:
                    score_str = score_data['score']
                    try:
                        home, away = map(int, score_str.split('-'))
                        parsed_scores.append({
                            "home": home,
                            "away": away,
                            "cote": score_data.get('cote', 0)
                        })
                    except:
                        continue
            
            logger.info(f"✅ Tesseract: {len(parsed_scores)} scores extraits")
            return {
                "success": True,
                "parsed_scores": parsed_scores,
                "raw_text": result.get('rawText', ''),
                "confidence": 0.70
            }
        else:
            logger.warning("⚠️ Tesseract: Aucun score extrait")
            return {"success": False, "parsed_scores": [], "raw_text": ""}
            
    except Exception as e:
        logger.error(f"❌ Tesseract error: {e}")
        return {"success": False, "parsed_scores": [], "raw_text": "", "error": str(e)}

def parse_scores_from_text(raw_text: str) -> List[Dict]:
    """
    Parsing basique des scores depuis texte brut
    Format attendu: "1-0", "2-1", etc.
    """
    import re
    
    scores = []
    # Chercher les patterns de scores
    pattern = r'\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b'
    matches = re.findall(pattern, raw_text)
    
    for match in matches:
        try:
            home = int(match[0])
            away = int(match[1])
            if 0 <= home <= 10 and 0 <= away <= 10:  # Validation basique
                scores.append({
                    "home": home,
                    "away": away,
                    "cote": 0
                })
        except:
            continue
    
    return scores

def process_image(image_path: str, prefer_gpt_vision: bool = True) -> Dict[str, Any]:
    """
    Point d'entrée principal du pipeline OCR
    
    Args:
        image_path: Chemin vers l'image
        prefer_gpt_vision: Si True, essaie GPT-Vision en premier
    
    Returns:
        dict: {
            'ocr_engine': 'gpt-vision'|'tesseract'|None,
            'parsed_scores': [...],
            'raw_text': '...',
            'success': True/False,
            'confidence': 0.0-1.0
        }
    """
    logger.info(f"🔍 Traitement image: {Path(image_path).name} (prefer_gpt_vision={prefer_gpt_vision})")
    
    # 1) Priorité GPT-Vision
    if prefer_gpt_vision:
        try:
            res = call_gpt_vision(image_path)
            if res.get("success") and len(res.get("parsed_scores", [])) > 0:
                res["ocr_engine"] = "gpt-vision"
                logger.info(f"✅ Pipeline: GPT-Vision réussi ({len(res['parsed_scores'])} scores)")
                return res
            else:
                logger.warning("⚠️ GPT-Vision n'a pas retourné de scores, passage à Tesseract")
        except Exception as e:
            logger.error(f"❌ GPT-Vision exception: {e}, passage à Tesseract")

    # 2) Fallback Tesseract
    try:
        t = call_tesseract(image_path)
        if t.get("success"):
            parsed = t.get("parsed_scores") or parse_scores_from_text(t.get("raw_text", ""))
            
            result = {
                "ocr_engine": "tesseract",
                "parsed_scores": parsed,
                "raw_text": t.get("raw_text", ""),
                "success": len(parsed) > 0,
                "confidence": t.get("confidence", 0.70)
            }
            
            if result["success"]:
                logger.info(f"✅ Pipeline: Tesseract réussi ({len(parsed)} scores)")
            else:
                logger.warning("⚠️ Pipeline: Tesseract n'a pas extrait de scores")
            
            return result
            
    except Exception as e:
        logger.error(f"❌ Tesseract exception: {e}")
        return {
            "ocr_engine": None,
            "parsed_scores": [],
            "raw_text": "",
            "success": False,
            "error": str(e)
        }

def extract_match_info(image_path: str) -> Dict[str, Any]:
    """
    Extrait les informations du match (équipes, ligue, bookmaker)
    Utilise le système existant
    """
    try:
        from ocr_parser import extract_match_info as extract_match_info_advanced
        
        result = extract_match_info_advanced(image_path)
        
        return {
            "home_team": result.get("home_team", "Unknown"),
            "away_team": result.get("away_team", "Unknown"),
            "league": result.get("league", "Unknown"),
            "bookmaker": result.get("bookmaker", "Unknown")
        }
    except Exception as e:
        logger.error(f"❌ Extract match info error: {e}")
        return {
            "home_team": "Unknown",
            "away_team": "Unknown",
            "league": "Unknown",
            "bookmaker": "Unknown"
        }

# Test du module
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*70)
    print("TEST PIPELINE OCR")
    print("="*70)
    
    # Tester avec une image existante
    test_images = list(Path("/app/data/bookmaker_images").glob("*.jpg"))[:3]
    
    if not test_images:
        print("⚠️ Aucune image de test trouvée")
    else:
        for img_path in test_images:
            print(f"\n📸 Test: {img_path.name}")
            print("-" * 50)
            
            # Test GPT-Vision prioritaire
            result = process_image(str(img_path), prefer_gpt_vision=True)
            print(f"Moteur: {result.get('ocr_engine')}")
            print(f"Succès: {result.get('success')}")
            print(f"Scores: {len(result.get('parsed_scores', []))}")
            
            if result.get('parsed_scores'):
                for score in result['parsed_scores'][:3]:
                    print(f"  - {score}")

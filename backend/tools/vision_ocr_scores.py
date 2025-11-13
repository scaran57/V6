#!/usr/bin/env python3
"""
Vision OCR spécialisé pour extraire TOUS les scores et cotes d'un bookmaker
Utilise GPT-4 Vision via Emergent LLM Key
"""

import os
import base64
import json
import logging
import asyncio
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

load_dotenv()

logger = logging.getLogger(__name__)

VISION_API_KEY = os.getenv("EMERGENT_LLM_KEY", "")

def encode_image_to_base64(image_path: str) -> str:
    """Convertit une image en base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

async def extract_all_odds_with_vision(image_path: str) -> List[Dict]:
    """
    Utilise GPT-4 Vision pour extraire TOUS les scores et cotes d'une image de bookmaker
    
    Returns:
        Liste de dicts: [{"score": "1-0", "odds": 84.0}, ...]
    """
    if not VISION_API_KEY:
        logger.error("Clé Emergent LLM manquante")
        return []
    
    try:
        # Encoder l'image
        image_b64 = encode_image_to_base64(image_path)
        image_content = ImageContent(image_base64=image_b64)
        
        # Prompt pour extraction complète
        prompt = """
Analyse cette image de bookmaker et extrais TOUS les scores de football avec leurs cotes.

IMPORTANT:
- Lis attentivement les nombres à 3 chiffres (ex: 100, pas 10.0 ou 7.0)
- Liste TOUS les scores visibles (1-0, 0-0, 2-1, 3-2, etc.)
- Pour chaque score, donne la cote exacte

Retourne un JSON valide avec cette structure:
{
  "scores": [
    {"score": "1-0", "odds": 84.0},
    {"score": "0-0", "odds": 25.0},
    {"score": "0-1", "odds": 7.7},
    {"score": "2-0", "odds": 100},
    {"score": "3-2", "odds": 100},
    ...
  ]
}

ATTENTION: 
- "100" est un nombre à 3 chiffres, PAS "10.0" ou "7.0" !
- Si la cote affiche "100", mets 100 (pas 10, pas 7)
"""
        
        # Initialiser le chat GPT-4 Vision
        chat = LlmChat(
            api_key=VISION_API_KEY,
            session_id=f"vision_scores_{datetime.now().timestamp()}",
            system_message="Tu es un expert OCR spécialisé dans la lecture précise de cotes de paris sportifs. Tu lis les nombres à 3 chiffres comme 100 correctement."
        ).with_model("openai", "gpt-4o")
        
        # Créer le message avec image
        user_message = UserMessage(
            text=prompt,
            file_contents=[image_content]
        )
        
        # Envoyer et obtenir la réponse
        response = await chat.send_message(user_message)
        
        logger.info(f"[VISION_SCORES] Réponse brute : {response[:500]}")
        
        # Parser la réponse JSON
        raw = response.strip()
        
        # Enlever les backticks markdown si présents
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join([l for l in lines if not l.strip().startswith("```")])
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        
        data = json.loads(raw)
        
        # Extraire la liste des scores
        if "scores" in data and isinstance(data["scores"], list):
            scores = data["scores"]
            logger.info(f"[VISION_SCORES] {len(scores)} scores extraits")
            
            # Validation et nettoyage
            cleaned_scores = []
            for item in scores:
                if "score" in item and "odds" in item:
                    try:
                        score = str(item["score"]).strip()
                        odds = float(item["odds"])
                        
                        # Validation du format score
                        if "-" in score:
                            cleaned_scores.append({"score": score, "odds": odds})
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Score invalide ignoré: {item} - {e}")
            
            logger.info(f"[VISION_SCORES] {len(cleaned_scores)} scores valides")
            return cleaned_scores
        else:
            logger.error("[VISION_SCORES] Format de réponse invalide")
            return []
            
    except json.JSONDecodeError as e:
        logger.error(f"[VISION_SCORES] Erreur JSON: {e}")
        logger.error(f"Réponse: {response[:500]}")
        return []
    except Exception as e:
        logger.error(f"[VISION_SCORES] Erreur: {e}")
        import traceback
        traceback.print_exc()
        return []

def extract_odds_with_vision_sync(image_path: str) -> List[Dict]:
    """Version synchrone pour compatibilité"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(extract_all_odds_with_vision(image_path))

# Export pour compatibilité
extract_odds_from_image = extract_odds_with_vision_sync

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"Extraction des cotes de: {image_path}")
        result = extract_odds_with_vision_sync(image_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python vision_ocr_scores.py <image_path>")

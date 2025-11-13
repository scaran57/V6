import os
import base64
import json
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

from PIL import Image
import pytesseract
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

# Charger les variables d'environnement
load_dotenv()

# ---------------------------------------------------------------------
# 🔧 CONFIGURATION
# ---------------------------------------------------------------------

LOG_FILE = "/app/backend/vision_ocr.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Utiliser la clé Emergent LLM
VISION_API_KEY = os.getenv("EMERGENT_LLM_KEY", "")
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "openai")

# Seuils de confiance pour Tesseract et Vision
TESSERACT_MIN_CONFIDENCE = 0.70  # si <70%, on tente GPT-4 Vision
VISION_DEFAULT_CONFIDENCE = 0.95

# ---------------------------------------------------------------------
# 🧩 OUTILS
# ---------------------------------------------------------------------
def encode_image_to_base64(image_path: str) -> str:
    """Convertit une image en base64 pour l'envoi à GPT-4 Vision."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# ---------------------------------------------------------------------
# 🟠 OCR FALLBACK : Tesseract
# ---------------------------------------------------------------------
def ocr_with_tesseract(image_path: str) -> Dict[str, str]:
    """
    Utilise Tesseract pour extraire le texte brut.
    Retourne également un niveau de confiance simulé (faible si texte court ou vide).
    """
    try:
        text = pytesseract.image_to_string(Image.open(image_path))
        confidence = min(1.0, max(0.1, len(text) / 300))  # estimation grossière
        logging.info(f"[TESSERACT] OCR réussi sur {image_path} (conf={confidence:.2f})")
        return {"raw_text": text.strip(), "provider": "tesseract", "confidence": confidence}
    except Exception as e:
        logging.error(f"[TESSERACT] Erreur sur {image_path} : {e}")
        return {"raw_text": "", "provider": "tesseract", "confidence": 0.0}

# ---------------------------------------------------------------------
# 🟢 OCR : GPT-4 Vision avec Emergent LLM
# ---------------------------------------------------------------------
async def ocr_with_gpt4_vision(image_path: str) -> Optional[Dict]:
    """Utilise GPT-4 Vision pour extraire ligue, équipes et cotes."""
    if not VISION_API_KEY:
        logging.error("Clé API Vision manquante. Impossible d'utiliser GPT-4 Vision.")
        return None

    try:
        # Encoder l'image en base64
        image_b64 = encode_image_to_base64(image_path)
        
        # Créer l'objet ImageContent
        image_content = ImageContent(image_base64=image_b64)

        # Prompt pour l'extraction
        prompt = """
Tu es un système OCR intelligent pour les paris sportifs.
Analyse l'image et extrais les informations suivantes :
- Nom de la ligue
- Nom de l'équipe domicile
- Nom de l'équipe extérieure
- Cotes (1, N, 2)

Retourne uniquement un JSON valide, au format :
{
  "league": "string",
  "home_team": "string",
  "away_team": "string",
  "home_odds": float,
  "draw_odds": float,
  "away_odds": float
}

Si une donnée est illisible, mets null.
"""

        # Initialiser le chat GPT-4 Vision
        chat = LlmChat(
            api_key=VISION_API_KEY,
            session_id=f"vision_ocr_{datetime.now().timestamp()}",
            system_message="Tu es un assistant OCR expert pour les paris sportifs."
        ).with_model("openai", "gpt-4o")  # gpt-4o supporte les images

        # Créer le message avec image
        user_message = UserMessage(
            text=prompt,
            file_contents=[image_content]
        )

        # Envoyer et obtenir la réponse
        response = await chat.send_message(user_message)
        
        logging.info(f"[GPT4_VISION] Réponse brute : {response}")

        # Parser la réponse JSON
        try:
            # Extraire le JSON de la réponse
            raw = response.strip()
            # Parfois la réponse est entourée de ```json ... ```
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logging.error(f"[GPT4_VISION] Réponse non-JSON : {response}")
            return None

        parsed["provider"] = "gpt4_vision"
        parsed["confidence"] = VISION_DEFAULT_CONFIDENCE
        logging.info(f"[GPT4_VISION] Extraction réussie : {parsed}")
        return parsed

    except Exception as e:
        logging.error(f"[GPT4_VISION] Erreur API : {e}")
        return None

# ---------------------------------------------------------------------
# 🔁 LOGIQUE INTELLIGENTE : combinaison Vision + Tesseract
# ---------------------------------------------------------------------
def extract_odds_from_image(image_path: str) -> Dict:
    """
    Étapes :
      1. Tenter Tesseract (gratuit, local)
      2. Si résultat vide ou confiance < seuil, basculer sur GPT-4 Vision
    """
    tess_result = ocr_with_tesseract(image_path)

    if tess_result["confidence"] >= TESSERACT_MIN_CONFIDENCE and tess_result["raw_text"]:
        logging.info(f"[OCR_ENGINE] Résultat Tesseract accepté ({tess_result['confidence']:.2f})")
        return tess_result

    logging.warning(f"[OCR_ENGINE] Tesseract insuffisant, tentative GPT-4 Vision : {image_path}")
    
    # Appel asynchrone à GPT-4 Vision
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    vision_result = loop.run_until_complete(ocr_with_gpt4_vision(image_path))

    if vision_result:
        return vision_result

    logging.warning(f"[OCR_ENGINE] GPT-4 Vision échec, retour Tesseract brut.")
    return tess_result

# ---------------------------------------------------------------------
# 🧪 TEST LOCAL
# ---------------------------------------------------------------------
if __name__ == "__main__":
    test_image = "sample_bet_image.jpg"
    result = extract_odds_from_image(test_image)
    print(json.dumps(result, indent=2, ensure_ascii=False))
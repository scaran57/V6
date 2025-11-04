import json
import os
from math import fabs
import logging

logger = logging.getLogger(__name__)

DATA_FILE = "/app/backend/learning_data.json"

def get_diff_expected():
    """
    Récupère la différence de buts attendue depuis le fichier de données.
    Par défaut: 2 buts de différence.
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                diff = data.get("diffExpected", 2)
                logger.info(f"Différence attendue chargée: {diff}")
                return diff
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du fichier d'apprentissage: {str(e)}")
    return 2

def update_model(predicted, real):
    """
    Met à jour le modèle d'apprentissage avec le score prédit vs réel.
    Ajuste progressivement la différence de buts attendue.
    """
    current = get_diff_expected()
    
    try:
        # Validation: ignorer si "Autre" ou format invalide
        if "autre" in predicted.lower() or "autre" in real.lower():
            logger.info(f"⚠️ Apprentissage ignoré: 'Autre' détecté (prédit={predicted}, réel={real})")
            return {"skipped": True, "reason": "Score 'Autre' ne peut pas être utilisé pour l'apprentissage"}
        
        # Valider le format des scores (X-Y)
        if "-" not in predicted or "-" not in real:
            logger.warning(f"Format invalide: prédit={predicted}, réel={real}")
            return False
        
        # Parse les scores
        p_parts = predicted.split("-")
        r_parts = real.split("-")
        
        if len(p_parts) != 2 or len(r_parts) != 2:
            logger.warning(f"Format invalide: prédit={predicted}, réel={real}")
            return False
        
        p_home, p_away = int(p_parts[0]), int(p_parts[1])
        r_home, r_away = int(r_parts[0]), int(r_parts[1])
        
        # Calcul des différences
        diff_pred = fabs(p_away - p_home)
        diff_real = fabs(r_away - r_home)
        
        # Mise à jour progressive (moyenne pondérée: 80% ancien, 20% nouveau)
        new_diff = round((current * 4 + diff_real) / 5)
        
        logger.info(f"✅ Apprentissage: prédit={predicted}, réel={real}")
        logger.info(f"📊 Différence attendue mise à jour: {current} → {new_diff}")
        
        # Sauvegarde
        with open(DATA_FILE, "w") as f:
            json.dump({"diffExpected": new_diff}, f)
        
        return True
        
    except ValueError as e:
        logger.error(f"❌ Erreur de conversion en nombre: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour du modèle: {str(e)}")
        return False
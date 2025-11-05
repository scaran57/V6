import json
import os
from math import fabs
import logging

logger = logging.getLogger(__name__)

DATA_FILE = "/app/backend/learning_data.json"

def get_diff_expected():
    """
    Récupère la différence de buts attendue depuis le système sécurisé.
    Fallback sur l'ancien fichier si le nouveau n'existe pas.
    Par défaut: 2 buts de différence.
    """
    # Essayer d'abord le nouveau système sécurisé
    try:
        import sys
        sys.path.insert(0, '/app')
        from modules.local_learning_safe import load_meta
        
        meta = load_meta()
        diff = meta.get("diffExpected", 2)
        logger.info(f"✅ Différence attendue (système sécurisé): {diff}")
        return diff
    except Exception as e:
        logger.warning(f"⚠️ Système sécurisé indisponible, fallback ancien système: {str(e)}")
        
        # Fallback sur l'ancien système
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    diff = data.get("diffExpected", 2)
                    logger.info(f"Différence attendue (ancien système): {diff}")
                    return diff
            except Exception as e:
                logger.error(f"Erreur lecture ancien fichier: {str(e)}")
        
        return 2

def update_model(predicted, real, home_team=None, away_team=None):
    """
    Met à jour le modèle d'apprentissage avec le score prédit vs réel.
    Ajuste progressivement la différence de buts attendue.
    
    Args:
        predicted: Score prédit (format "X-Y")
        real: Score réel (format "X-Y")
        home_team: Nom de l'équipe domicile (optionnel)
        away_team: Nom de l'équipe extérieur (optionnel)
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
        
        # Mise à jour progressive (moyenne pondérée: 60% ancien, 40% nouveau)
        # Formule plus réactive pour l'apprentissage manuel
        new_diff = round((current * 3 + diff_real * 2) / 5)
        
        logger.info(f"✅ Apprentissage: prédit={predicted}, réel={real}")
        logger.info(f"📊 Différence attendue mise à jour: {current} → {new_diff}")
        
        # Si les noms d'équipes sont fournis, mettre à jour leurs stats
        if home_team and away_team:
            try:
                from score_predictor import update_team_results, adjust_diff_expected
                
                # Mettre à jour les stats des équipes
                update_team_results(home_team, r_home, r_away)
                update_team_results(away_team, r_away, r_home)
                
                # Ajuster le diffExpected basé sur les équipes
                adjusted_diff = adjust_diff_expected(new_diff, home_team, away_team)
                new_diff = adjusted_diff
                
                logger.info(f"🎯 Ajustement par équipes: {home_team} vs {away_team}")
            except Exception as e:
                logger.warning(f"⚠️ Impossible d'ajuster par équipes: {str(e)}")
        
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
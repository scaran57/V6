import json
import os
import copy
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# --- 📦 FICHIER DE SAUVEGARDE PERSISTANTE ---
MEMORY_FILE = "/app/backend/data/matches_memory.json"

# --- 📦 MÉMOIRE EN COURS ---
analyzed_matches = {}

# --- 🔁 CHARGEMENT AU DÉMARRAGE ---
def load_matches_memory():
    """Charge la mémoire des matchs depuis le fichier JSON"""
    global analyzed_matches
    
    # Créer le dossier data s'il n'existe pas
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                analyzed_matches = json.load(f)
            logger.info(f"🧠 Mémoire chargée : {len(analyzed_matches)} matchs restaurés.")
        except Exception as e:
            logger.error(f"⚠️ Erreur de lecture mémoire : {e}")
            analyzed_matches = {}
    else:
        logger.info("📂 Aucune mémoire trouvée — démarrage neuf.")
        analyzed_matches = {}

# --- 💾 SAUVEGARDE AUTOMATIQUE ---
def save_matches_memory():
    """Sauvegarde la mémoire des matchs dans le fichier JSON"""
    try:
        # Créer le dossier data s'il n'existe pas
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(analyzed_matches, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Mémoire sauvegardée ({len(analyzed_matches)} matchs enregistrés).")
    except Exception as e:
        logger.error(f"⚠️ Erreur de sauvegarde mémoire : {e}")

# --- 🔍 ANALYSE STABLE AVEC SAUVEGARDE ---
def analyze_match_stable(match_id, scores_data, probabilities, confidence, top3, bookmaker=None, match_name=None):
    """
    Sauvegarde le résultat d'analyse d'un match.
    - Si le match existe déjà → retourne le résultat sauvegardé (pas de recalcul)
    - Sinon → sauvegarde le résultat final.
    
    Args:
        match_id: Identifiant unique du match
        scores_data: Scores extraits de l'image
        probabilities: Probabilités calculées
        confidence: Score de confiance
        top3: Top 3 des scores
        bookmaker: Nom du bookmaker
        match_name: Nom du match
    
    Returns:
        dict: Résultat d'analyse (existant ou nouveau)
    """
    
    # 1️⃣ Vérifie si le match existe déjà
    if match_id in analyzed_matches:
        logger.info(f"⚙️ Match {match_id} déjà analysé — résultat figé retourné.")
        return analyzed_matches[match_id]
    
    # 2️⃣ Créer le résultat d'analyse
    result = {
        "match_id": match_id,
        "match_name": match_name or "Match non détecté",
        "bookmaker": bookmaker or "Bookmaker inconnu",
        "extracted_scores": scores_data,
        "probabilities": probabilities,
        "confidence": confidence,
        "top3": top3,
        "analyzed_at": datetime.now().isoformat(),
    }
    
    # 3️⃣ Sauvegarde du résultat figé pour ce match
    analyzed_matches[match_id] = result
    
    save_matches_memory()
    logger.info(f"✅ Match {match_id} analysé et figé dans la mémoire")
    
    return result

# --- 🔍 RÉCUPÉRATION D'UN MATCH ---
def get_match_result(match_id):
    """
    Récupère le résultat d'un match déjà analysé.
    
    Args:
        match_id: Identifiant unique du match
    
    Returns:
        dict ou None: Résultat du match si trouvé, None sinon
    """
    return analyzed_matches.get(match_id)

# --- 📋 LISTE TOUS LES MATCHS ---
def get_all_matches():
    """
    Retourne la liste de tous les matchs en mémoire.
    
    Returns:
        dict: Tous les matchs analysés
    """
    return analyzed_matches

# --- 🗑️ SUPPRESSION D'UN MATCH ---
def delete_match(match_id):
    """
    Supprime un match de la mémoire.
    
    Args:
        match_id: Identifiant unique du match
    
    Returns:
        bool: True si supprimé, False si non trouvé
    """
    if match_id in analyzed_matches:
        del analyzed_matches[match_id]
        save_matches_memory()
        logger.info(f"🗑️ Match {match_id} supprimé de la mémoire")
        return True
    return False

# --- 🧹 NETTOYAGE DE LA MÉMOIRE ---
def clear_all_matches():
    """Supprime tous les matchs de la mémoire"""
    global analyzed_matches
    analyzed_matches = {}
    save_matches_memory()
    logger.info("🧹 Mémoire complètement effacée")

# --- 🔑 GÉNÉRATION D'ID UNIQUE ---
def generate_match_id(match_name, bookmaker, date=None):
    """
    Génère un identifiant unique pour un match.
    
    Args:
        match_name: Nom du match (ex: "PSG - Lyon")
        bookmaker: Nom du bookmaker
        date: Date (optionnel, utilise aujourd'hui par défaut)
    
    Returns:
        str: ID unique du match
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Nettoyer le nom du match (enlever espaces, tirets, etc.)
    clean_name = match_name.replace(" ", "").replace("-", "").lower()
    clean_bookmaker = bookmaker.replace(" ", "").lower()
    
    return f"{clean_name}_{clean_bookmaker}_{date}"

# --- ⚙️ CHARGEMENT AUTOMATIQUE AU DÉMARRAGE ---
load_matches_memory()

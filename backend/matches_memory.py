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

# --- 📊 RAPPORT DE SUIVI AUTOMATIQUE ---
def generate_system_report():
    """
    🔍 Génère un rapport synthétique sur les matchs en mémoire, l'apprentissage, et la stabilité.
    
    Returns:
        dict: Rapport structuré avec statistiques et dernières analyses
    """
    try:
        total_matches = len(analyzed_matches)
        
        # Obtenir la date de dernière modification du fichier
        last_update = "—"
        if os.path.exists(MEMORY_FILE):
            last_update_timestamp = os.path.getmtime(MEMORY_FILE)
            last_update = datetime.fromtimestamp(last_update_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        # Comptage des stats
        bookmakers = {}
        match_names = []
        confidence_scores = []
        
        for match_id, info in analyzed_matches.items():
            if isinstance(info, dict):
                # Bookmaker
                if "bookmaker" in info:
                    bm = info["bookmaker"]
                    bookmakers[bm] = bookmakers.get(bm, 0) + 1
                
                # Nom du match
                if "match_name" in info:
                    match_names.append(info["match_name"])
                
                # Confiance
                if "confidence" in info:
                    confidence_scores.append(info["confidence"])
        
        # Calcul de la confiance moyenne
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        # Générer rapport textuel
        report_text = f"""
===============================
📊 RAPPORT DE SUIVI AUTOMATIQUE
===============================

🕒 Dernière mise à jour : {last_update}
📁 Matchs mémorisés : {total_matches}
📈 Confiance moyenne : {avg_confidence * 100:.1f}%

🔸 Répartition par bookmaker :
"""
        if bookmakers:
            for bm, count in sorted(bookmakers.items(), key=lambda x: x[1], reverse=True):
                report_text += f"   - {bm}: {count} match(s)\n"
        else:
            report_text += "   Aucun bookmaker enregistré\n"

        report_text += "\n"
        report_text += "✅ Mémoire fonctionnelle et stable\n" if total_matches > 0 else "⚠️ Aucune donnée encore sauvegardée\n"

        # Derniers matchs analysés
        if total_matches > 0:
            recent_matches = list(analyzed_matches.items())[-5:]  # 5 derniers
            report_text += f"\n📋 {min(5, total_matches)} dernier(s) match(s) analysé(s) :\n"
            
            for match_id, match_data in reversed(recent_matches):
                if isinstance(match_data, dict):
                    match_name = match_data.get("match_name", "N/A")
                    confidence = match_data.get("confidence", 0) * 100
                    top_score = match_data.get("top3", [{}])[0].get("score", "N/A") if match_data.get("top3") else "N/A"
                    
                    report_text += f"   • {match_name}\n"
                    report_text += f"     Score prédit: {top_score} | Confiance: {confidence:.1f}%\n"

        report_text += "\n===============================\n"
        
        # Rapport structuré pour l'API
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "last_update": last_update,
            "statistics": {
                "total_matches": total_matches,
                "average_confidence": round(avg_confidence, 4),
                "bookmakers_count": len(bookmakers),
                "bookmakers_distribution": bookmakers
            },
            "recent_matches": [
                {
                    "match_id": mid,
                    "match_name": mdata.get("match_name", "N/A"),
                    "bookmaker": mdata.get("bookmaker", "N/A"),
                    "confidence": mdata.get("confidence", 0),
                    "top_score": mdata.get("top3", [{}])[0].get("score", "N/A") if mdata.get("top3") else "N/A",
                    "analyzed_at": mdata.get("analyzed_at", "N/A")
                }
                for mid, mdata in list(analyzed_matches.items())[-5:]
                if isinstance(mdata, dict)
            ],
            "status": "operational" if total_matches > 0 else "empty",
            "report_text": report_text
        }
        
        logger.info("📊 Rapport de suivi généré")
        return report_data
        
    except Exception as e:
        logger.error(f"⚠️ Erreur génération rapport : {e}")
        return {
            "error": str(e),
            "status": "error"
        }

# --- ⚙️ CHARGEMENT AUTOMATIQUE AU DÉMARRAGE ---
load_matches_memory()

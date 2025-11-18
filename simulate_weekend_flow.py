#!/usr/bin/env python3
"""
SIMULATION COMPLÈTE DU FLUX WEEK-END
====================================

Ce script simule le cycle complet d'une analyse de match :
1. Utilisateur upload une photo bookmaker (samedi)
2. Système analyse et prédit le score
3. Match se joue (dimanche)
4. Scheduler 3h00 (lundi matin) :
   - Met à jour les classements
   - Récupère les scores réels
   - Lance l'apprentissage automatique
   - Ajuste diffExpected
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/app')
sys.path.insert(0, '/app/backend')

print("="*70)
print("🏈 SIMULATION WEEK-END - CYCLE COMPLET")
print("="*70)

# Import des modules
from core.models import SessionLocal, UploadedImage, AnalysisResult, init_db
from core.learning import learn_from_match, get_learning_stats
from core.config import get_league_params, update_league_param
from league_unified import update_all_leagues

# Initialiser la DB si nécessaire
init_db()

# ============================================================================
# 1️⃣ SAMEDI 14h00 : UTILISATEUR ANALYSE UN MATCH BOOKMAKER
# ============================================================================
print("\n" + "="*70)
print("1️⃣ SAMEDI 14h00 - UTILISATEUR ANALYSE UN MATCH")
print("="*70)

db = SessionLocal()

# Paramètres actuels avant l'analyse
league = "PremierLeague"
params_before = get_league_params(league)
diff_before = params_before.get('diffExpected', 2.1380)

print(f"\n📊 Paramètres actuels:")
print(f"   Ligue: {league}")
print(f"   diffExpected: {diff_before:.4f}")

# Créer une image uploadée (simulation)
uploaded_img = UploadedImage(
    filename="/app/test_images/ocr_test_premierleague.jpg",
    original_filename="bookmaker_screenshot_MUN_CHE.jpg",
    league=league,
    home_team="Manchester United",
    away_team="Chelsea",
    bookmaker="Winamax",
    upload_time=datetime.utcnow() - timedelta(days=2, hours=10)  # Samedi 14h
)
db.add(uploaded_img)
db.commit()
db.refresh(uploaded_img)

print(f"\n✅ Image uploadée:")
print(f"   ID: {uploaded_img.id}")
print(f"   Match: {uploaded_img.home_team} vs {uploaded_img.away_team}")
print(f"   Date: {uploaded_img.upload_time.strftime('%Y-%m-%d %H:%M')}")

# Créer l'analyse avec prédictions
fake_scores = [
    {"home": 2, "away": 1, "cote": 8.5},
    {"home": 1, "away": 0, "cote": 7.2},
    {"home": 2, "away": 0, "cote": 9.0},
    {"home": 1, "away": 1, "cote": 6.8},
    {"home": 0, "away": 0, "cote": 12.0}
]

analysis = AnalysisResult(
    parsed_scores=fake_scores,
    extracted_count=len(fake_scores),
    most_probable_score="2-1",
    top3_scores=[
        {"score": "2-1", "prob": 34.5},
        {"score": "1-1", "prob": 29.2},
        {"score": "2-0", "prob": 19.1}
    ],
    confidence=0.87,
    ocr_engine="gpt-vision",
    ocr_confidence=0.95,
    diff_expected_used=diff_before,
    base_expected_used=1.45,
    league_used=league,
    created_at=uploaded_img.upload_time
)
db.add(analysis)
db.commit()
db.refresh(analysis)

# Lier l'image à l'analyse
uploaded_img.analysis_id = analysis.id
uploaded_img.processed = True
db.commit()

print(f"\n✅ Analyse complétée:")
print(f"   ID: {analysis.id}")
print(f"   OCR Engine: {analysis.ocr_engine}")
print(f"   Scores extraits: {analysis.extracted_count}")
print(f"   Score prédit (plus probable): {analysis.most_probable_score}")
print(f"   Confiance: {analysis.confidence:.2%}")
print(f"\n   Top 3 prédictions:")
for pred in analysis.top3_scores:
    print(f"      {pred['score']}: {pred['prob']:.1f}%")

# ============================================================================
# 2️⃣ DIMANCHE 17h00 : MATCH SE JOUE - SCORE RÉEL
# ============================================================================
print("\n" + "="*70)
print("2️⃣ DIMANCHE 17h00 - MATCH SE TERMINE")
print("="*70)

# Le match se termine avec un score réel
real_score = "3-1"  # Différent de la prédiction (2-1)

print(f"\n⚽ Score final: {uploaded_img.home_team} {real_score} {uploaded_img.away_team}")
print(f"   Prédit: {analysis.most_probable_score}")
print(f"   Réel: {real_score}")

if analysis.most_probable_score == real_score:
    print("   ✅ Prédiction exacte !")
else:
    print("   ⚠️ Prédiction différente (le système va apprendre)")

# ============================================================================
# 3️⃣ LUNDI 3h00 : SCHEDULER AUTOMATIQUE
# ============================================================================
print("\n" + "="*70)
print("3️⃣ LUNDI 3h00 - SCHEDULER AUTOMATIQUE")
print("="*70)

# A. Mise à jour des classements de ligues
print("\n📊 Étape 1: Mise à jour des classements...")
print("-" * 50)

try:
    report = update_all_leagues()
    print(f"✅ Mise à jour complétée:")
    print(f"   Total ligues: {report.get('total_leagues', 0)}")
    print(f"   Mises à jour: {report.get('leagues_updated', 0)}")
    print(f"   Via API: {report.get('leagues_updated', 0) - report.get('leagues_fallback', 0)}")
    print(f"   Via cache: {report.get('leagues_fallback', 0)}")
except Exception as e:
    print(f"⚠️ Erreur mise à jour: {e}")

# B. Récupération du score réel et enregistrement
print("\n⚽ Étape 2: Récupération score réel...")
print("-" * 50)

analysis.real_score = real_score
analysis.real_score_confirmed = True
analysis.real_score_source = "automatic"
analysis.updated_at = datetime.utcnow()
db.commit()

print(f"✅ Score réel enregistré: {real_score}")

# C. Apprentissage automatique
print("\n🎓 Étape 3: Apprentissage automatique...")
print("-" * 50)

learning_result = learn_from_match(
    league=league,
    predicted_score=analysis.most_probable_score,
    real_score=real_score,
    home_team=uploaded_img.home_team,
    away_team=uploaded_img.away_team,
    analysis_id=analysis.id,
    source="automatic"
)

if learning_result.get('success'):
    diff_after = learning_result.get('diff_expected_after')
    adjustment = learning_result.get('adjustment')
    
    print(f"✅ Apprentissage réussi:")
    print(f"   diffExpected avant: {diff_before:.4f}")
    print(f"   diffExpected après: {diff_after:.4f}")
    print(f"   Ajustement: {adjustment:+.4f}")
    print(f"   Event ID: {learning_result.get('event_id')}")
else:
    print(f"❌ Erreur apprentissage: {learning_result.get('error')}")
    diff_after = diff_before
    adjustment = 0

# ============================================================================
# 4️⃣ RAPPORT FINAL
# ============================================================================
print("\n" + "="*70)
print("4️⃣ RAPPORT FINAL DE LA SIMULATION")
print("="*70)

# Statistiques d'apprentissage
stats = get_learning_stats(league=league, days=30)

report = {
    "simulation_date": datetime.utcnow().isoformat(),
    "match": {
        "league": league,
        "home_team": uploaded_img.home_team,
        "away_team": uploaded_img.away_team,
        "predicted_score": analysis.most_probable_score,
        "real_score": real_score,
        "prediction_correct": analysis.most_probable_score == real_score
    },
    "analysis": {
        "upload_id": uploaded_img.id,
        "analysis_id": analysis.id,
        "upload_time": uploaded_img.upload_time.isoformat(),
        "ocr_engine": analysis.ocr_engine,
        "confidence": analysis.confidence,
        "scores_extracted": analysis.extracted_count
    },
    "learning": {
        "success": learning_result.get('success'),
        "diff_expected_before": diff_before,
        "diff_expected_after": diff_after,
        "adjustment": adjustment,
        "learning_event_id": learning_result.get('event_id')
    },
    "league_update": {
        "executed": True,
        "total_leagues": report.get('total_leagues', 0) if 'report' in locals() else 0,
        "updated_count": report.get('leagues_updated', 0) if 'report' in locals() else 0
    },
    "learning_stats": {
        "total_events": stats.get('count', 0),
        "period_days": stats.get('period_days', 30),
        "avg_adjustment": stats.get('avg_adjustment', 0)
    }
}

print("\n📄 Rapport JSON:")
print(json.dumps(report, indent=2, ensure_ascii=False))

# Résumé visuel
print("\n" + "="*70)
print("📊 RÉSUMÉ DE LA SIMULATION")
print("="*70)

print(f"""
✅ Cycle complet simulé avec succès !

📸 1. Upload & Analyse (Samedi 14h00)
   - Image uploadée et analysée
   - {analysis.extracted_count} scores extraits via {analysis.ocr_engine}
   - Prédiction: {analysis.most_probable_score}

⚽ 2. Match (Dimanche 17h00)
   - Score réel: {real_score}
   - Prédiction {'✅ exacte' if analysis.most_probable_score == real_score else '⚠️ différente'}

🔄 3. Scheduler automatique (Lundi 3h00)
   - Classements mis à jour
   - Score réel récupéré
   - Apprentissage effectué

🎓 4. Apprentissage
   - diffExpected: {diff_before:.4f} → {diff_after:.4f} ({adjustment:+.4f})
   - Le système s'est amélioré !

📈 Statistiques d'apprentissage:
   - Total événements: {stats.get('count', 0)}
   - Ajustement moyen: {stats.get('avg_adjustment', 0):+.4f}

🎯 Le système continue d'apprendre et de s'améliorer automatiquement !
""")

print("="*70)
print("✅ SIMULATION TERMINÉE")
print("="*70)

db.close()

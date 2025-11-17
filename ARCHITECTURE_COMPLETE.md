# ARCHITECTURE COMPLÈTE - SYSTÈME AVANCÉ

## 📋 RÉSUMÉ

Architecture complète avec :
- ✅ Configuration par ligue (JSON)
- ✅ Base de données SQLite (persistance)
- ✅ Pipeline OCR (GPT-Vision → Tesseract)
- ✅ Scheduler automatique (3h00)
- ✅ Système d'apprentissage (ajustement diffExpected)
- ✅ Nouveaux endpoints FastAPI

---

## 📁 FICHIERS CRÉÉS

### 1. Configuration par ligue
**Fichier:** `/app/config/leagues_params.json`

```json
{
  "LaLiga": {
    "diffExpected": 2.1380,
    "base_expected": 1.4,
    "coeff_min": 0.85,
    "coeff_max": 1.30,
    "coeff_home": 1.0,
    "coeff_away": 1.0,
    "teams": 20
  },
  // ... 10 autres ligues
}
```

**Avantages:**
- Paramètres spécifiques par ligue
- diffExpected adapté à chaque compétition
- Facteurs domicile/extérieur personnalisables

---

### 2. Module de gestion config
**Fichier:** `/app/core/config.py`

**Fonctions principales:**
```python
get_league_params(league_name: str) -> dict
set_league_params(league_name: str, params: dict)
update_league_param(league_name: str, key: str, value)
get_all_leagues() -> list
get_all_params() -> dict
reset_league_to_default(league_name: str)
```

**Caractéristiques:**
- Lecture/écriture thread-safe (RLock)
- Fallback sur valeurs par défaut
- Logging détaillé

**Test:**
```bash
cd /app && python -m core.config
```

---

### 3. Modèles de base de données
**Fichier:** `/app/core/models.py`

**Tables SQLite:**

#### UploadedImage
- id, filename, original_filename
- upload_time, league, home_team, away_team, bookmaker
- processed, analysis_id

#### AnalysisResult
- id, parsed_scores, extracted_count
- most_probable_score, top3_scores, confidence
- ocr_engine, ocr_confidence, ocr_raw_text
- diff_expected_used, base_expected_used, league_used
- real_score, real_score_confirmed, real_score_source
- created_at, updated_at

#### LearningEvent
- id, analysis_id, league, home_team, away_team
- predicted_score, real_score
- diff_expected_before, diff_expected_after, adjustment
- source, created_at

**Fonctions utilitaires:**
```python
init_db()  # Initialise la DB
get_recent_analyses(limit: int = 20)
get_unconfirmed_analyses(limit: int = 100)
confirm_real_score(analysis_id: int, real_score: str, source: str = "manual")
```

**Test:**
```bash
cd /app && python -m core.models
```

---

### 4. Pipeline OCR unifié
**Fichier:** `/app/core/ocr_pipeline.py`

**Fonction principale:**
```python
process_image(image_path: str, prefer_gpt_vision: bool = True) -> Dict
```

**Ordre d'exécution:**
1. **GPT-Vision** (prioritaire)
   - Utilise `tools/vision_ocr_scores.py`
   - Confiance: 95%
   
2. **Tesseract** (fallback)
   - Utilise `ocr_engine.py`
   - Confiance: 70%

**Format de sortie:**
```python
{
    'ocr_engine': 'gpt-vision' | 'tesseract' | None,
    'parsed_scores': [{"home": 2, "away": 1, "cote": 8.5}, ...],
    'raw_text': '...',
    'success': True/False,
    'confidence': 0.0-1.0
}
```

**Test:**
```bash
cd /app && python -m core.ocr_pipeline
```

---

### 5. Service de scheduler
**Fichier:** `/app/core/scheduler_service.py`

**Configuration:**
- Exécution: 3h00 du matin (Europe/Paris)
- Job: `update_all_leagues_job()`
- Statut: `/app/state/scheduler_status.json`

**Fonctions principales:**
```python
start_scheduler() -> BackgroundScheduler
stop_scheduler(scheduler=None)
manual_trigger_update() -> report
get_scheduler_status() -> dict
get_scheduler_info() -> dict
```

**Statut stocké:**
```json
{
  "active": true,
  "last_run": "2025-11-16T03:00:00+01:00",
  "last_error": null,
  "next_run": "2025-11-17T03:00:00+01:00",
  "timezone": "Europe/Paris"
}
```

**Test:**
```bash
cd /app && python -m core.scheduler_service
```

---

### 6. Système d'apprentissage
**Fichier:** `/app/core/learning.py`

**Fonctions principales:**
```python
learn_from_match(
    league: str,
    predicted_score: str,
    real_score: str,
    home_team: str = None,
    away_team: str = None,
    analysis_id: int = None,
    source: str = "manual"
) -> Dict

batch_learning(matches: List[Dict]) -> Dict
update_learning_from_confirmed_matches(days_back: int = 7) -> Dict
get_learning_stats(league: str = None, days: int = 30) -> Dict
```

**Algorithme d'ajustement:**
```python
# Calculer la différence de buts
pred_diff = abs(predicted_home - predicted_away)
real_diff = abs(real_home - real_away)

# Erreur
error = real_diff - pred_diff

# Ajustement (learning rate = 0.1)
adjustment = error * 0.1

# Nouvelle valeur
new_diff = current_diff + adjustment
new_diff = max(0.5, min(new_diff, 5.0))  # Contraintes
```

**Exemple:**
```python
# Match: Prédit 2-1 (diff=1), Réel 3-0 (diff=3)
error = 3 - 1 = 2
adjustment = 2 * 0.1 = +0.2
diffExpected = 2.1380 + 0.2 = 2.3380
```

**Test:**
```bash
cd /app && python -m core.learning
```

---

### 7. Nouveaux endpoints FastAPI
**Fichier:** `/app/backend/server.py` (ajoutés)

#### Gestion des images

**POST `/api/upload-image-advanced`**
- Upload image avec OCR avancé
- Sauvegarde en DB
- Paramètres: file, league, home_team, away_team, bookmaker, prefer_gpt_vision

**GET `/api/last-uploads?limit=20`**
- Liste des dernières images uploadées

**GET `/api/last-analyses?limit=20`**
- Liste des dernières analyses

#### Configuration

**POST `/api/set-league-param`**
- Met à jour un paramètre d'une ligue
- Paramètres: league, key, value

**GET `/api/get-league-params?league=LaLiga`**
- Récupère les paramètres d'une ligue

**GET `/api/all-leagues-params`**
- Récupère tous les paramètres de toutes les ligues

**POST `/api/set-prefer-ocr`**
- Configure GPT-Vision vs Tesseract
- Body: `{"prefer_gpt_vision": true/false}`

#### Scheduler

**GET `/api/scheduler-status`**
- Statut du scheduler (fichier + runtime)

**POST `/api/trigger-update-manual`**
- Déclenche une mise à jour manuelle

#### Apprentissage

**POST `/api/learn-from-match`**
- Apprend d'un match
- Paramètres: league, predicted_score, real_score, home_team, away_team, analysis_id

**GET `/api/learning-stats?league=LaLiga&days=30`**
- Statistiques d'apprentissage

**POST `/api/auto-learning-update`**
- Lance l'apprentissage automatique depuis les analyses confirmées
- Paramètre: days_back=7

---

## 🚀 INITIALISATION AU DÉMARRAGE

Le backend initialise automatiquement :

```python
@app.on_event("startup")
async def startup_event():
    # 1. Initialiser la DB SQLite
    from core.models import init_db
    init_db()
    
    # 2. Démarrer le scheduler
    from core.scheduler_service import start_scheduler
    start_scheduler()
```

---

## 📊 FLUX COMPLET

### Upload et analyse d'image

```
1. User upload image
   ↓
2. POST /api/upload-image-advanced
   - Sauvegarde fichier
   - Crée UploadedImage en DB
   ↓
3. Pipeline OCR
   - GPT-Vision (priorité) → extraction scores
   - Si échec → Tesseract
   ↓
4. Crée AnalysisResult en DB
   - parsed_scores, ocr_engine, confidence
   - Lie à UploadedImage
   ↓
5. Retour JSON avec scores extraits
```

### Apprentissage

```
1. User fournit score réel
   ↓
2. POST /api/learn-from-match
   - league, predicted_score, real_score
   ↓
3. Calcul ajustement
   - error = |real_diff - pred_diff|
   - adjustment = error * 0.1
   ↓
4. Mise à jour diffExpected
   - new_diff = current + adjustment
   - Sauvegarde dans leagues_params.json
   ↓
5. Crée LearningEvent en DB
   - Historique complet
```

### Mise à jour automatique (3h00)

```
1. Scheduler déclenche update_all_leagues_job()
   ↓
2. Pour chaque ligue:
   - Football-Data.org API
   - SoccerData fallback
   - Scrapers personnalisés (Ligue 2, Europa League)
   - Cache local
   ↓
3. Sauvegarde données ligues
   - /app/data/leagues/*.json
   - Cache multi-sources
   ↓
4. (Optionnel) Apprentissage automatique
   - Récupération analyses non confirmées
   - Tentative match avec scores réels
   - Ajustement diffExpected
   ↓
5. Rapport de mise à jour
   - Statut par ligue
   - Fichier status JSON
```

---

## 🔧 COMMANDES UTILES

### Tests unitaires
```bash
# Config
python -m core.config

# Modèles DB
python -m core.models

# Pipeline OCR
python -m core.ocr_pipeline

# Scheduler
python -m core.scheduler_service

# Apprentissage
python -m core.learning
```

### API via curl

```bash
# Upload image
curl -X POST http://localhost:8001/api/upload-image-advanced \
  -F "file=@/path/to/image.jpg" \
  -F "league=LaLiga" \
  -F "prefer_gpt_vision=true"

# Statut scheduler
curl http://localhost:8001/api/scheduler-status

# Paramètres ligue
curl http://localhost:8001/api/get-league-params?league=LaLiga

# Apprentissage
curl -X POST http://localhost:8001/api/learn-from-match \
  -F "league=LaLiga" \
  -F "predicted_score=2-1" \
  -F "real_score=3-0"

# Stats apprentissage
curl "http://localhost:8001/api/learning-stats?league=LaLiga&days=30"

# Déclencher mise à jour
curl -X POST http://localhost:8001/api/trigger-update-manual
```

---

## 📈 AVANTAGES DE CETTE ARCHITECTURE

### 1. Persistance complète
✅ Toutes les images sauvegardées
✅ Toutes les analyses en DB
✅ Historique d'apprentissage complet

### 2. Flexibilité OCR
✅ Toggle GPT-Vision/Tesseract
✅ Fallback automatique
✅ Confiance par moteur

### 3. Apprentissage par ligue
✅ diffExpected adapté par compétition
✅ Ajustement automatique
✅ Statistiques détaillées

### 4. Scheduler robuste
✅ Mise à jour quotidienne automatique
✅ Statut en temps réel
✅ Déclenchement manuel possible

### 5. Thread-safe
✅ Locks pour config
✅ Session DB par requête
✅ Scheduler background

### 6. Extensible
✅ Facile d'ajouter nouvelles ligues
✅ Facile d'ajouter nouveaux paramètres
✅ API REST complète

---

## 🎯 PROCHAINES ÉTAPES

1. **Intégration avec score_predictor.py**
   - Utiliser les paramètres par ligue dans les calculs
   - Remplacer diffExpected global par diffExpected par ligue

2. **Frontend**
   - Dashboard de gestion des paramètres
   - Visualisation des analyses
   - Interface d'apprentissage

3. **Récupération automatique scores réels**
   - Scraping après les matchs
   - Match des analyses avec résultats
   - Apprentissage automatique

4. **Optimisation**
   - Cache des calculs
   - Batch processing des images
   - Webhooks pour notifications

---

## 📝 NOTES IMPORTANTES

### Base de données
- SQLite pour dev/MVP
- Migration PostgreSQL recommandée pour production
- Backup automatique à configurer

### Scheduler
- Timezone: Europe/Paris
- Configurable via environment
- Logs dans `/app/logs/`

### Apprentissage
- Learning rate: 0.1 (ajustable)
- Contraintes: diffExpected ∈ [0.5, 5.0]
- Historique conservé indéfiniment

### OCR
- GPT-Vision: coût par image
- Tesseract: gratuit, moins précis
- Preference stockée: `/app/state/ocr_preference.json`

---

**Version:** 1.0
**Date:** 16 novembre 2025
**Auteur:** Système de développement IA

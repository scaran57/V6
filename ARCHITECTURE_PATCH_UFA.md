# 🎯 Architecture Patch - Système d'Apprentissage Séparé

## Vue d'ensemble

Ce patch résout le problème d'incohérence de l'apprentissage entre le Mode Production et le Mode Analyzer UEFA en créant deux systèmes d'apprentissage séparés.

## 🏗️ Architecture Après Patch

```
/app/backend/
│
├── production_phase1/           ← NOUVEAU
│   ├── __init__.py
│   └── save_real_score.py       ← Enregistre les scores réels (SANS apprentissage)
│
├── ufa/                         ← NOUVEAU
│   ├── __init__.py
│   ├── analyzer.py              ← Prédictions avec coefficients de ligue
│   └── training/
│       ├── __init__.py
│       └── trainer.py           ← Apprentissage par ligue
│
├── league_scheduler.py          ← MODIFIÉ: appelle train_from_real_matches()
└── server.py                    ← MODIFIÉ: nouvel endpoint /api/save-real-score
```

## 📂 Nouveaux Fichiers

### 1. `/app/backend/production_phase1/save_real_score.py`

**Rôle** : Enregistrement simple des scores réels sans apprentissage

**Fonctions** :
- `save_real_score()` : Enregistre un score dans `/app/data/real_scores.jsonl`
- `get_real_scores()` : Récupère les scores enregistrés

**Format des données** :
```json
{
  "timestamp": "2025-11-08T01:00:00",
  "match_id": "match_12345",
  "league": "LaLiga",
  "home_team": "Real Madrid",
  "away_team": "Barcelona",
  "home_goals": 2,
  "away_goals": 1,
  "source": "production_phase1"
}
```

### 2. `/app/backend/ufa/analyzer.py`

**Rôle** : Système d'analyse avec coefficients de ligue et priors ajustables

**Classe principale** : `UFAAnalyzer`

**Attributs** :
```python
priors = {
    "draw_prior": 0.28,        # Probabilité de nul
    "avg_goals": 2.7,          # Moyenne de buts
    "home_advantage": 1.05,    # Avantage domicile
    "high_score_penalty": 0.75 # Pénalité scores élevés
}
```

**Méthodes** :
- `predict_score_distribution()` : Prédit les probabilités de scores
- `adjust_priors()` : Ajuste les priors selon la performance
- `load_state()` / `save_state()` : Gestion de l'état

### 3. `/app/backend/ufa/training/trainer.py`

**Rôle** : Système d'apprentissage par ligue

**Fonctions principales** :

#### `train_from_real_matches()`
- Charge les scores réels depuis `/app/data/real_scores.jsonl`
- Compare avec les prédictions UFA
- Calcule la perte (log-loss) par ligue
- Ajuste automatiquement les priors
- Sauvegarde l'état dans `/app/backend/ufa/training/state.json`

#### `calculate_loss(predicted_distribution, real_score)`
- Utilise la cross-entropy (log-loss)
- Formule : `loss = -log(P(score_réel))`

**Fichiers générés** :
- `/app/backend/ufa/training/state.json` : État actuel
- `/app/data/ufa_training_history.jsonl` : Historique complet

### 4. Modifications dans `league_scheduler.py`

**Nouvelle méthode** : `_run_ufa_training()`

**Séquence quotidienne (3h00)** :
1. Mise à jour des ligues (league_unified)
2. Validation des prédictions (prediction_validator)
3. **Entraînement UFA** ← NOUVEAU

### 5. Modifications dans `server.py`

**Nouvel endpoint** : `POST /api/save-real-score`

**Paramètres** :
- `match_id` : ID du match
- `league` : Nom de la ligue
- `home_team` : Équipe domicile
- `away_team` : Équipe extérieur
- `home_goals` : Buts domicile
- `away_goals` : Buts extérieur

**Exemple d'utilisation** :
```bash
curl -X POST http://localhost:8001/api/save-real-score \
  -F "match_id=match_123" \
  -F "league=LaLiga" \
  -F "home_team=Real Madrid" \
  -F "away_team=Barcelona" \
  -F "home_goals=2" \
  -F "away_goals=1"
```

## 🔄 Flux de Fonctionnement

### Mode Production (Phase 1)

```
1. Utilisateur fait une prédiction
   ↓
2. Prédiction affichée (SANS coefficients de ligue)
   ↓
3. Utilisateur entre le score réel
   ↓
4. Score enregistré dans real_scores.jsonl
   (AUCUN apprentissage)
   ↓
5. Fin
```

### Mode Analyzer UEFA

```
1. Utilisateur fait une prédiction
   ↓
2. Prédiction avec coefficients de ligue (0.85-1.30)
   ↓
3. Utilisateur entre le score réel
   ↓
4. Score enregistré dans real_scores.jsonl
   ↓
5. Fin
```

### Apprentissage Automatique (3h00 chaque jour)

```
1. Scheduler se déclenche à 3h00
   ↓
2. Mise à jour des ligues
   ↓
3. Validation des prédictions
   ↓
4. APPRENTISSAGE UFA:
   ├─ Charge tous les scores réels
   ├─ Pour chaque match:
   │  ├─ Obtient la ligue
   │  ├─ Récupère les coefficients
   │  ├─ Prédit la distribution
   │  ├─ Compare avec score réel
   │  └─ Calcule la perte (loss)
   ├─ Calcule moyenne par ligue
   ├─ Ajuste les priors automatiquement
   └─ Sauvegarde l'état
   ↓
5. Fin
```

## 📊 Système de Métriques

### Par Ligue

```json
{
  "LaLiga": {
    "avg_loss": 2.34,
    "matches": 15,
    "accuracy": 26.7
  },
  "PremierLeague": {
    "avg_loss": 1.89,
    "matches": 12,
    "accuracy": 33.3
  }
}
```

### Globale

```json
{
  "timestamp": "2025-11-08T03:00:00",
  "matches_processed": 49,
  "global_avg_loss": 2.15,
  "priors": {
    "draw_prior": 0.28,
    "avg_goals": 2.64,
    "home_advantage": 1.05
  }
}
```

## 🎯 Avantages de Cette Architecture

| Aspect | Avant | Après |
|--------|-------|-------|
| **Apprentissage** | Global, mélangé | Séparé par mode ✅ |
| **Coefficients** | Incohérence possible | Cohérent par ligue ✅ |
| **Priors** | Fixes | Ajustables automatiquement ✅ |
| **Performance** | Pas de métriques par ligue | Métriques détaillées ✅ |
| **Maintenance** | Complexe | Modulaire ✅ |

## 📝 Utilisation

### 1. Enregistrer un score réel (Frontend)

```javascript
// Mode Production
const response = await fetch(`${API_URL}/api/save-real-score`, {
  method: 'POST',
  body: new FormData({
    match_id: 'match_123',
    league: 'Unknown', // Ou ligue détectée
    home_team: homeTeam,
    away_team: awayTeam,
    home_goals: homeGoals,
    away_goals: awayGoals
  })
});
```

### 2. Lancer le training manuellement (Test)

```bash
python3 /app/backend/ufa/training/trainer.py
```

### 3. Vérifier l'état du training

```bash
cat /app/backend/ufa/training/state.json
```

### 4. Voir l'historique d'apprentissage

```bash
tail -20 /app/data/ufa_training_history.jsonl
```

## 🔧 Configuration

### Ajuster les priors manuellement

Éditer `/app/backend/ufa/analyzer.py` :

```python
self.priors = {
    "draw_prior": 0.28,        # ↑ pour plus de nuls prédits
    "avg_goals": 2.7,          # ↑ pour scores plus élevés
    "home_advantage": 1.05,    # ↑ pour favoriser domicile
    "high_score_penalty": 0.75 # ↓ pour pénaliser moins les scores élevés
}
```

### Désactiver l'apprentissage automatique

Commenter dans `/app/backend/league_scheduler.py` :

```python
# self._run_ufa_training()  # Désactivé
```

## 🧪 Tests

### Test 1 : Enregistrement d'un score

```bash
curl -X POST http://localhost:8001/api/save-real-score \
  -F "match_id=test_123" \
  -F "league=LaLiga" \
  -F "home_team=Real Madrid" \
  -F "away_team=Barcelona" \
  -F "home_goals=2" \
  -F "away_goals=1"
```

### Test 2 : Lancer le training

```bash
python3 /app/backend/ufa/training/trainer.py
```

### Test 3 : Vérifier l'état

```bash
cat /app/backend/ufa/training/state.json | python3 -m json.tool
```

## 📈 Monitoring

### Fichiers à surveiller

1. `/app/data/real_scores.jsonl` : Scores réels enregistrés
2. `/app/backend/ufa/training/state.json` : État actuel du training
3. `/app/data/ufa_training_history.jsonl` : Historique complet
4. `/var/log/supervisor/backend.out.log` : Logs du scheduler

### Métriques importantes

- **Perte moyenne (avg_loss)** : Plus bas = meilleur
  - < 1.5 : Excellent
  - 1.5-2.5 : Bon
  - > 2.5 : Nécessite ajustement

- **Accuracy** : % de scores exacts prédits
  - > 30% : Excellent
  - 20-30% : Bon
  - < 20% : À améliorer

## 🚀 Migration depuis l'Ancien Système

### Données existantes

Les données de l'ancien système (`/app/data/learning_events.jsonl`) restent intactes et continuent de fonctionner pour le système global `diffExpected`.

### Coexistence

Les deux systèmes peuvent coexister :
- **Ancien** : Apprentissage global via `/api/learn`
- **Nouveau** : Apprentissage par ligue via `/api/save-real-score` + training UFA

## ✅ Résumé

Cette architecture patch permet :

1. ✅ Séparation claire des modes Production et UFA
2. ✅ Apprentissage cohérent par ligue
3. ✅ Ajustement automatique des priors
4. ✅ Métriques détaillées par ligue
5. ✅ Aucune régression sur le système existant
6. ✅ Training automatique quotidien
7. ✅ Monitoring complet

**Status** : Système Patch Implémenté et Opérationnel ✅

# Documentation UFA Auto-Validate

## Vue d'ensemble

Le système `ufa_auto_validate.py` est un script automatique qui scanne, valide et prépare les scores réels pour l'entraînement du système UFA (Unified Football Analytics).

## Fonctionnalités

### 1. Validation Automatique des Scores
- Scanne `/app/data/real_scores.jsonl` pour les entrées non validées
- Vérifie la présence et le format des scores (0-9 buts)
- Marque les entrées validées avec `validated: true` et `validated_at: <timestamp>`

### 2. Normalisation des Équipes
- Utilise le fichier `/app/data/team_map.json` (dérivé de `ocr_parser.py`)
- Applique le fuzzy matching (FuzzyWuzzy) avec seuil de 75%
- Détecte automatiquement la ligue basée sur les équipes
- Ajoute les champs `home_team_normalized` et `away_team_normalized`

### 3. Détection de Doublons
- Vérifie les doublons basés sur:
  - Mêmes équipes (home + away)
  - Même ligue
  - Timestamps dans une fenêtre de 7 jours
- Marque les doublons avec `validated: false` et `validation_error: "duplicate"`

### 4. Déclenchement de l'Entraînement
- Prépare un payload minimal pour chaque match validé
- Tente d'abord l'API (si `TRAIN_API_URL` est défini)
- Sinon, appelle le script local (`TRAIN_SCRIPT`)
- Marque les matchs entraînés avec `trained: true` et `trained_at: <timestamp>`

### 5. Logging Détaillé
- Tous les événements sont enregistrés dans `/app/logs/ufa_auto_train.log`
- Format: `[UFA-AUTO] <timestamp> - <message>`
- Trace complète des validations, doublons, erreurs

## Configuration

### Variables d'environnement (optionnel)
```bash
# API d'entraînement (prioritaire)
export UFA_TRAIN_API="http://localhost:8001/api/learn?auto=true"

# Script d'entraînement (fallback)
export UFA_TRAIN_SCRIPT="/app/backend/ufa/training/train_ufa_model.py"
```

### Fichiers de configuration
- `REAL_SCORES_FILE`: `/app/data/real_scores.jsonl`
- `TEAM_MAP_FILE`: `/app/data/team_map.json` (133 équipes)
- `LOG_FILE`: `/app/logs/ufa_auto_train.log`

### Seuils configurables
- `FUZZY_THRESHOLD`: 75 (seuil de correspondance fuzzy)
- `MIN_GOAL` / `MAX_GOAL`: 0-9 (plage de buts valides)
- `DUPLICATE_WINDOW_DAYS`: 7 (fenêtre de détection de doublons)

## Structure du Fichier real_scores.jsonl

### Avant validation
```json
{
  "home_team": "PSG",
  "away_team": "Marseille",
  "home_goals": 2,
  "away_goals": 1,
  "league": "Ligue1",
  "source": "ocr_auto",
  "timestamp": "2025-11-09T10:00:00"
}
```

### Après validation réussie
```json
{
  "home_team": "PSG",
  "away_team": "Marseille",
  "home_goals": 2,
  "away_goals": 1,
  "league": "Ligue1",
  "source": "ocr_auto",
  "timestamp": "2025-11-09T10:00:00",
  "home_team_normalized": "psg",
  "away_team_normalized": "marseille",
  "validated": true,
  "validated_at": "2025-11-09T11:05:23.456789",
  "trained": true,
  "trained_at": "2025-11-09T11:05:25.123456"
}
```

### Après marquage comme doublon
```json
{
  "home_team": "PSG",
  "away_team": "Marseille",
  "home_goals": 2,
  "away_goals": 1,
  "league": "Ligue1",
  "validated": false,
  "validation_error": "duplicate"
}
```

## Utilisation

### Exécution manuelle
```bash
python3 /app/backend/ufa/ufa_auto_validate.py
```

### Exécution automatique via scheduler
Le script est intégré dans `league_scheduler.py` et s'exécute automatiquement:
- **Quand**: Après la mise à jour quotidienne des ligues (3h00)
- **Ordre**: 
  1. Mise à jour des ligues
  2. Validation des prédictions
  3. **Auto-validation UFA** ← Nouveau
  4. Entraînement UFA
  5. Vérification d'équilibre

### Exécution périodique via cron (optionnel)
Pour des exécutions plus fréquentes (ex: toutes les 10 minutes):
```bash
*/10 * * * * /usr/bin/python3 /app/backend/ufa/ufa_auto_validate.py >> /app/logs/ufa_auto_validate_cron.log 2>&1
```

## Logs

### Consulter les logs
```bash
# Dernières lignes du log
tail -f /app/logs/ufa_auto_train.log

# Rechercher des validations réussies
grep "Validated:" /app/logs/ufa_auto_train.log

# Rechercher des doublons
grep "duplicate" /app/logs/ufa_auto_train.log

# Compter les entrées traitées
grep "validated" /app/logs/ufa_auto_train.log | wc -l
```

### Format des logs
```
[UFA-AUTO] 2025-11-09T11:14:02.467139 - ufa_auto_validate started
[UFA-AUTO] 2025-11-09T11:14:02.470943 - Found 92 pending entries, 0 already validated/trained.
[UFA-AUTO] 2025-11-09T11:14:02.471115 - Validated: manchester city vs liverpool (1-1) - PremierLeague
[UFA-AUTO] 2025-11-09T11:14:02.471115 - Training triggered for match: manchester city vs liverpool
[UFA-AUTO] 2025-11-09T11:14:02.471052 - Entry #0 marked duplicate: real madrid vs barcelona (LaLiga)
[UFA-AUTO] 2025-11-09T11:14:02.743388 - Updated real_scores.jsonl (2 validated, 2 trained).
[UFA-AUTO] 2025-11-09T11:14:02.743440 - ufa_auto_validate finished
```

## Workflow Complet

```
┌─────────────────────────────────┐
│ Nouvelle entrée dans            │
│ real_scores.jsonl               │
│ (validated: absent ou false)    │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 1. Validation du format         │
│    - Score présent (0-9 buts)   │
│    - Équipes présentes          │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 2. Normalisation équipes        │
│    - Fuzzy matching team_map    │
│    - Détection ligue            │
│    - Ajout champs normalized    │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 3. Vérification doublons        │
│    - Même équipes + ligue       │
│    - Fenêtre 7 jours            │
└────────────┬────────────────────┘
             │
             ▼
        ┌────┴────┐
        │Doublon? │
        └────┬────┘
     OUI│    │NON
        │    │
        ▼    ▼
    ┌───────────────────┐  ┌───────────────────┐
    │ Marquer duplicate │  │ Marquer validated │
    │ validated: false  │  │ validated: true   │
    └───────────────────┘  └─────────┬─────────┘
                                     │
                                     ▼
                          ┌───────────────────┐
                          │ Préparer payload  │
                          │ pour training     │
                          └─────────┬─────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │ Déclencher        │
                          │ training UFA      │
                          └─────────┬─────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │ Marquer trained   │
                          │ trained: true     │
                          └───────────────────┘
```

## Intégration avec le Système UFA

### Fichiers créés/modifiés
1. ✅ `/app/backend/ufa/ufa_auto_validate.py` - Script principal
2. ✅ `/app/backend/ufa/training/train_ufa_model.py` - Wrapper training
3. ✅ `/app/data/team_map.json` - Table de mapping équipes → ligues
4. ✅ `/app/logs/ufa_auto_train.log` - Fichier de log
5. ✅ `/app/backend/league_scheduler.py` - Ajout méthode `_run_ufa_auto_validate()`

### Dépendances installées
```bash
pip install python-Levenshtein requests
```

### Flux de données
```
OCR Parser (ocr_parser.py)
    ↓
Real Scores (real_scores.jsonl)
    ↓
Auto-Validate (ufa_auto_validate.py) ← Nouveau
    ↓
UFA Training (trainer.py)
    ↓
UFA Priors (priors ajustés)
    ↓
Prédictions améliorées
```

## Statistiques et Monitoring

### Vérifier l'état du système
```bash
# Nombre total d'entrées
wc -l /app/data/real_scores.jsonl

# Entrées validées
grep -c '"validated": true' /app/data/real_scores.jsonl

# Entrées entraînées
grep -c '"trained": true' /app/data/real_scores.jsonl

# Doublons détectés
grep -c '"validation_error": "duplicate"' /app/data/real_scores.jsonl
```

### Analyser les performances
```bash
# Dernières validations réussies
grep "Validated:" /app/logs/ufa_auto_train.log | tail -10

# Derniers entraînements déclenchés
grep "Training triggered" /app/logs/ufa_auto_train.log | tail -10

# Erreurs récentes
grep "ERROR\|error\|failed" /app/logs/ufa_auto_train.log | tail -10
```

## Maintenance

### Nettoyer les doublons
Si trop de doublons s'accumulent, vous pouvez:
```bash
# Sauvegarder l'original
cp /app/data/real_scores.jsonl /app/data/real_scores.jsonl.backup

# Filtrer les doublons (garder seulement validated: true)
grep '"validated": true' /app/data/real_scores.jsonl > /app/data/real_scores_clean.jsonl
mv /app/data/real_scores_clean.jsonl /app/data/real_scores.jsonl
```

### Réinitialiser le statut de validation
Pour revalider toutes les entrées:
```bash
# ATTENTION: Cela forcera la revalidation de TOUTES les entrées
python3 << 'EOF'
import json
from pathlib import Path

file_path = Path("/app/data/real_scores.jsonl")
entries = []
with file_path.open("r") as f:
    for line in f:
        if line.strip():
            entry = json.loads(line)
            # Retirer les flags de validation
            entry.pop("validated", None)
            entry.pop("validated_at", None)
            entry.pop("trained", None)
            entry.pop("trained_at", None)
            entry.pop("validation_error", None)
            entries.append(entry)

with file_path.open("w") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

print(f"✅ Reset de {len(entries)} entrées")
EOF
```

## Troubleshooting

### Problème: Script ne trouve pas les équipes
**Solution**: Vérifier que `/app/data/team_map.json` existe et contient les équipes
```bash
cat /app/data/team_map.json | jq 'length'  # Devrait afficher ~133
```

### Problème: Training ne se déclenche pas
**Solution**: Vérifier les chemins et permissions
```bash
# Vérifier le script de training
ls -la /app/backend/ufa/training/train_ufa_model.py

# Tester manuellement
python3 /app/backend/ufa/training/train_ufa_model.py
```

### Problème: Trop de doublons marqués
**Solution**: Ajuster `DUPLICATE_WINDOW_DAYS` dans le script
```python
# Dans ufa_auto_validate.py, ligne ~45
DUPLICATE_WINDOW_DAYS = 14  # Augmenter la fenêtre à 14 jours
```

### Problème: Logs trop volumineux
**Solution**: Rotation des logs
```bash
# Archiver les anciens logs
gzip /app/logs/ufa_auto_train.log
mv /app/logs/ufa_auto_train.log.gz /app/logs/archive/ufa_auto_train_$(date +%Y%m%d).log.gz

# Nouveau log vide
touch /app/logs/ufa_auto_train.log
```

## Améliorations Futures

### Possibles évolutions
1. **API REST endpoint**: Exposer `/api/ufa/auto-validate` pour déclencher manuellement
2. **Dashboard de monitoring**: Interface web pour visualiser les validations
3. **Alertes**: Notifications en cas d'erreurs répétées
4. **Statistiques avancées**: Rapport hebdomadaire de performance
5. **Machine Learning**: Amélioration du fuzzy matching avec modèles ML

### Configuration avancée
```python
# Ajouter dans ufa_auto_validate.py
ENABLE_AUTO_LEAGUE_DETECTION = True  # Détecter ligue automatiquement
ENABLE_DUPLICATE_CHECK = True        # Activer vérification doublons
ENABLE_AUTO_TRAINING = True          # Déclencher training automatiquement
RETRY_FAILED_TRAINING = True         # Réessayer les trainings échoués
MAX_RETRIES = 3                      # Nombre de tentatives max
```

## Résumé

✅ **Script créé et testé** : `/app/backend/ufa/ufa_auto_validate.py`
✅ **Intégré au scheduler** : Exécution automatique quotidienne
✅ **Logging complet** : `/app/logs/ufa_auto_train.log`
✅ **Normalisation avancée** : Fuzzy matching + team_map
✅ **Détection de doublons** : Évite les entrées en double
✅ **Training automatique** : Déclenche l'entraînement UFA

Le système est maintenant **100% automatisé** : de la capture OCR à l'entraînement du modèle UFA.

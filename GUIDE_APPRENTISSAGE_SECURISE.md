# 🔒 Guide - Système d'Apprentissage Sécurisé

## 📋 Vue d'Ensemble

Ce système empêche la perte de données d'apprentissage grâce à :
- **Log append-only** (learning_events.jsonl) - source de vérité immuable
- **Écritures atomiques** (tmp + rename)
- **Versioning de schéma** (protection contre corruptions)
- **Reconstruction possible** depuis le log

---

## 🏗️ Architecture

```
/app/data/
├── learning_events.jsonl      # 🔐 LOG APPEND-ONLY (immuable)
├── teams_data.json             # Derniers N matchs par équipe
├── learning_meta.json          # diffExpected + schema_version
└── matches_memory.json         # Mémoire des analyses

/app/modules/
└── local_learning_safe.py      # Module de lecture/écriture sécurisé

/app/scripts/
├── rebuild_from_learning_log.py    # Reconstruction depuis le log
└── migrate_existing_data.py        # Migration données existantes
```

---

## 🔑 Fonctions Principales

### 1. `record_learning_event()`

**La fonction à utiliser TOUJOURS pour enregistrer un apprentissage**

```python
from modules.local_learning_safe import record_learning_event

success, event = record_learning_event(
    match_id="ajax-galatasaray-2025-11-05",
    home_team="Ajax Amsterdam",
    away_team="Galatasaray",
    predicted="2-1",
    real="3-0",
    agent_id="my_agent",
    keep_last=5  # Nombre de matchs à conserver par équipe
)

if success:
    print(f"✅ Apprentissage enregistré: {event}")
else:
    print(f"❌ Erreur: {event}")
```

**Ce qu'elle fait:**
1. ✅ Ajoute une ligne au log append-only (immuable)
2. ✅ Met à jour teams_data.json (derniers N matchs)
3. ✅ Recalcule diffExpected avec formule 60/40
4. ✅ Tout est atomique (pas de corruption possible)

### 2. `load_meta()` / `save_meta()`

```python
from modules.local_learning_safe import load_meta, save_meta

# Charger
meta = load_meta()
print(f"diffExpected: {meta['diffExpected']}")

# Sauvegarder (utiliser avec prudence !)
meta['diffExpected'] = 2.5
save_meta(meta)
```

### 3. `load_teams()` / `save_teams()`

```python
from modules.local_learning_safe import load_teams, save_teams

# Charger
teams = load_teams()
print(f"Équipes: {list(teams.keys())}")

# Sauvegarder (utiliser avec prudence !)
teams['PSG'] = [[2, 1], [3, 0]]
save_teams(teams)
```

### 4. `get_learning_stats()`

```python
from modules.local_learning_safe import get_learning_stats

stats = get_learning_stats()
print(f"Total événements: {stats['total_learning_events']}")
print(f"Équipes: {stats['teams_count']}")
print(f"diffExpected: {stats['diffExpected']}")
```

### 5. `check_schema_compatibility()`

```python
from modules.local_learning_safe import check_schema_compatibility

if not check_schema_compatibility():
    print("⚠️ ATTENTION: Schéma incompatible!")
    # Ne pas écrire les données
else:
    print("✅ Schéma compatible")
```

---

## 🔧 Scripts de Maintenance

### Reconstruction depuis le log

Si teams_data.json ou learning_meta.json sont corrompus :

```bash
# Reconstruction avec 20 matchs par équipe
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 20

# Reconstruction avec 5 matchs par équipe (défaut)
python3 /app/scripts/rebuild_from_learning_log.py
```

**Ce script:**
- ✅ Lit le log complet (immuable)
- ✅ Rejoue tous les événements
- ✅ Reconstruit teams_data.json
- ✅ Recalcule diffExpected

### Migration des données existantes

Pour créer le log depuis des données existantes :

```bash
python3 /app/scripts/migrate_existing_data.py
```

---

## 📡 API Endpoints

### POST `/api/learn` (Modifié)

Utilise maintenant le système sécurisé automatiquement.

```bash
curl -X POST http://localhost:8001/api/learn \
  -F "predicted=2-1" \
  -F "real=3-0" \
  -F "home_team=Ajax" \
  -F "away_team=Galatasaray"
```

**Réponse:**
```json
{
  "success": true,
  "message": "Modèle ajusté avec le score réel: 3-0 ✅",
  "newDiffExpected": 1.8,
  "event": {
    "ts": 1730831234.567,
    "iso": "2025-11-05T18:20:34Z",
    "match_id": "learn_1730831234",
    "home": "Ajax",
    "away": "Galatasaray",
    "predicted": "2-1",
    "real": "3-0",
    "agent_id": "api_learn_endpoint",
    "schema_version": 2
  }
}
```

### POST `/api/admin/rebuild-learning`

Reconstruit les données depuis le log.

```bash
curl -X POST "http://localhost:8001/api/admin/rebuild-learning?keep_last=20"
```

### GET `/api/admin/learning-stats`

Retourne les statistiques d'apprentissage.

```bash
curl http://localhost:8001/api/admin/learning-stats
```

**Réponse:**
```json
{
  "success": true,
  "stats": {
    "total_learning_events": 32,
    "teams_count": 4,
    "diffExpected": 1.624,
    "schema_version": 2,
    "log_file_exists": true,
    "teams_file_exists": true,
    "meta_file_exists": true
  }
}
```

### GET `/api/admin/export-learning-log`

Télécharge le log complet pour backup.

```bash
curl -o backup.jsonl http://localhost:8001/api/admin/export-learning-log
```

---

## ⚠️ RÈGLES IMPORTANTES

### ✅ À FAIRE

1. **Toujours utiliser `record_learning_event()`** pour enregistrer
2. **Vérifier la compatibilité** avant d'écrire:
   ```python
   if check_schema_compatibility():
       record_learning_event(...)
   ```
3. **Faire des backups réguliers** du log:
   ```bash
   cp /app/data/learning_events.jsonl /backup/
   ```
4. **Utiliser le script rebuild** en cas de corruption
5. **Documenter l'agent_id** lors des enregistrements

### ❌ À NE PAS FAIRE

1. ❌ **Ne JAMAIS modifier manuellement** learning_events.jsonl
2. ❌ **Ne JAMAIS supprimer** learning_events.jsonl (sauf admin)
3. ❌ **Ne JAMAIS écraser** directement teams_data.json
4. ❌ **Ne JAMAIS écrire sans vérifier** le schéma
5. ❌ **Ne JAMAIS ignorer** les erreurs de `record_learning_event()`

---

## 🔄 Format du Log (learning_events.jsonl)

Chaque ligne est un événement JSON :

```json
{
  "ts": 1730831234.567,
  "iso": "2025-11-05T18:20:34Z",
  "match_id": "ajax-galatasaray-2025-11-05",
  "home": "Ajax Amsterdam",
  "away": "Galatasaray",
  "predicted": "2-1",
  "real": "3-0",
  "agent_id": "main_agent",
  "schema_version": 2
}
```

**Avantages:**
- ✅ Append-only (jamais modifié, seulement ajouté)
- ✅ Horodatage précis (ts + iso)
- ✅ Traçabilité (agent_id)
- ✅ Versioning (schema_version)
- ✅ Reconstruction possible à tout moment

---

## 📊 Schéma des Fichiers

### learning_meta.json
```json
{
  "diffExpected": 1.624,
  "schema_version": 2
}
```

### teams_data.json
```json
{
  "Ajax Amsterdam": [
    [2, 1],  // [buts_marqués, buts_encaissés]
    [3, 0],
    [1, 2],
    [0, 0],
    [2, 2]
  ],
  "Galatasaray": [
    [1, 2],
    [0, 3],
    [2, 1],
    [0, 0],
    [2, 2]
  ]
}
```

---

## 🧪 Tests et Vérifications

### Test basique

```python
from modules.local_learning_safe import record_learning_event, get_learning_stats

# Enregistrer un test
success, event = record_learning_event(
    match_id="test_001",
    home_team="Team A",
    away_team="Team B",
    predicted="1-1",
    real="2-0",
    agent_id="test"
)

assert success, "L'enregistrement a échoué"

# Vérifier les stats
stats = get_learning_stats()
print(f"Total: {stats['total_learning_events']}")
```

### Test de reconstruction

```bash
# Sauvegarder l'état actuel
cp /app/data/teams_data.json /tmp/teams_backup.json

# Supprimer (simulation corruption)
rm /app/data/teams_data.json

# Reconstruire
python3 /app/scripts/rebuild_from_learning_log.py

# Vérifier que c'est identique
diff /tmp/teams_backup.json /app/data/teams_data.json
```

---

## 🛡️ Protection Contre les Agents Futurs

### Métadonnées de traçabilité

Chaque événement enregistre:
- **agent_id**: Identifier qui a fait la modification
- **schema_version**: Vérifier la compatibilité
- **timestamp**: Ordre chronologique garanti

### Vérification avant écriture

```python
from modules.local_learning_safe import check_schema_compatibility

if not check_schema_compatibility():
    print("⚠️ Schéma incompatible - NE PAS ÉCRIRE")
    # Alerter, loguer, ou arrêter
    raise Exception("Schéma incompatible")

# Sinon, procéder normalement
record_learning_event(...)
```

---

## 💾 Backup et Restauration

### Backup manuel

```bash
# Backup complet
tar czvf backup_learning_$(date +%Y%m%d_%H%M%S).tgz /app/data/learning_events.jsonl /app/data/teams_data.json /app/data/learning_meta.json

# Backup du log seul (le plus important)
cp /app/data/learning_events.jsonl /backup/learning_$(date +%Y%m%d).jsonl
```

### Restauration

```bash
# 1. Restaurer le log
cp /backup/learning_20251105.jsonl /app/data/learning_events.jsonl

# 2. Reconstruire les fichiers dérivés
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 20
```

---

## 📈 Évolution Future

### Version 3 (planifiée)

Futures améliorations possibles:
- Compression du log (gzip)
- Index pour recherches rapides
- Archivage automatique (rotation)
- Statistiques avancées par agent
- Détection d'anomalies

### Migration vers v3

Le système de versioning permet des migrations sûres :

```python
def migrate_v2_to_v3():
    # Lire v2
    # Transformer
    # Écrire v3
    # Marquer schema_version = 3
    pass
```

---

## 🆘 Dépannage

### Problème: "Schéma incompatible"

```bash
# Vérifier la version
python3 -c "from modules.local_learning_safe import load_meta; print(load_meta())"

# Si différent de 2, migration nécessaire
```

### Problème: "Log corrompu"

```bash
# Vérifier l'intégrité
python3 -c "
import json
with open('/app/data/learning_events.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except:
            print(f'Ligne {i} corrompue')
"

# Supprimer les lignes corrompues si nécessaire
# Puis reconstruire
python3 /app/scripts/rebuild_from_learning_log.py
```

### Problème: "Perte de données"

```bash
# Si le log existe, tout est récupérable
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 100

# Si le log n'existe pas, données perdues
# → Restaurer depuis backup
```

---

## ✅ Checklist de Sécurité

- [ ] Le log append-only existe et n'est jamais supprimé
- [ ] Tous les enregistrements passent par `record_learning_event()`
- [ ] Le schema_version est vérifié avant écriture
- [ ] Des backups réguliers du log sont effectués
- [ ] Le script rebuild est testé et fonctionne
- [ ] Les agents futurs utilisent ce système
- [ ] La documentation est à jour

---

**Date de mise en place**: 2025-11-05  
**Version du système**: 2.0  
**Auteur**: Système de sécurisation d'apprentissage

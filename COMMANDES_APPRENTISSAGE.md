# 🔧 Commandes Utiles - Système d'Apprentissage Sécurisé

## 📊 Vérification et Statistiques

### Voir les statistiques
```bash
curl -s http://localhost:8001/api/admin/learning-stats | python -m json.tool
```

### Compter les événements
```bash
wc -l /app/data/learning_events.jsonl
```

### Voir les derniers événements
```bash
tail -n 10 /app/data/learning_events.jsonl | python -m json.tool
```

### Afficher diffExpected actuel
```bash
cat /app/data/learning_meta.json | python -m json.tool
```

### Voir les équipes
```bash
cat /app/data/teams_data.json | python -m json.tool
```

---

## 🔄 Reconstruction et Migration

### Reconstruire avec 20 matchs par équipe
```bash
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 20
```

### Reconstruire avec valeur par défaut (5)
```bash
python3 /app/scripts/rebuild_from_learning_log.py
```

### Migrer les données existantes
```bash
python3 /app/scripts/migrate_existing_data.py
```

---

## 💾 Backup et Export

### Backup complet
```bash
tar czvf /tmp/backup_learning_$(date +%Y%m%d_%H%M%S).tgz \
  /app/data/learning_events.jsonl \
  /app/data/teams_data.json \
  /app/data/learning_meta.json \
  /app/backend/data/matches_memory.json
```

### Export du log via API
```bash
curl -o /tmp/learning_backup.jsonl \
  http://localhost:8001/api/admin/export-learning-log
```

### Copie manuelle du log
```bash
cp /app/data/learning_events.jsonl /tmp/learning_backup_$(date +%Y%m%d).jsonl
```

---

## 🧪 Tests et Apprentissage

### Enregistrer un apprentissage via API
```bash
curl -X POST http://localhost:8001/api/learn \
  -F "predicted=2-1" \
  -F "real=3-0" \
  -F "home_team=PSG" \
  -F "away_team=Lyon"
```

### Enregistrer via Python
```python
import sys
sys.path.insert(0, '/app')
from modules.local_learning_safe import record_learning_event

success, event = record_learning_event(
    match_id="test_match_001",
    home_team="Real Madrid",
    away_team="Barcelona",
    predicted="2-1",
    real="1-1",
    agent_id="manual_test"
)

print(f"Success: {success}")
print(f"Event: {event}")
```

### Vérifier schema
```python
import sys
sys.path.insert(0, '/app')
from modules.local_learning_safe import check_schema_compatibility

compatible = check_schema_compatibility()
print(f"Schema compatible: {compatible}")
```

---

## 🔍 Analyse du Log

### Compter par agent
```bash
cat /app/data/learning_events.jsonl | \
  jq -r '.agent_id' | \
  sort | uniq -c
```

### Compter par équipe
```bash
cat /app/data/learning_events.jsonl | \
  jq -r '.home' | \
  sort | uniq -c
```

### Voir les 10 premiers événements
```bash
head -n 10 /app/data/learning_events.jsonl | python -m json.tool
```

### Filtrer par équipe
```bash
cat /app/data/learning_events.jsonl | \
  jq 'select(.home == "Ajax Amsterdam")'
```

### Statistiques temporelles
```bash
cat /app/data/learning_events.jsonl | \
  jq -r '.iso' | \
  cut -d'T' -f1 | \
  sort | uniq -c
```

---

## 🛠️ Maintenance

### Vérifier intégrité du log
```bash
python3 -c "
import json
errors = 0
with open('/app/data/learning_events.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except Exception as e:
            print(f'Ligne {i} corrompue: {e}')
            errors += 1

if errors == 0:
    print('✅ Log intègre')
else:
    print(f'❌ {errors} lignes corrompues')
"
```

### Nettoyer les fichiers temporaires
```bash
rm -f /app/data/*.tmp
```

### Voir la taille des fichiers
```bash
ls -lh /app/data/
```

---

## 🔄 Restauration après Problème

### Scenario 1: teams_data.json corrompu

```bash
# Sauvegarder le corrompu
mv /app/data/teams_data.json /tmp/teams_corrupted.json

# Reconstruire depuis le log
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 20

# Vérifier
cat /app/data/teams_data.json | python -m json.tool
```

### Scenario 2: learning_meta.json perdu

```bash
# Reconstruire (inclut le meta)
python3 /app/scripts/rebuild_from_learning_log.py

# Vérifier
cat /app/data/learning_meta.json
```

### Scenario 3: Tout perdu sauf le log

```bash
# Le log suffit pour tout reconstruire
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 20

# Tout est restauré
ls -la /app/data/
```

---

## 📡 Endpoints API Récapitulatifs

### Endpoints Admin

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/admin/learning-stats` | GET | Statistiques d'apprentissage |
| `/api/admin/rebuild-learning` | POST | Reconstruction depuis log |
| `/api/admin/export-learning-log` | GET | Export du log complet |

### Endpoint Principal

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/learn` | POST | Enregistrer apprentissage (sécurisé) |

---

## 🎯 Workflow Typique

### Apprentissage quotidien

```bash
# 1. Enregistrer les apprentissages via API ou Python
curl -X POST http://localhost:8001/api/learn -F "predicted=2-0" -F "real=1-1"

# 2. Vérifier les stats
curl -s http://localhost:8001/api/admin/learning-stats

# 3. Backup quotidien
tar czvf /backup/learning_$(date +%Y%m%d).tgz /app/data/learning_events.jsonl
```

### Maintenance hebdomadaire

```bash
# 1. Vérifier l'intégrité
python3 -c "from modules.local_learning_safe import get_learning_stats; print(get_learning_stats())"

# 2. Backup complet
tar czvf /backup/weekly_$(date +%Y%m%d).tgz /app/data/

# 3. Vérifier l'espace disque
du -sh /app/data/
```

### Après migration/upgrade

```bash
# 1. Vérifier la compatibilité
python3 -c "from modules.local_learning_safe import check_schema_compatibility; print(check_schema_compatibility())"

# 2. Reconstruire si nécessaire
python3 /app/scripts/rebuild_from_learning_log.py

# 3. Tester avec un apprentissage
curl -X POST http://localhost:8001/api/learn -F "predicted=0-0" -F "real=0-0" -F "home_team=Test" -F "away_team=Test"
```

---

## 🚨 Commandes d'Urgence

### En cas de corruption

```bash
# 1. STOP - Ne rien écrire
# 2. Backup immédiat de tout
tar czvf /tmp/emergency_backup_$(date +%s).tgz /app/data/

# 3. Reconstruction complète
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 50

# 4. Vérification
curl -s http://localhost:8001/api/admin/learning-stats
```

### Reset complet (DANGER)

```bash
# ⚠️ ATTENTION: Supprime TOUT sauf le log
rm -f /app/data/teams_data.json /app/data/learning_meta.json

# Reconstruire depuis zéro
python3 /app/scripts/rebuild_from_learning_log.py --keep-last 100

# Vérifier
ls -la /app/data/
```

---

## 📝 Notes Importantes

1. **Ne JAMAIS supprimer** `learning_events.jsonl` - c'est la source de vérité
2. **Toujours utiliser** `record_learning_event()` pour écrire
3. **Faire des backups réguliers** du log
4. **Tester la reconstruction** périodiquement
5. **Documenter l'agent_id** pour traçabilité

---

**Dernière mise à jour**: 2025-11-05  
**Version du système**: 2.0

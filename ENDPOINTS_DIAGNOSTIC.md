# 🔍 Endpoints de Diagnostic

Documentation des endpoints pour diagnostiquer l'état du système de prédiction.

---

## 📊 GET `/api/diagnostic/system-status`

Retourne un diagnostic complet du système incluant l'apprentissage, les analyses et la configuration.

### Requête

```bash
curl http://localhost:8001/api/diagnostic/system-status
```

### Réponse

```json
{
  "success": true,
  "timestamp": "2025-11-05T23:53:29.090665",
  "learning_system": {
    "total_events": 19,
    "teams_count": 3,
    "diffExpected": 1.509,
    "schema_version": 2,
    "files_ok": true
  },
  "matches_memory": {
    "total_matches_analyzed": 0,
    "last_match_id": null
  },
  "current_config": {
    "diffExpected": 1.509
  },
  "status": "operational"
}
```

### Interprétation

| Champ | Description |
|-------|-------------|
| `learning_system.total_events` | Nombre total d'apprentissages enregistrés |
| `learning_system.teams_count` | Nombre d'équipes avec historique |
| `learning_system.diffExpected` | Différence de buts attendue (ajustée par apprentissage) |
| `learning_system.schema_version` | Version du schéma (doit être 2) |
| `learning_system.files_ok` | Tous les fichiers critiques présents |
| `matches_memory.total_matches_analyzed` | Nombre d'analyses en mémoire |
| `current_config.diffExpected` | Valeur actuellement utilisée par le système |
| `status` | État général (operational/warning/error) |

---

## 🔍 GET `/api/diagnostic/last-analysis`

Retourne la dernière analyse effectuée (dernier match analysé via upload d'image).

### Requête

```bash
curl http://localhost:8001/api/diagnostic/last-analysis
```

### Réponse (si une analyse existe)

```json
{
  "success": true,
  "match_id": "kairatintermilan_bookmakerinconnu_2025-11-05",
  "analysis": {
    "match_name": "Kairat - Inter Milan",
    "bookmaker": "Bookmaker inconnu",
    "analyzed_at": "2025-11-05T17:51:06.123456",
    "confidence": 0.304,
    "top3": [
      {"score": "3-2", "probability": 30.88},
      {"score": "4-2", "probability": 13.8},
      {"score": "2-0", "probability": 7.96}
    ],
    "extracted_scores": [...],
    "probabilities": {...}
  }
}
```

### Réponse (si aucune analyse)

```json
{
  "success": false,
  "message": "Aucune analyse en mémoire"
}
```

---

## 📈 Cas d'Usage

### 1. Vérification Rapide de Santé

```bash
# Vérifier que tout fonctionne
curl -s http://localhost:8001/api/diagnostic/system-status | jq '.status'
# Output: "operational"
```

### 2. Voir le Nombre d'Apprentissages

```bash
curl -s http://localhost:8001/api/diagnostic/system-status | jq '.learning_system.total_events'
# Output: 19
```

### 3. Vérifier diffExpected Actuel

```bash
curl -s http://localhost:8001/api/diagnostic/system-status | jq '.current_config.diffExpected'
# Output: 1.509
```

### 4. Consulter la Dernière Analyse

```bash
curl -s http://localhost:8001/api/diagnostic/last-analysis | jq '.analysis.match_name'
# Output: "Kairat - Inter Milan"
```

### 5. Monitoring Automatisé

```bash
#!/bin/bash
# Script de monitoring

STATUS=$(curl -s http://localhost:8001/api/diagnostic/system-status)

# Vérifier l'état
if echo "$STATUS" | jq -e '.status == "operational"' > /dev/null; then
  echo "✅ Système opérationnel"
else
  echo "❌ Problème détecté!"
  echo "$STATUS" | jq '.'
fi

# Vérifier les fichiers
FILES_OK=$(echo "$STATUS" | jq -r '.learning_system.files_ok')
if [ "$FILES_OK" != "true" ]; then
  echo "⚠️ Fichiers manquants!"
fi

# Alerter si peu d'événements
EVENTS=$(echo "$STATUS" | jq -r '.learning_system.total_events')
if [ "$EVENTS" -lt 5 ]; then
  echo "⚠️ Peu d'apprentissages ($EVENTS)"
fi
```

---

## 🔔 Alertes et Seuils

### Seuils Recommandés

| Métrique | Seuil Minimum | Action si < Seuil |
|----------|---------------|-------------------|
| `total_events` | 10 | ⚠️ Ajouter plus d'apprentissages |
| `teams_count` | 2 | ℹ️ Système fonctionnel mais limité |
| `files_ok` | true | ❌ CRITIQUE - Vérifier fichiers |
| `diffExpected` | 0.5 - 3.0 | ⚠️ Valeur inhabituelle |

### États du Système

| Status | Description | Action |
|--------|-------------|--------|
| `operational` | ✅ Tout fonctionne | Aucune |
| `warning` | ⚠️ Problème mineur | Vérifier logs |
| `error` | ❌ Problème critique | Intervention requise |

---

## 🛠️ Dépannage via Diagnostic

### Problème : diffExpected incohérent

```bash
# Comparer les valeurs
curl -s http://localhost:8001/api/diagnostic/system-status | \
  jq '{learning: .learning_system.diffExpected, current: .current_config.diffExpected}'

# Si différent, reconstruire
python3 /app/scripts/rebuild_from_learning_log.py
```

### Problème : Aucune analyse en mémoire

```bash
# Vérifier si le endpoint d'analyse fonctionne
curl -X POST http://localhost:8001/api/analyze \
  -F "file=@test_image.jpg"

# Puis vérifier à nouveau
curl http://localhost:8001/api/diagnostic/last-analysis
```

### Problème : files_ok = false

```bash
# Identifier les fichiers manquants
python3 /app/scripts/check_learning_system.py

# Reconstruire si nécessaire
python3 /app/scripts/rebuild_from_learning_log.py
```

---

## 📊 Intégration avec d'autres Endpoints

### Workflow Complet de Vérification

```bash
# 1. État général
curl -s http://localhost:8001/api/health

# 2. Diagnostic complet
curl -s http://localhost:8001/api/diagnostic/system-status

# 3. Statistiques d'apprentissage détaillées
curl -s http://localhost:8001/api/admin/learning-stats

# 4. Dernière analyse
curl -s http://localhost:8001/api/diagnostic/last-analysis

# 5. Rapport système
curl -s http://localhost:8001/api/report
```

### Comparaison des Endpoints

| Endpoint | Type | Utilisation |
|----------|------|-------------|
| `/api/health` | Simple | Check rapide (up/down) |
| `/api/diagnostic/system-status` | Détaillé | État complet du système |
| `/api/admin/learning-stats` | Apprentissage | Focus sur les données d'apprentissage |
| `/api/diagnostic/last-analysis` | Analyse | Dernière prédiction effectuée |
| `/api/report` | Rapport | Rapport textuel formaté |

---

## 🔄 Automatisation

### Cron Job de Monitoring

```bash
# Ajouter dans crontab
*/15 * * * * /usr/bin/curl -s http://localhost:8001/api/diagnostic/system-status | /usr/bin/jq -r '.status' | grep -q operational || echo "⚠️ Système en problème" | mail -s "Alert" admin@example.com
```

### Script Python de Monitoring

```python
import requests
import json

def check_system_health():
    """Vérifie la santé du système"""
    try:
        response = requests.get('http://localhost:8001/api/diagnostic/system-status')
        data = response.json()
        
        if not data.get('success'):
            print("❌ Requête échouée")
            return False
        
        # Vérifications
        checks = {
            "État général": data.get('status') == 'operational',
            "Fichiers OK": data['learning_system'].get('files_ok'),
            "Events > 10": data['learning_system'].get('total_events', 0) >= 10,
            "diffExpected cohérent": abs(
                data['learning_system'].get('diffExpected', 0) - 
                data['current_config'].get('diffExpected', 0)
            ) < 0.01
        }
        
        all_ok = all(checks.values())
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check}")
        
        return all_ok
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    healthy = check_system_health()
    exit(0 if healthy else 1)
```

---

## 📝 Notes

- Les endpoints de diagnostic sont **en lecture seule**
- Ils ne modifient **aucune donnée**
- Peuvent être appelés **aussi souvent que nécessaire**
- Utiles pour **monitoring continu** et **debugging**

---

**Dernière mise à jour**: 2025-11-05  
**Version**: 1.0

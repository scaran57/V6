# 📡 API Endpoints - Prédicteur de Score

Documentation complète de tous les endpoints disponibles dans l'application.

## 🏠 Base URL

```
http://localhost:8001/api
```

---

## 📊 Endpoints Principaux

### 1. Health Check

**GET** `/api/health`

Vérifie que l'API est en ligne.

**Réponse:**
```json
{
  "status": "ok",
  "message": "API de prédiction de score en ligne ✅"
}
```

---

### 2. Analyse d'image

**POST** `/api/analyze`

Analyse une image de bookmaker et prédit le score le plus probable.

**Paramètres:**
- `file`: Fichier image (multipart/form-data)

**Réponse:**
```json
{
  "success": true,
  "fromMemory": false,
  "matchId": "kairatintermilan_bookmakerinconnu_2025-11-05",
  "matchName": "Kairat - Inter Milan",
  "bookmaker": "Bookmaker inconnu",
  "extractedScores": [
    {"score": "0-0", "odds": 6.6},
    {"score": "1-0", "odds": 12.5}
  ],
  "mostProbableScore": "3-2",
  "probabilities": {
    "0-0": 11.23,
    "1-0": 8.45,
    "3-2": 30.88
  },
  "confidence": 0.304,
  "top3": [
    {"score": "3-2", "probability": 30.88},
    {"score": "4-2", "probability": 13.8},
    {"score": "2-0", "probability": 7.96}
  ]
}
```

**Notes:**
- `fromMemory: true` si le match a déjà été analysé (résultat figé)
- `fromMemory: false` pour une nouvelle analyse

---

### 3. Apprentissage

**POST** `/api/learn`

Ajuste le modèle avec le score prédit vs le score réel.

**Paramètres (form-data):**
- `predicted`: Score prédit (ex: "2-1")
- `real`: Score réel (ex: "1-1")
- `home_team`: Nom équipe domicile (optionnel)
- `away_team`: Nom équipe extérieur (optionnel)

**Réponse:**
```json
{
  "success": true,
  "message": "Modèle ajusté avec le score réel: 1-1 ✅",
  "newDiffExpected": 0.5
}
```

---

### 4. Récupération de diffExpected

**GET** `/api/diff`

Récupère la différence de buts attendue (paramètre du modèle).

**Réponse:**
```json
{
  "diffExpected": 0.5
}
```

---

## 🧠 Endpoints de Mémoire

### 5. Liste tous les matchs

**GET** `/api/matches/memory`

Récupère tous les matchs en mémoire.

**Réponse:**
```json
{
  "success": true,
  "total_matches": 2,
  "matches": {
    "kairatintermilan_bookmakerinconnu_2025-11-05": {
      "match_id": "kairatintermilan_bookmakerinconnu_2025-11-05",
      "match_name": "Kairat - Inter Milan",
      "bookmaker": "Bookmaker inconnu",
      "confidence": 0.304,
      "top3": [...],
      "analyzed_at": "2025-11-05T17:51:06.123456"
    }
  }
}
```

---

### 6. Récupérer un match spécifique

**GET** `/api/matches/{match_id}`

Récupère les détails d'un match par son ID.

**Exemple:**
```
GET /api/matches/kairatintermilan_bookmakerinconnu_2025-11-05
```

**Réponse:**
```json
{
  "success": true,
  "match": {
    "match_id": "kairatintermilan_bookmakerinconnu_2025-11-05",
    "match_name": "Kairat - Inter Milan",
    "bookmaker": "Bookmaker inconnu",
    "extracted_scores": [...],
    "probabilities": {...},
    "confidence": 0.304,
    "top3": [...],
    "analyzed_at": "2025-11-05T17:51:06.123456"
  }
}
```

---

### 7. Supprimer un match

**DELETE** `/api/matches/{match_id}`

Supprime un match de la mémoire.

**Réponse:**
```json
{
  "success": true,
  "message": "Match kairatintermilan_bookmakerinconnu_2025-11-05 supprimé"
}
```

---

### 8. Effacer toute la mémoire

**DELETE** `/api/matches/memory/clear`

Supprime tous les matchs de la mémoire.

**Réponse:**
```json
{
  "success": true,
  "message": "Mémoire complètement effacée"
}
```

---

## 📊 Endpoints de Rapport

### 9. Rapport complet (JSON)

**GET** `/api/system/report`

Génère un rapport détaillé avec statistiques et données structurées.

**Réponse:**
```json
{
  "timestamp": "2025-11-05T17:59:26.123456",
  "last_update": "2025-11-05 17:59:26",
  "statistics": {
    "total_matches": 2,
    "average_confidence": 0.222,
    "bookmakers_count": 1,
    "bookmakers_distribution": {
      "Bookmaker inconnu": 2
    }
  },
  "recent_matches": [
    {
      "match_id": "...",
      "match_name": "Kairat - Inter Milan",
      "bookmaker": "Bookmaker inconnu",
      "confidence": 0.304,
      "top_score": "3-2",
      "analyzed_at": "2025-11-05T17:51:06.123456"
    }
  ],
  "status": "operational",
  "report_text": "..."
}
```

---

### 10. Rapport simplifié (texte)

**GET** `/api/report`

Retourne uniquement le rapport textuel formaté.

**Réponse:**
```json
{
  "rapport": "\n===============================\n📊 RAPPORT DE SUIVI AUTOMATIQUE\n===============================\n\n🕒 Dernière mise à jour : 2025-11-05 17:59:26\n📁 Matchs mémorisés : 2\n..."
}
```

---

## 👥 Endpoints d'Équipes

### 11. Statistiques de toutes les équipes

**GET** `/api/teams/stats`

Récupère les statistiques de toutes les équipes.

**Réponse:**
```json
{
  "teams": {
    "PSG": {
      "matches_count": 5,
      "avg_goals_for": 2.3,
      "avg_goals_against": 1.1,
      "recent_matches": [...]
    }
  },
  "total_teams": 10
}
```

---

### 12. Statistiques d'une équipe

**GET** `/api/teams/{team_name}`

Récupère les statistiques d'une équipe spécifique.

**Exemple:**
```
GET /api/teams/PSG
```

**Réponse:**
```json
{
  "team": "PSG",
  "found": true,
  "avg_goals_for": 2.3,
  "avg_goals_against": 1.1,
  "matches_count": 5,
  "recent_matches": [...]
}
```

---

## 📝 Exemples d'utilisation

### Curl

```bash
# Health check
curl http://localhost:8001/api/health

# Analyser une image
curl -X POST http://localhost:8001/api/analyze \
  -F "file=@bookmaker.jpg"

# Apprentissage
curl -X POST http://localhost:8001/api/learn \
  -F "predicted=2-1" \
  -F "real=1-1"

# Rapport
curl http://localhost:8001/api/report
```

### Python (requests)

```python
import requests

# Analyse d'image
with open('bookmaker.jpg', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://localhost:8001/api/analyze', files=files)
    result = response.json()
    print(f"Score prédit: {result['mostProbableScore']}")

# Rapport
response = requests.get('http://localhost:8001/api/report')
print(response.json()['rapport'])
```

### JavaScript (fetch)

```javascript
// Analyse d'image
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8001/api/analyze', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log('Score prédit:', result.mostProbableScore);

// Rapport
const report = await fetch('http://localhost:8001/api/report');
const data = await report.json();
console.log(data.rapport);
```

---

## 🔐 Notes de sécurité

- Tous les endpoints sont accessibles sans authentification (development mode)
- En production, ajouter une authentification JWT ou API key
- Limiter le taux de requêtes (rate limiting)
- Valider la taille des fichiers uploadés

---

## 🐛 Codes d'erreur

| Code | Signification |
|------|---------------|
| 200 | Succès |
| 400 | Requête invalide |
| 404 | Ressource non trouvée |
| 500 | Erreur serveur |

---

## 📚 Documentation interactive

Une fois le serveur lancé, accédez à la documentation Swagger interactive :

```
http://localhost:8001/docs
```

Ou à la documentation ReDoc :

```
http://localhost:8001/redoc
```

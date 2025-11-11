# 🎯 Intégration Unified Analyzer - Documentation Complète

## 📊 Vue d'ensemble

Le **Unified Analyzer** est une nouvelle API qui fusionne **Analyzer UEFA** et **Mode Production** en un seul endpoint unifié. Cette intégration résout définitivement le problème des analyses perdues et assure que tous les coefficients de ligue sont toujours appliqués.

## ✅ Problèmes Résolus

### Avant (Problèmes)
- ❌ Analyses perdues (cache non sauvegardé)
- ❌ Confusion entre Mode Production et Analyzer UEFA
- ❌ Coefficients parfois non appliqués
- ❌ Pas de traçabilité des analyses
- ❌ Doublons dans les analyses

### Après (Solutions)
- ✅ Toutes les analyses sauvegardées dans `analysis_cache.jsonl`
- ✅ Un seul endpoint pour tous les modes
- ✅ Coefficients **toujours** appliqués automatiquement
- ✅ Traçabilité complète (timestamp, source, etc.)
- ✅ Détection de doublons possible

## 🚀 Nouvelle API

### Endpoint Principal

```
POST /api/unified/analyze
```

**Paramètres (Form Data) :**
- `file` (required) : Image du bookmaker (JPEG/PNG)
- `manual_home` (optional) : Override manuel équipe domicile
- `manual_away` (optional) : Override manuel équipe extérieur
- `manual_league` (optional) : Override manuel ligue
- `persist_cache` (optional, default: true) : Sauvegarder dans le cache

**Réponse JSON :**
```json
{
  "success": true,
  "matchName": "PSG - Marseille",
  "league": "Ligue1",
  "leagueCoeffsApplied": true,
  "mostProbableScore": "2-1",
  "probabilities": {
    "2-1": 12.5,
    "1-1": 10.2,
    "2-0": 9.8
  },
  "confidence": 0.85,
  "top3": [
    {"score": "2-1", "probability": 12.5},
    {"score": "1-1", "probability": 10.2},
    {"score": "2-0", "probability": 9.8}
  ],
  "savedToCache": true,
  "timestamp": "2025-11-09T20:01:57.138529",
  "info": {
    "home_team": "PSG",
    "away_team": "Marseille",
    "league": "Ligue1",
    "home_goals_detected": null,
    "away_goals_detected": null
  }
}
```

### Endpoint de Santé

```
GET /api/unified/health
```

**Réponse JSON :**
```json
{
  "status": "ok",
  "analysis_cache": "/app/data/analysis_cache.jsonl",
  "real_scores": "/app/data/real_scores.jsonl",
  "cache_entries": 1,
  "real_scores_entries": 143
}
```

## 💻 Intégration Frontend

### Option 1 : JavaScript Fetch

```javascript
// Dans votre composant React
async function analyzeImage(imageFile) {
  const formData = new FormData();
  formData.append('file', imageFile);
  formData.append('persist_cache', 'true');
  
  // Optional: manual overrides
  // formData.append('manual_home', 'PSG');
  // formData.append('manual_away', 'Marseille');
  // formData.append('manual_league', 'Ligue1');
  
  try {
    const response = await fetch('/api/unified/analyze', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log('✅ Analyse réussie');
      console.log('Match:', result.matchName);
      console.log('Ligue:', result.league);
      console.log('Score probable:', result.mostProbableScore);
      console.log('Coefficients appliqués:', result.leagueCoeffsApplied);
      console.log('Top 3:', result.top3);
      
      // Afficher les résultats dans l'UI
      displayResults(result);
    } else {
      console.error('❌ Erreur:', result.error);
    }
  } catch (error) {
    console.error('❌ Exception:', error);
  }
}

function displayResults(result) {
  // Mettre à jour votre UI avec les résultats
  document.getElementById('match-name').textContent = result.matchName;
  document.getElementById('league').textContent = result.league;
  document.getElementById('most-probable').textContent = result.mostProbableScore;
  
  // Afficher le top 3
  const top3List = document.getElementById('top3-list');
  top3List.innerHTML = '';
  result.top3.forEach(item => {
    const li = document.createElement('li');
    li.textContent = `${item.score}: ${item.probability.toFixed(2)}%`;
    top3List.appendChild(li);
  });
}
```

### Option 2 : Axios

```javascript
import axios from 'axios';

async function analyzeImage(imageFile) {
  const formData = new FormData();
  formData.append('file', imageFile);
  formData.append('persist_cache', 'true');
  
  try {
    const { data } = await axios.post('/api/unified/analyze', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    if (data.success) {
      console.log('✅ Analyse réussie:', data);
      return data;
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    console.error('❌ Erreur:', error);
    throw error;
  }
}
```

### Option 3 : React Component Complet

```jsx
import React, { useState } from 'react';
import axios from 'axios';

function UnifiedAnalyzer() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setError(null);
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError('Veuillez sélectionner une image');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('persist_cache', 'true');

    try {
      const { data } = await axios.post('/api/unified/analyze', formData);
      
      if (data.success) {
        setResult(data);
      } else {
        setError(data.error || 'Erreur inconnue');
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="unified-analyzer">
      <h2>🎯 Analyse Unifiée (UEFA + Production)</h2>
      
      <div className="upload-section">
        <input 
          type="file" 
          accept="image/*" 
          onChange={handleFileChange}
        />
        <button 
          onClick={handleAnalyze} 
          disabled={!file || loading}
        >
          {loading ? '⏳ Analyse en cours...' : '🔍 Analyser & Sauvegarder'}
        </button>
      </div>

      {error && (
        <div className="error">
          ❌ {error}
        </div>
      )}

      {result && (
        <div className="results">
          <h3>✅ Résultats de l'Analyse</h3>
          
          <div className="match-info">
            <p><strong>Match :</strong> {result.matchName}</p>
            <p><strong>Ligue :</strong> {result.league}</p>
            <p>
              <strong>Coefficients appliqués :</strong> 
              {result.leagueCoeffsApplied ? ' ✅ Oui' : ' ❌ Non'}
            </p>
          </div>

          <div className="prediction">
            <h4>Score le plus probable</h4>
            <div className="score-badge">
              {result.mostProbableScore}
            </div>
            <p>Confiance : {(result.confidence * 100).toFixed(1)}%</p>
          </div>

          <div className="top3">
            <h4>Top 3 des scores</h4>
            <ol>
              {result.top3.map((item, idx) => (
                <li key={idx}>
                  <span className="score">{item.score}</span>
                  <span className="probability">{item.probability.toFixed(2)}%</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="metadata">
            <p><small>
              Sauvegardé : {result.savedToCache ? '✅' : '❌'} | 
              Timestamp : {new Date(result.timestamp).toLocaleString()}
            </small></p>
          </div>
        </div>
      )}
    </div>
  );
}

export default UnifiedAnalyzer;
```

## 🧪 Tests

### Test 1 : Upload via cURL

```bash
# Test avec une image
curl -X POST "https://aiscore-oracle.preview.emergentagent.com/api/unified/analyze" \
  -F "file=@/path/to/your/image.jpg" \
  -F "persist_cache=true" \
  | jq '.'

# Test avec overrides manuels
curl -X POST "https://aiscore-oracle.preview.emergentagent.com/api/unified/analyze" \
  -F "file=@/path/to/your/image.jpg" \
  -F "manual_home=PSG" \
  -F "manual_away=Marseille" \
  -F "manual_league=Ligue1" \
  -F "persist_cache=true" \
  | jq '.'
```

### Test 2 : Vérifier le Cache

```bash
# Compter les analyses
cat /app/data/analysis_cache.jsonl | wc -l

# Voir la dernière analyse
tail -1 /app/data/analysis_cache.jsonl | jq '.'

# Filtrer par ligue
cat /app/data/analysis_cache.jsonl | jq 'select(.league == "Ligue1")'

# Statistiques par ligue
cat /app/data/analysis_cache.jsonl | jq -r '.league' | sort | uniq -c
```

### Test 3 : Health Check

```bash
curl "https://aiscore-oracle.preview.emergentagent.com/api/unified/health" | jq '.'
```

## 📂 Fichiers et Stockage

### Structure des Fichiers

```
/app/
├── data/
│   ├── analysis_cache.jsonl      # ✨ NOUVEAU : Cache des analyses
│   ├── real_scores.jsonl         # Scores réels pour training
│   ├── team_map.json             # Mapping équipes → ligues
│   └── matches_memory.json       # (Ancien cache, peut être déprécié)
├── uploads/
│   └── unified/                  # ✨ NOUVEAU : Uploads unified analyzer
├── backend/
│   └── ufa/
│       ├── unified_analyzer.py   # ✨ NOUVEAU : Module unified analyzer
│       ├── ufa_auto_validate.py  # Auto-validation API
│       └── training/
└── logs/
    └── ufa_auto_train.log
```

### Format analysis_cache.jsonl

Chaque ligne est un objet JSON :

```json
{
  "timestamp": "2025-11-09T20:01:57.138529",
  "source": "ocr_unified",
  "home_team": "PSG",
  "away_team": "Marseille",
  "league": "Ligue1",
  "home_goals_detected": null,
  "away_goals_detected": null,
  "raw_text": "PSG vs Marseille",
  "prediction": {
    "status": "success",
    "most_probable": "2-1",
    "probabilities": {"2-1": 12.5, "1-1": 10.2},
    "confidence": 0.85,
    "league_coeffs_applied": true,
    "top3": [
      {"score": "2-1", "probability": 12.5},
      {"score": "1-1", "probability": 10.2},
      {"score": "2-0", "probability": 9.8}
    ]
  }
}
```

## 🔄 Migration depuis l'Ancien Système

### Mettre à jour le Frontend

**Ancien code (Mode Production) :**
```javascript
// ❌ Ancien
fetch('/api/analyze', {
  method: 'POST',
  body: formData
})
```

**Nouveau code (Unified Analyzer) :**
```javascript
// ✅ Nouveau
fetch('/api/unified/analyze', {
  method: 'POST',
  body: formData
})
```

### Compatibilité

L'ancien endpoint `/api/analyze` reste fonctionnel pour compatibilité ascendante, mais il est **recommandé** de migrer vers `/api/unified/analyze` pour :
- ✅ Sauvegarde automatique des analyses
- ✅ Meilleure traçabilité
- ✅ Compatibilité avec le pipeline UFA
- ✅ Détection de doublons future

## 🎯 Workflow Recommandé

### Pour les Utilisateurs

```
1. Ouvrir https://aiscore-oracle.preview.emergentagent.com/
2. Cliquer sur "Analyser & Sauvegarder (UFA)" (nouveau bouton unifié)
3. Uploader l'image du bookmaker
4. ✅ Résultat avec coefficients appliqués automatiquement
5. ✅ Analyse sauvegardée dans le cache
6. ✅ Consultable ultérieurement
```

### Pour les Développeurs

```
1. Appeler POST /api/unified/analyze avec image
2. Récupérer le résultat JSON
3. Afficher matchName, league, mostProbableScore
4. Afficher top3 des scores
5. Indiquer si coefficients appliqués (leagueCoeffsApplied)
6. Confirmer sauvegarde (savedToCache)
```

## 📊 Monitoring et Analytics

### Tableau de Bord Simple

```bash
#!/bin/bash
# dashboard.sh - Affiche les statistiques du système

echo "📊 Unified Analyzer Dashboard"
echo "=============================="
echo ""

# Analyses totales
total=$(cat /app/data/analysis_cache.jsonl | wc -l)
echo "✅ Total analyses: $total"

# Analyses par ligue
echo ""
echo "📈 Analyses par ligue:"
cat /app/data/analysis_cache.jsonl | jq -r '.league' | sort | uniq -c | sort -rn

# Dernière analyse
echo ""
echo "🕐 Dernière analyse:"
tail -1 /app/data/analysis_cache.jsonl | jq '{time: .timestamp, match: "\(.home_team) vs \(.away_team)", league: .league, score: .prediction.most_probable}'

# Taux de succès coefficients
echo ""
echo "🏆 Taux d'application des coefficients:"
total_with_coeffs=$(cat /app/data/analysis_cache.jsonl | jq -r 'select(.prediction.league_coeffs_applied == true)' | wc -l)
echo "$total_with_coeffs / $total analyses avec coefficients"
```

### Logs Backend

```bash
# Suivre les analyses en temps réel
tail -f /var/log/supervisor/backend.err.log | grep "Unified Analyzer"

# Voir les dernières analyses
tail -50 /var/log/supervisor/backend.err.log | grep -A3 "Unified Analyzer - Analyse terminée"
```

## 🔧 Troubleshooting

### Problème : "No scores detected"

**Cause :** Image de mauvaise qualité ou pas de cotes visibles

**Solution :**
1. Vérifier la qualité de l'image (nette, contrastée)
2. Utiliser les overrides manuels si nécessaire
3. Essayer avec une autre capture

### Problème : "league_coeffs_applied: false"

**Cause :** Équipes ou ligue non détectées

**Solution :**
1. Vérifier les équipes dans les logs : `tail -20 /var/log/supervisor/backend.err.log`
2. Utiliser les overrides manuels :
   ```javascript
   formData.append('manual_home', 'PSG');
   formData.append('manual_away', 'Marseille');
   formData.append('manual_league', 'Ligue1');
   ```

### Problème : Cache non sauvegardé

**Cause :** `persist_cache=false` ou erreur lors de l'écriture

**Solution :**
1. Vérifier que `persist_cache=true`
2. Vérifier les permissions : `ls -la /app/data/`
3. Vérifier l'espace disque : `df -h`

## 🎉 Avantages du Unified Analyzer

### Pour les Utilisateurs
- ✅ Une seule interface pour tout
- ✅ Toutes les analyses sauvegardées automatiquement
- ✅ Coefficients toujours appliqués
- ✅ Traçabilité complète
- ✅ Historique consultable

### Pour les Développeurs
- ✅ Code simplifié (un seul endpoint)
- ✅ Maintenance facilitée
- ✅ Tests plus simples
- ✅ Logs standardisés
- ✅ Pipeline UFA intégré

### Pour le Système
- ✅ Données structurées et cohérentes
- ✅ Compatibilité avec auto-validate
- ✅ Training UFA plus efficace
- ✅ Détection de doublons possible
- ✅ Analytics simplifiées

## 📚 Ressources Complémentaires

- **Guide utilisateur** : `/app/GUIDE_UTILISATION_COEFFICIENTS.md`
- **Documentation UFA V2** : `/app/UFA_AUTO_VALIDATE_V2_DOC.md`
- **Architecture OCR Parser** : `/app/backend/ocr_parser.py`
- **Logs système** : `/var/log/supervisor/backend.err.log`
- **Cache analyses** : `/app/data/analysis_cache.jsonl`

## 🚀 Prochaines Étapes

1. **Migration Frontend** : Mettre à jour tous les boutons pour utiliser `/api/unified/analyze`
2. **Tests E2E** : Tester avec différentes images et bookmakers
3. **Monitoring** : Créer un dashboard de visualisation
4. **Documentation utilisateur** : Guide visuel avec captures d'écran
5. **Analytics** : Analyser les patterns d'utilisation

---

**🎯 Résumé : Le Unified Analyzer est maintenant le point d'entrée unique pour toutes les analyses, garantissant que vos 15+3 analyses (et toutes les futures) seront sauvegardées avec les coefficients appliqués !**

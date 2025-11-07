# 🗂️ Gestion du Cache d'Analyse

Documentation sur le système de cache des analyses et comment le contrôler.

---

## 📋 Vue d'Ensemble

Par défaut, le système **sauvegarde** chaque analyse dans une mémoire pour éviter de recalculer le même match. Cela permet :
- ✅ Résultats **figés et reproductibles**
- ✅ Performances optimisées
- ✅ Traçabilité des analyses

Cependant, pour les **tests** et le **développement**, il est utile de pouvoir :
- 🔄 Forcer un nouveau calcul à chaque upload
- 🗑️ Vider complètement le cache

---

## 🔄 Désactiver le Cache pour une Analyse

### Méthode 1 : Query Parameter

Ajouter `?disable_cache=true` à l'URL de l'endpoint `/api/analyze`.

```bash
curl -X POST "http://localhost:8001/api/analyze?disable_cache=true" \
  -F "file=@bookmaker.jpg"
```

**Résultat :**
```json
{
  "success": true,
  "fromMemory": false,
  "cacheDisabled": true,        // ← Confirme que le cache est désactivé
  "matchName": "PSG - Lyon",
  "mostProbableScore": "2-1",
  ...
}
```

### Méthode 2 : Via Python

```python
import requests

with open('bookmaker.jpg', 'rb') as f:
    files = {'file': f}
    response = requests.post(
        'http://localhost:8001/api/analyze',
        params={'disable_cache': True},
        files=files
    )
    result = response.json()
    print(f"Cache désactivé: {result.get('cacheDisabled')}")
```

### Méthode 3 : Via JavaScript

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch(
  'http://localhost:8001/api/analyze?disable_cache=true',
  {
    method: 'POST',
    body: formData
  }
);

const result = await response.json();
console.log('Cache désactivé:', result.cacheDisabled);
```

---

## 🗑️ Vider Complètement le Cache

### Endpoint Admin

**DELETE** `/api/admin/clear-analysis-cache`

Supprime toutes les analyses en mémoire.

```bash
curl -X DELETE http://localhost:8001/api/admin/clear-analysis-cache
```

**Réponse :**
```json
{
  "success": true,
  "message": "Cache d'analyse vidé avec succès",
  "timestamp": "2025-11-06T00:20:03.065713"
}
```

### Vérification

Après vidage, vérifier que le cache est vide :

```bash
curl -s http://localhost:8001/api/matches/memory | jq '.total_matches'
# Output: 0
```

---

## 🔍 Comportement du Cache

### Avec Cache Activé (défaut)

```
1ère analyse : Image → OCR → Calcul → Sauvegarde en mémoire
               ↓
               Résultat A (confiance: 30%)

2ème analyse : Image (même match) → Récupération mémoire
               ↓
               Résultat A (identique, figé)
```

### Avec Cache Désactivé

```
1ère analyse : Image → OCR → Calcul → PAS de sauvegarde
               ↓
               Résultat A (confiance: 30%)

2ème analyse : Image (même match) → OCR → Calcul → PAS de sauvegarde
               ↓
               Résultat A' (peut être légèrement différent si OCR varie)
```

---

## 📊 Comparaison

| Critère | Cache Activé | Cache Désactivé |
|---------|--------------|-----------------|
| **Performance** | ⚡ Rapide (récupération) | 🐌 Plus lent (calcul complet) |
| **Reproductibilité** | ✅ Identique à chaque fois | ⚠️ Peut varier légèrement |
| **Usage mémoire** | 📈 Augmente avec analyses | 📉 Stable |
| **Tests** | ❌ Difficile (résultats figés) | ✅ Idéal pour tester |
| **Production** | ✅ Recommandé | ❌ Non recommandé |

---

## 🎯 Cas d'Usage

### 1. Tests de l'OCR

Si vous voulez tester l'OCR plusieurs fois sur la même image :

```bash
# Activer le mode test
for i in {1..10}; do
  curl -X POST "http://localhost:8001/api/analyze?disable_cache=true" \
    -F "file=@test.jpg" \
    -s | jq '.extractedScores | length'
done
```

### 2. Comparaison de Versions

Comparer les résultats avant/après modification du code :

```bash
# Version 1
curl -X POST "http://localhost:8001/api/analyze?disable_cache=true" \
  -F "file=@match.jpg" > result_v1.json

# Modifier le code...

# Version 2
curl -X POST "http://localhost:8001/api/analyze?disable_cache=true" \
  -F "file=@match.jpg" > result_v2.json

# Comparer
diff result_v1.json result_v2.json
```

### 3. Nettoyage après Tests

Après une session de tests, vider le cache :

```bash
# Tests multiples
curl -X POST "http://localhost:8001/api/analyze" -F "file=@test1.jpg"
curl -X POST "http://localhost:8001/api/analyze" -F "file=@test2.jpg"
curl -X POST "http://localhost:8001/api/analyze" -F "file=@test3.jpg"

# Nettoyer
curl -X DELETE http://localhost:8001/api/admin/clear-analysis-cache
```

### 4. Développement d'une Nouvelle Fonctionnalité

Pendant le développement, toujours utiliser `disable_cache=true` :

```bash
# Script de test
#!/bin/bash
API="http://localhost:8001/api/analyze?disable_cache=true"

curl -X POST "$API" -F "file=@bookmaker1.jpg" | jq '.confidence'
curl -X POST "$API" -F "file=@bookmaker2.jpg" | jq '.confidence'
curl -X POST "$API" -F "file=@bookmaker3.jpg" | jq '.confidence'
```

---

## ⚙️ Configuration

### Variable d'Environnement (future)

Pour désactiver le cache globalement (tous les appels) :

```bash
# .env
DISABLE_ANALYSIS_CACHE=true
```

### Modifier le Comportement par Défaut

Dans `server.py`, ligne de l'endpoint `/analyze` :

```python
disable_cache: bool = Query(default=False, ...)
#                                   ^^^^
#                                   Changer à True pour désactiver par défaut
```

---

## 🔒 Sécurité

### Accès au Vidage du Cache

L'endpoint `/api/admin/clear-analysis-cache` devrait être protégé en production :

```python
@api_router.delete("/admin/clear-analysis-cache")
async def admin_clear_analysis_cache(
    api_key: str = Header(..., alias="X-API-Key")
):
    if api_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(status_code=403, detail="Non autorisé")
    
    clear_all_matches()
    return {"success": True, ...}
```

---

## 📈 Monitoring

### Surveiller la Taille du Cache

```bash
# Nombre d'analyses en mémoire
curl -s http://localhost:8001/api/matches/memory | jq '.total_matches'

# Diagnostic complet
curl -s http://localhost:8001/api/diagnostic/system-status | \
  jq '.matches_memory'
```

### Alertes

Si le cache devient trop volumineux :

```bash
#!/bin/bash
CACHE_SIZE=$(curl -s http://localhost:8001/api/matches/memory | jq '.total_matches')

if [ "$CACHE_SIZE" -gt 100 ]; then
  echo "⚠️ Cache volumineux ($CACHE_SIZE analyses)"
  # Envoyer alerte ou vider automatiquement
fi
```

---

## 🧪 Tests Automatisés

### Script de Test Complet

```python
import requests

API_BASE = "http://localhost:8001/api"

def test_cache_behavior():
    """Test le comportement du cache"""
    
    # 1. Vider le cache
    response = requests.delete(f"{API_BASE}/admin/clear-analysis-cache")
    assert response.json()['success']
    
    # 2. Première analyse (devrait calculer)
    with open('test.jpg', 'rb') as f:
        response = requests.post(
            f"{API_BASE}/analyze",
            files={'file': f}
        )
    result1 = response.json()
    assert result1['fromMemory'] == False
    
    # 3. Deuxième analyse (devrait venir du cache)
    with open('test.jpg', 'rb') as f:
        response = requests.post(
            f"{API_BASE}/analyze",
            files={'file': f}
        )
    result2 = response.json()
    assert result2['fromMemory'] == True
    
    # 4. Troisième analyse avec cache désactivé (devrait recalculer)
    with open('test.jpg', 'rb') as f:
        response = requests.post(
            f"{API_BASE}/analyze?disable_cache=true",
            files={'file': f}
        )
    result3 = response.json()
    assert result3['cacheDisabled'] == True
    assert result3['fromMemory'] == False
    
    print("✅ Tous les tests passent")

if __name__ == "__main__":
    test_cache_behavior()
```

---

## 📝 Résumé des Commandes

```bash
# Analyser avec cache désactivé
curl -X POST "http://localhost:8001/api/analyze?disable_cache=true" \
  -F "file=@image.jpg"

# Vider le cache
curl -X DELETE http://localhost:8001/api/admin/clear-analysis-cache

# Vérifier la taille du cache
curl -s http://localhost:8001/api/matches/memory | jq '.total_matches'

# Diagnostic complet
curl -s http://localhost:8001/api/diagnostic/system-status
```

---

**Dernière mise à jour**: 2025-11-06  
**Version**: 1.0

# 🧪 Guide de l'Algorithme Combiné - Réglage des Paramètres

## 🎯 Vue d'ensemble

Le nouvel algorithme combiné est une amélioration majeure qui fusionne **trois approches** :

1. **Distribution de Poisson** : Modèle statistique des buts de football
2. **Probabilités implicites des cotes** : Intelligence du marché bookmaker
3. **Smoothing de voisinage** : Lissage pour éviter les pics isolés irréalistes

---

## 📊 Différences avec l'algorithme classique

| Aspect | Algorithme Classique | Algorithme Combiné |
|--------|---------------------|-------------------|
| Base | 1/cote + pondération Poisson | Poisson complet + ImpliedOdds + Smoothing |
| Discrimination | Faible (ALPHA=0.4) | Forte (ALPHA=1.0 par défaut) |
| Lissage | Aucun | Smoothing de voisinage |
| Scores extrêmes | Clamping manuel | Clamping automatique (MAX_GOALS) |
| Probabilités | Parfois concentrées | Distribution plus réaliste |
| Calibrage | Fixe | Paramètres ajustables |

---

## ⚙️ Paramètres Calibrables

Ces paramètres sont définis dans `/app/backend/score_predictor.py` :

### 1. `MAX_GOALS` (défaut: 5)

**Définition :** Nombre maximum de buts par équipe pris en compte

```python
MAX_GOALS = 5  # clamp goals per side (0..5)
```

**Effet :**
- `MAX_GOALS = 5` : Considère les scores de 0-0 à 5-5
- `MAX_GOALS = 4` : Exclut les 5-X et X-5 (plus conservateur)
- `MAX_GOALS = 6` : Inclut les scores très élevés

**Quand augmenter :**
- Championnats offensifs (Bundesliga, Eredivisie)
- Matchs entre équipes faibles défensivement

**Quand diminuer :**
- Championnats défensifs (Serie A, Ligue 1)
- Matchs entre grandes équipes

---

### 2. `ALPHA` (défaut: 1.0)

**Définition :** Force de la gaussienne sur la différence de buts

```python
ALPHA = 1.0  # force de la gaussienne sur diff
```

**Formule :** `weight = exp(-ALPHA * (diff - diffExpected)²)`

**Effet :**
- `ALPHA = 0.4` (ancien) : Faible discrimination, distribution plate
- `ALPHA = 1.0` (défaut) : Discrimination forte, favorise scores proches de diffExpected
- `ALPHA = 1.5` : Discrimination très forte, pénalise fortement les écarts

**Impact sur les probabilités :**

| ALPHA | 2-0 (diff=2) | 3-1 (diff=2) | 4-0 (diff=4) | 1-1 (diff=0) |
|-------|-------------|-------------|-------------|-------------|
| 0.4   | 15%         | 14%         | 8%          | 12%         |
| 1.0   | 18%         | 17%         | 4%          | 10%         |
| 1.5   | 22%         | 20%         | 2%          | 8%          |

**Quand augmenter (ALPHA > 1.0) :**
✅ Les scores hauts (4-2, 3-3) sont trop probables
✅ Vous voulez plus de discrimination
✅ Vous avez un bon historique de diffExpected ajusté

**Quand diminuer (ALPHA < 1.0) :**
✅ Les favoris sont trop dominants
✅ La distribution est trop concentrée
✅ Vous voulez laisser plus de place aux surprises

---

### 3. `BLEND_BETA` (défaut: 0.7)

**Définition :** Poids relatif Poisson vs ImpliedOdds

```python
BLEND_BETA = 0.7  # 70% Poisson, 30% odds
```

**Formule :** `proba = BETA × Poisson + (1-BETA) × ImpliedOdds`

**Effet :**
- `BLEND_BETA = 0.0` : 100% ImpliedOdds (pure cote bookmaker)
- `BLEND_BETA = 0.5` : 50/50 Poisson et ImpliedOdds
- `BLEND_BETA = 0.7` (défaut) : 70% Poisson, 30% ImpliedOdds
- `BLEND_BETA = 1.0` : 100% Poisson (ignore les cotes)

**Impact typique :**

| Score | Pure Poisson (1.0) | Blend 0.7 | Pure Odds (0.0) |
|-------|-------------------|-----------|----------------|
| 1-1   | 12%               | 15%       | 18%            |
| 2-0   | 18%               | 16%       | 14%            |
| 0-0   | 8%                | 10%       | 12%            |
| 3-3   | 2%                | 3%        | 5%             |

**Quand augmenter (BETA > 0.7) :**
✅ Vous faites plus confiance au modèle Poisson qu'au bookmaker
✅ Les cotes du bookmaker semblent biaisées
✅ Vous avez de bonnes stats d'équipes

**Quand diminuer (BETA < 0.7) :**
✅ Vous faites plus confiance au marché qu'au modèle
✅ Les cotes reflètent des infos que vous n'avez pas (blessures, etc.)
✅ Vous voulez coller au consensus bookmaker

---

### 4. `EPS` (défaut: 1e-9)

**Définition :** Valeur epsilon pour éviter les divisions par zéro

```python
EPS = 1e-9  # lissage pour éviter 0
```

**Effet :** Technique, généralement pas besoin de modifier

---

## 🧮 Smoothing de Voisinage

L'algorithme applique un lissage automatique :

```python
# Distribution: 80% au score lui-même, 20% aux voisins
smoothed[score] += probability * 0.80
for neighbor in [(h+1,a), (h-1,a), (h,a+1), (h,a-1)]:
    smoothed[neighbor] += probability * 0.05
```

**Exemple concret :**

Avant smoothing :
- 2-1 : 20%
- 1-1 : 2%
- 3-1 : 3%
- 2-0 : 1%
- 2-2 : 1%

Après smoothing :
- 2-1 : 16% (80% de 20%)
- 1-1 : 3% (2% + 5% de 20%)
- 3-1 : 4% (3% + 5% de 20%)
- 2-0 : 2% (1% + 5% de 20%)
- 2-2 : 2% (1% + 5% de 20%)

**Bénéfice :** Évite les pics isolés irréalistes

---

## 🔧 Comment Régler les Paramètres

### Méthode recommandée : Tests A/B

1. **Préparez 10-20 images de test représentatives**
   - Matchs équilibrés (Équipe A ≈ Équipe B)
   - Matchs déséquilibrés (Favori clair)
   - Différents bookmakers

2. **Testez avec les paramètres par défaut**
   ```bash
   # Mode Test avec nouvel algorithme
   curl -X POST "http://localhost:8001/api/analyze" \
     -F "file=@test_image.jpg"
   ```

3. **Analysez les résultats**
   - Top 3 des scores fait sens ?
   - Distribution décroissante logique ?
   - Confiance cohérente avec l'incertitude réelle ?

4. **Ajustez UN paramètre à la fois**

---

## 📈 Scénarios de Réglage

### Scénario 1 : Scores hauts trop probables

**Symptôme :**
```
Top 3:
1. 4-2 : 15%
2. 3-3 : 14%
3. 4-3 : 12%
```

**Solution :**
```python
ALPHA = 1.5  # Augmenter pour pénaliser les écarts élevés
```

---

### Scénario 2 : Favoris trop dominants

**Symptôme :**
```
Top 3:
1. 2-0 : 45%
2. 1-0 : 30%
3. 3-0 : 15%
```

**Solution :**
```python
ALPHA = 0.7        # Diminuer discrimination
BLEND_BETA = 0.5   # Plus de poids aux cotes bookmaker
```

---

### Scénario 3 : Distribution trop plate

**Symptôme :**
```
Top 3:
1. 1-1 : 8%
2. 2-0 : 7.5%
3. 0-1 : 7.2%
... (tous les scores entre 5-10%)
```

**Solution :**
```python
ALPHA = 1.5        # Augmenter discrimination
BLEND_BETA = 0.8   # Plus de poids au Poisson
```

---

### Scénario 4 : Scores extrêmes non filtrés

**Symptôme :**
```
Top 3:
1. 2-1 : 15%
2. 6-5 : 12%  ← Irréaliste
3. 1-0 : 10%
```

**Solution :**
```python
MAX_GOALS = 4  # Réduire le clamp
```

---

## 🧪 Script de Test Rapide

Créez `/app/backend/test_params.py` :

```python
from score_predictor import predict_combined

# Scores de test
test_scores = {
    "0-0": 12.5, "1-0": 7.2, "0-1": 7.6,
    "1-1": 7.1, "2-0": 7.6, "0-2": 11.5,
    "2-1": 11.5, "1-2": 13.0, "2-2": 11.5,
    "3-0": 12.0, "0-3": 13.0, "3-1": 13.0,
    "1-3": 50.0, "3-2": 7.0, "2-3": 7.0
}

# Test avec différents paramètres
for alpha in [0.7, 1.0, 1.5]:
    for beta in [0.5, 0.7, 0.9]:
        print(f"\n=== ALPHA={alpha}, BETA={beta} ===")
        # Modifier temporairement les paramètres (ou dans le code)
        result = predict_combined(test_scores, diffExpected=2)
        print(f"Top 3: {result['probabilities'][:3]}")
        print(f"Confiance: {result['confidence']}")
```

---

## 📊 Comparaison Avant/Après

### Exemple réel : Match PSV vs Olympiakos

**Algorithme Classique :**
```
Top 3:
1. 1-1 : 24.3%
2. 2-0 : 18.7%
3. 0-1 : 16.4%

Confiance: 0.243
```

**Algorithme Combiné (défaut) :**
```
Top 3:
1. 2-1 : 17.8%
2. 1-0 : 15.2%
3. 2-0 : 14.6%

Confiance: 0.178
```

**Analyse :**
- Distribution plus réaliste (moins concentrée sur 1-1)
- Prise en compte des cotes bookmaker
- Smoothing évite les pics isolés

---

## 🎯 Recommandations Finales

### Pour commencer (Configuration par défaut)
```python
MAX_GOALS = 5
ALPHA = 1.0
BLEND_BETA = 0.7
```

### Pour matchs équilibrés
```python
MAX_GOALS = 4
ALPHA = 0.8
BLEND_BETA = 0.6
```

### Pour matchs déséquilibrés
```python
MAX_GOALS = 5
ALPHA = 1.2
BLEND_BETA = 0.7
```

### Pour coller au bookmaker
```python
MAX_GOALS = 5
ALPHA = 0.9
BLEND_BETA = 0.4  # 60% odds, 40% Poisson
```

---

## 🔄 Activation/Désactivation

### Depuis l'API

**Activer l'algorithme combiné (par défaut) :**
```bash
curl -X POST "http://localhost:8001/api/analyze" \
  -F "file=@image.jpg"
```

**Désactiver (utiliser l'algorithme classique) :**
```bash
curl -X POST "http://localhost:8001/api/analyze?use_combined_algo=false" \
  -F "file=@image.jpg"
```

### Depuis le Frontend

Vous pouvez ajouter un toggle dans `AnalyzePage.jsx` pour permettre à l'utilisateur de choisir.

---

## 📝 Logs pour Débogage

L'algorithme combiné génère des logs détaillés :

```bash
tail -f /var/log/supervisor/backend.out.log | grep -E "(COMBINÉ|Lambdas|ALPHA|BETA)"
```

Exemple de logs :
```
INFO: 🔬 NOUVEL ALGORITHME COMBINÉ - diffExpected=2, ALPHA=1.0, BLEND_BETA=0.7
INFO: 📊 Lambdas calculés depuis stats équipes: λ_home=1.8, λ_away=1.5
INFO: 🏆 Score le plus probable (combiné): 2-1 (17.82%)
INFO: 💯 Confiance: 17.8%
```

---

## 🚀 Prochaines Étapes

1. **Tester avec vos 10 images représentatives**
2. **Noter les cas où les résultats ne sont pas satisfaisants**
3. **Ajuster UN paramètre à la fois**
4. **Valider avec de nouvelles images**
5. **Répéter jusqu'à satisfaction**

---

*Document créé pour faciliter le réglage de l'algorithme combiné*  
*Version : 1.0 - Date : 2025-11-06*

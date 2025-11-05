# 🎯 Les 3 Systèmes d'Apprentissage Intégrés

## Vue d'Ensemble

Le système de prédiction utilise **3 mécanismes complémentaires** pour affiner ses calculs :

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTÈME COMPLET                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1️⃣ APPRENTISSAGE MANUEL (diffExpected)                    │
│     • 22 scores entrés manuellement via /api/learn         │
│     • Ajuste la différence de buts attendue                │
│     • Valeur actuelle: diffExpected = 1                    │
│     • Formule: 60/40 (réactivité moyenne)                  │
│                                                             │
│  ⬇️                                                          │
│                                                             │
│  2️⃣ SUIVI FORME ÉQUIPES (teams_data.json)                  │
│     • 5 derniers matchs par équipe conservés               │
│     • Calcul moyennes: buts pour/contre                    │
│     • Ajustement contextuel de diffExpected                │
│     • Actuel: 10 matchs (Ajax: 5, Galatasaray: 5)         │
│                                                             │
│  ⬇️                                                          │
│                                                             │
│  3️⃣ PONDÉRATION PAR COTES (odds weighting)                 │
│     • Lors de la lecture OCR des cotes                     │
│     • Ajuste les probabilités selon confiance bookmaker    │
│     • Cotes < 1.8: -15% (trop évident)                    │
│     • Cotes 4-8: +10% (value bet)                         │
│     • Cotes > 15: -20% (très peu probable)                │
│                                                             │
│  =  PRÉDICTION FINALE OPTIMISÉE                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ SYSTÈME 1 : Apprentissage Manuel (diffExpected)

### Objectif
Ajuster globalement l'écart de buts attendu en fonction des scores réels observés.

### Données Actuelles
- **Fichier**: `/app/backend/learning_data.json`
- **Contenu**: `{"diffExpected": 1}`
- **Historique**: 22 apprentissages effectués
- **Source**: Scores entrés manuellement via `/api/learn`

### Fonctionnement
```python
# Formule 60/40 (plus réactive)
new_diff = round((current * 3 + diff_real * 2) / 5)

# Exemple:
# Si diffExpected = 1 et score réel = 3-0 (diff = 3)
# new_diff = (1*3 + 3*2) / 5 = 9/5 = 1.8 → 2
```

### Impact
- Modifie le calcul de base des probabilités Poisson
- Plus le diffExpected est élevé, plus les scores avec écart sont favorisés
- Valeur 1 = matchs équilibrés attendus

---

## 2️⃣ SYSTÈME 2 : Suivi Forme Équipes

### Objectif
Ajuster les prédictions selon la forme récente des équipes spécifiques.

### Données Actuelles
- **Fichier**: `/app/data/teams_data.json`
- **Contenu**: 10 matchs (5 par équipe)
  - Ajax Amsterdam: moyenne 1.6 buts marqués, 0.8 encaissés
  - Galatasaray: moyenne 0.8 buts marqués, 1.6 encaissés

### Fonctionnement
```python
# Calcul des moyennes par équipe
avg_goals_for = sum(goals_for) / len(matches)
avg_goals_against = sum(goals_against) / len(matches)

# Ajustement contextuel de diffExpected
adj = ((home_for - away_against) - (away_for - home_against)) / 2
adjusted_diff = diff_expected + adj
```

### Exemple Concret
```
Ajax vs Galatasaray:
• Ajax (domicile): 1.6 marqués, 0.8 encaissés
• Galatasaray (ext): 0.8 marqués, 1.6 encaissés

Ajustement:
adj = ((1.6 - 1.6) - (0.8 - 0.8)) / 2 = 0.0
→ Pas d'ajustement (équipes équilibrées sur ces stats)
```

### Impact
- Personnalise diffExpected pour chaque match
- Favorise équipe en forme / pénalise équipe en difficulté
- Conserve seulement 5 derniers matchs (forme récente)

---

## 3️⃣ SYSTÈME 3 : Pondération par Cotes

### Objectif
Ajuster les probabilités finales selon la confiance du bookmaker.

### Fonctionnement
Lors de la lecture OCR des cotes, chaque score est pondéré :

| Plage Cote | Interprétation | Poids | Impact |
|------------|----------------|-------|--------|
| ≤ 1.8 | Trop évident | 0.85 | -15% |
| 1.8 - 4.0 | Normal | 1.00 | 0% |
| 4.0 - 8.0 | Value bet | 1.10 | +10% |
| 8.0 - 15.0 | Peu probable | 0.90 | -10% |
| > 15.0 | Extrême | 0.80 | -20% |

### Exemple Calcul
```python
# Score 2-0 avec cote 7.25
proba_base = 1 / 7.25 = 0.138 (13.8%)
poids = 1.10  # Car cote dans [4-8]
proba_ajustée = 0.138 × 1.10 = 0.152 (15.2%)

# Gain: +1.4 points de probabilité
```

### Impact
- Rééquilibre les probabilités après Poisson
- Exploite l'expertise du bookmaker
- Détecte les opportunités (value bets)

---

## 🔄 INTÉGRATION COMPLÈTE

### Flux de Calcul

```
1. IMAGE BOOKMAKER
   ↓
2. OCR EXTRACTION (ocr_engine.py)
   → Scores + Cotes extraits
   ↓
3. PONDÉRATION COTES (système 3)
   → adjust_score_weight_by_odds()
   → Probabilités de base ajustées
   ↓
4. ALGORITHME POISSON + CORRECTION NULS
   → calculate_probabilities()
   → Utilise diffExpected (système 1)
   ↓
5. AJUSTEMENT PAR ÉQUIPES (système 2)
   → adjust_diff_expected()
   → Personnalisation match-specific
   ↓
6. CALCUL CONFIANCE
   → calculate_confidence()
   → Score de fiabilité
   ↓
7. RÉSULTAT FINAL
   → Score le plus probable
   → Top 3 avec probabilités
   → Niveau de confiance
```

### Code d'Intégration (score_predictor.py)

```python
def calculate_probabilities(scores, diff_expected=2):
    """
    Calcul complet avec les 3 systèmes intégrés
    """
    
    # Système 3: Pondération par cotes (si activé)
    if use_odds_weighting:
        weighted_scores = process_scores_with_odds(scores)
    
    # Algorithme Poisson avec diffExpected
    # (Système 1: valeur ajustée par apprentissages manuels)
    probabilities = calculate_poisson_probs(scores, diff_expected)
    
    # Système 2: Ajustement par équipes (si noms fournis)
    if home_team and away_team:
        adjusted_diff = adjust_diff_expected(diff_expected, home_team, away_team)
        # Recalcul avec diffExpected ajusté
    
    # Calcul confiance + top 3
    confidence = calculate_confidence(probabilities)
    top3 = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        'mostProbableScore': top_score,
        'probabilities': probabilities,
        'confidence': confidence,
        'top3': top3
    }
```

---

## 📊 DONNÉES ACTUELLES

### Système 1: Apprentissage Manuel
```json
{
  "diffExpected": 1
}
```
- 22 apprentissages historiques
- Formule 60/40 active

### Système 2: Suivi Équipes
```json
{
  "Ajax Amsterdam": [[2,1], [3,0], [2,1], [1,0], [0,2]],
  "Galatasaray": [[1,2], [0,3], [1,2], [0,1], [2,0]]
}
```
- 10 matchs (5 par équipe)
- Moyennes calculées automatiquement

### Système 3: Pondération Cotes
- Intégré dans le code (pas de données statiques)
- Appliqué dynamiquement à chaque analyse

---

## ✅ RÉSUMÉ

| Système | Objectif | Données | Impact |
|---------|----------|---------|--------|
| **1. Apprentissage Manuel** | Ajuster diffExpected global | 22 scores manuels → `diffExpected=1` | Modifie base Poisson |
| **2. Suivi Forme** | Personnaliser par équipe | 10 matchs (5/équipe) | Ajuste diffExpected contextuel |
| **3. Pondération Cotes** | Intégrer expertise bookmaker | Appliqué à la volée | Rééquilibre probabilités |

**Résultat**: Prédictions multi-niveaux optimisées par 3 couches d'intelligence complémentaires.


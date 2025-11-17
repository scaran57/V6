# RÉSUMÉ COMPLET DU PROJET - SYSTÈME DE PRÉDICTION DE SCORES FOOTBALL

## 📋 APERÇU DU PROJET

**Nom**: Système de prédiction de scores de football (UFA - Unified Football Analyzer)

**Objectif**: Analyser des images de grilles de bookmakers (Winamax, Unibet, BetClic, FDJ) et prédire le score le plus probable d'un match en utilisant :
- Les cotes des bookmakers (extraction OCR)
- Les coefficients de force des équipes (basés sur classements de ligues)
- Un algorithme de Poisson adaptatif
- Un système d'apprentissage automatique

---

## 🧮 CALCULS ET ALGORITHMES

### 1. **EXTRACTION DES COTES (OCR)**

**Processus:**
```
Image bookmaker → Tesseract OCR → GPT-4 Vision (fallback) → Extraction des cotes
```

**Système multi-niveau:**
- Tesseract OCR (rapide, local)
- GPT-4 Vision API (fallback si Tesseract < 70% confiance)
- Parser avancé avec fuzzy-matching pour correction automatique

**Sortie:**
```json
{
  "scores": [
    {"home": 1, "away": 0, "cote": 6.5},
    {"home": 2, "away": 1, "cote": 8.0},
    ...
  ]
}
```

---

### 2. **CALCUL DES COEFFICIENTS DE FORCE DES ÉQUIPES**

**Formule de coefficient par position:**
```python
coeff = 0.85 + ((N - position) / (N - 1)) * 0.45
```

**Plage:** 0.85 (dernier) à 1.30 (premier)

**Exemple Ligue 1 (18 équipes):**
- PSG (1er) → coefficient = 1.30
- Marseille (2e) → coefficient = 1.276
- Auxerre (18e) → coefficient = 0.85

**Système de fallback intelligent pour compétitions européennes:**
- Champions League / Europa League : cherche d'abord le coefficient dans la ligue nationale
- Si équipe non trouvée → coefficient européen par défaut = 1.05
- Exemple: Real Madrid (CL) → 1.30 (depuis LaLiga), Galatasaray (CL) → 1.05 (fallback)

---

### 3. **CALCUL DES PROBABILITÉS (ALGORITHME PRINCIPAL)**

**Méthode: Distribution de Poisson adaptative**

#### Étape 1: Calcul des lambdas (espérance de buts)
```python
lambda_home = base_expected * coeff_home * (1 + diff_expected)
lambda_away = base_expected * coeff_away * (1 - diff_expected)
```

**Paramètres:**
- `base_expected` = 1.4 (moyenne de buts par équipe)
- `coeff_home` / `coeff_away` = coefficients de force (0.85-1.30)
- `diff_expected` = **2.1380** (ajusté par apprentissage)

#### Étape 2: Distribution de Poisson
```python
P(X=k) = (λ^k * e^-λ) / k!
```

Pour chaque score possible (0-0, 1-0, 1-1, etc.):
```python
prob_score = poisson(home_goals, lambda_home) * poisson(away_goals, lambda_away)
```

#### Étape 3: Correction adaptative des matchs nuls
```python
if home_goals == away_goals:
    if total_goals >= 6:  # 3-3, 4-4, etc.
        prob_score *= 0.25  # Réduction 75%
    elif total_goals == 4:  # 2-2
        prob_score *= 0.05  # Réduction 95%
    elif total_goals == 2:  # 1-1
        prob_score *= 0.50  # Réduction 50%
```

#### Étape 4: Pondération par les cotes bookmaker
```python
# Si le score existe dans les cotes extraites
weight = 1 / cote  # Plus la cote est basse, plus le poids est élevé
prob_finale = prob_poisson * (1 + weight * 0.3)
```

#### Étape 5: Normalisation
```python
# S'assurer que la somme des probabilités = 100%
for each score:
    prob_normalisée = (prob / somme_totale) * 100
```

---

### 4. **SYSTÈME D'APPRENTISSAGE AUTOMATIQUE**

**Endpoint:** `POST /api/learn`

**Paramètres:**
- `predicted`: Score prédit (ex: "2-1")
- `real`: Score réel (ex: "3-1")
- `home_team`: Équipe domicile
- `away_team`: Équipe extérieur

**Algorithme d'ajustement de diffExpected:**
```python
def adjust_diff_expected(predicted, real, current_diff):
    pred_home, pred_away = map(int, predicted.split('-'))
    real_home, real_away = map(int, real.split('-'))
    
    # Calculer l'écart de prédiction
    error_home = real_home - pred_home
    error_away = real_away - pred_away
    
    # Ajuster diffExpected
    if error_home > error_away:
        # L'équipe domicile a mieux performé
        new_diff = current_diff + 0.1
    elif error_away > error_home:
        # L'équipe extérieur a mieux performé
        new_diff = current_diff - 0.1
    else:
        # Performance équilibrée
        new_diff = current_diff * 0.95
    
    return new_diff
```

**Historique actuel:**
- Valeur initiale: 0.294
- Après 9 matchs appris: **2.1380**
- Changement: +1.844

---

## 🗂️ SYSTÈME DE MISE À JOUR DES LIGUES

### **Architecture Multi-Sources**

```
Scheduler quotidien (3h00)
    ↓
UnifiedUpdater (multi_source_updater.py)
    ↓
Tentative sources dans l'ordre:
    1. Football-Data.org API (2 clés en rotation)
    2. SoccerData/FBRef
    3. Scrapers personnalisés (Ligue 2, Europa League)
    4. DBfoot
    5. Cache local (toujours disponible)
```

---

### **CONFIGURATION PAR LIGUE**

#### **1. LaLiga (Espagne)**
- **Code API**: `PD`
- **Source primaire**: Football-Data.org
- **Équipes**: 20
- **Fallback**: SoccerData → Cache
- **Dernière mise à jour**: Via cache (< 24h)

#### **2. Premier League (Angleterre)**
- **Code API**: `PL`
- **Source primaire**: Football-Data.org
- **Équipes**: 20
- **Fallback**: SoccerData → Cache
- **Dernière mise à jour**: Via cache (< 24h)

#### **3. Serie A (Italie)**
- **Code API**: `SA`
- **Source primaire**: Football-Data.org
- **Équipes**: 20
- **Fallback**: SoccerData → Cache
- **Dernière mise à jour**: Via cache (< 24h)

#### **4. Bundesliga (Allemagne)**
- **Code API**: `BL1`
- **Source primaire**: Football-Data.org
- **Équipes**: 18
- **Fallback**: SoccerData → Cache
- **Dernière mise à jour**: Via cache (< 24h)

#### **5. Ligue 1 (France)**
- **Code API**: `FL1`
- **Source primaire**: Football-Data.org
- **Équipes**: 18
- **Fallback**: SoccerData → Cache
- **Dernière mise à jour**: Via cache (< 24h)

#### **6. Primeira Liga (Portugal)**
- **Code API**: `PPL`
- **Source primaire**: Football-Data.org
- **Équipes**: 18
- **Fallback**: SoccerData → Cache
- **Dernière mise à jour**: Via cache (< 24h)

#### **7. Ligue 2 (France) ⭐ NOUVEAU**
- **Code API**: `FL2`
- **Source primaire**: Football-Data.org (non disponible en tier gratuit)
- **Source secondaire**: **Scraper ligue1.com** (intégré)
- **Équipes**: 18
- **Fallback**: Cache local
- **Dernière mise à jour**: Via cache (< 24h)
- **Données actuelles**:
  - 1er: Troyes (28 pts, coeff 1.30)
  - 18e: Bastia (7 pts, coeff 0.85)

#### **8. Champions League**
- **Code API**: `CL`
- **Source primaire**: Football-Data.org
- **Équipes**: 36 (nouveau format)
- **Système de coefficient**: Fallback intelligent sur ligues nationales
- **Fallback**: Cache local
- **Dernière mise à jour**: Via cache (< 24h)
- **Exemple coefficients**:
  - Bayern Munich → 1.30 (depuis Bundesliga)
  - Real Madrid → 1.30 (depuis LaLiga)
  - Ajax → 1.05 (fallback européen)

#### **9. Europa League ⭐ NOUVEAU**
- **Code API**: `EL`
- **Source primaire**: Football-Data.org (non disponible en tier gratuit)
- **Source secondaire**: **Scraper uefa.com** (intégré)
- **Équipes**: 36 (nouveau format)
- **Système de coefficient**: Fallback intelligent sur ligues nationales
- **Fallback**: Cache local
- **Dernière mise à jour**: Via cache (< 24h)
- **Données actuelles**:
  - 1er: Midtjylland (12 pts)
  - 2e: SC Freiburg (10 pts, coeff depuis Bundesliga)
  - 36 équipes totales

#### **10. World Cup (Coupe du Monde)**
- **Code API**: `WC`
- **Source**: Cache statique
- **Équipes**: Variable selon phase
- **Fallback**: Cache local

#### **11. Copa Libertadores**
- **Code API**: `CLI`
- **Source**: Cache statique
- **Équipes**: Variable selon phase
- **Fallback**: Cache local

---

## 📊 RÉSUMÉ DES SOURCES DE DONNÉES

| Ligue | Source Active | Scraper Custom | API Gratuite | Cache |
|-------|---------------|----------------|--------------|-------|
| LaLiga | Football-Data.org | ❌ | ✅ | ✅ |
| Premier League | Football-Data.org | ❌ | ✅ | ✅ |
| Serie A | Football-Data.org | ❌ | ✅ | ✅ |
| Bundesliga | Football-Data.org | ❌ | ✅ | ✅ |
| Ligue 1 | Football-Data.org | ❌ | ✅ | ✅ |
| Primeira Liga | Football-Data.org | ❌ | ✅ | ✅ |
| **Ligue 2** | **Cache + Scraper** | **✅** | ❌ | ✅ |
| Champions League | Football-Data.org | ❌ | ✅ | ✅ |
| **Europa League** | **Cache + Scraper** | **✅** | ❌ | ✅ |
| World Cup | Cache statique | ❌ | ❌ | ✅ |
| Copa Libertadores | Cache statique | ❌ | ❌ | ✅ |

---

## ⏰ SCHEDULER AUTOMATIQUE

**Heure d'exécution:** 3h00 du matin (tous les jours)

**Processus:**
1. Lance `update_all_leagues()` depuis `league_unified.py`
2. Pour chaque ligue, appelle `UnifiedUpdater.update_league()`
3. Essaie les sources dans l'ordre de priorité
4. Sauvegarde les nouvelles données dans `/app/data/leagues/*.json`
5. Met à jour le cache multi-sources
6. Génère un rapport de mise à jour

**Fichiers générés:**
- `/app/data/leagues/{Ligue}.json` - Données de classement
- `/app/data/leagues/multi_source_cache.json` - Cache unifié
- `/app/data/leagues/last_unified_report.json` - Rapport de mise à jour
- `/app/logs/multi_source_updater.log` - Logs détaillés

---

## 🎯 FLUX COMPLET D'UNE ANALYSE

```
1. Utilisateur upload image bookmaker
   ↓
2. OCR extraction (Tesseract/GPT-4 Vision)
   → Extraction scores et cotes
   ↓
3. Parser avancé + Fuzzy matching
   → Détection équipes et ligue
   ↓
4. Récupération coefficients de force
   → Depuis fichiers JSON des ligues
   ↓
5. Calcul algorithme Poisson adaptatif
   → Application diffExpected (2.1380)
   → Correction matchs nuls
   → Pondération cotes bookmaker
   ↓
6. Normalisation probabilités
   → Somme = 100%
   ↓
7. Retour Top 3 scores les plus probables
   → Avec pourcentages
   ↓
8. (Optionnel) Apprentissage
   → /api/learn avec score réel
   → Ajustement diffExpected
```

---

## 📈 ÉTAT ACTUEL DU SYSTÈME

### Paramètres clés:
- **diffExpected**: 2.1380 (ajusté avec 9 matchs)
- **base_expected**: 1.4
- **Ligues actives**: 11
- **Cache fraîcheur**: < 24h
- **Scheduler**: Actif (3h00 quotidien)

### Performance récente:
- **9 matchs analysés** (Qualifications Coupe du Monde)
- **Précision**: 1/9 exact (11.1%)
- **Apprentissage**: +1.844 sur diffExpected
- **Amélioration attendue**: Oui, grâce à l'ajustement

### Fichiers de données:
```
/app/data/leagues/
├── LaLiga.json (20 équipes)
├── PremierLeague.json (20 équipes)
├── SerieA.json (20 équipes)
├── Bundesliga.json (18 équipes)
├── Ligue1.json (18 équipes)
├── PrimeiraLiga.json (18 équipes)
├── Ligue2.json (18 équipes) ⭐
├── ChampionsLeague.json (36 équipes)
├── EuropaLeague.json (36 équipes) ⭐
├── WorldCup.json
├── CopaLibertadores.json
└── multi_source_cache.json (cache unifié)
```

---

## 🔧 ENDPOINTS API PRINCIPAUX

### Analyse:
- `POST /api/analyze` - Analyse image bookmaker
- `POST /api/analyze?disable_cache=true` - Force nouveau calcul
- `POST /api/analyze?league=LaLiga` - Force une ligue spécifique
- `POST /api/analyze?enable_ocr_correction=true` - Active correction OCR

### Apprentissage:
- `POST /api/learn` - Entraîne le système (predicted, real, home_team, away_team)
- `GET /api/diff` - Récupère diffExpected actuel

### Administration ligues:
- `GET /api/admin/league/scheduler-status` - Statut du scheduler
- `POST /api/admin/league/trigger-update` - Force mise à jour manuelle
- `GET /api/admin/league/standings?league=LaLiga` - Classement d'une ligue
- `GET /api/league/team-coeff?team=PSG&league=Ligue1` - Coefficient d'une équipe

### Santé:
- `GET /api/health` - Vérification API

---

## 💾 STACK TECHNIQUE

- **Backend**: Python 3.9+ / FastAPI
- **Base de données**: MongoDB (analyses utilisateur)
- **OCR**: Tesseract + GPT-4 Vision
- **Scheduling**: APScheduler
- **Cache**: JSON local + MongoDB
- **Calculs**: NumPy, SciPy (Poisson)
- **Web scraping**: BeautifulSoup, Requests

---

## 🚀 PROCHAINES AMÉLIORATIONS

1. ✅ **Ligue 2 et Europa League intégrés** (FAIT)
2. ✅ **Système d'apprentissage automatique** (FAIT)
3. 🔄 **Surveillance des scrapers personnalisés**
4. 🔄 **Historique complet des analyses**
5. 🔄 **Dashboard de performance**
6. 🔄 **API d'export des prédictions**

---

**Date de mise à jour**: 16 novembre 2025
**Version**: 1.3
**diffExpected actuel**: 2.1380

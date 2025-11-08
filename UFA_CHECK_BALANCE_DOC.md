# 📊 UFA Check Balance v1.0 - Documentation

## Vue d'ensemble

Le module **UFA Check Balance** surveille en temps réel la cohérence et la qualité des données UFA, détecte les anomalies et génère des alertes.

## 🎯 Objectifs

1. **Surveiller le ratio Unknown** : Détecter si trop de matchs n'ont pas de ligue identifiée
2. **Analyser la diversité des scores** : Vérifier qu'il n'y a pas de sur-représentation d'un score
3. **Vérifier la distribution 1X2** : S'assurer que les résultats sont cohérents (domicile/nul/extérieur)
4. **Contrôler les moyennes par ligue** : Détecter les anomalies dans le nombre de buts

## 📁 Fichiers

### Module principal
- **Emplacement** : `/app/backend/ufa/ufa_check_balance.py`
- **Fonction principale** : `analyze_balance()`
- **Sortie** : Rapport JSON dans `/app/data/ufa_balance_report.json`

### Intégration
- **Scheduler** : `/app/backend/league_scheduler.py` (méthode `_run_balance_check()`)
- **API Endpoints** : 
  - `GET /api/ufa/balance` - Consulter le rapport
  - `POST /api/ufa/balance/run` - Lancer l'analyse manuellement

## 🔧 Configuration

### Seuils (THRESHOLDS)

```python
THRESHOLDS = {
    "unknown_max_ratio": 0.35,        # Max 35% de matchs Unknown
    "avg_goals_min": 2.0,             # Minimum de buts par match attendu
    "avg_goals_max": 3.3,             # Maximum de buts par match attendu
    "score_repeat_limit": 0.25,       # Max 25% du même score
    "min_matches_per_league": 3       # Minimum pour analyse fiable
}
```

## 📊 Analyses Effectuées

### 1. Ratio de Matchs Unknown

**Objectif** : Vérifier que la majorité des matchs ont une ligue identifiée.

**Seuil** : < 35% Unknown

**Alerte si** : > 35% de matchs sans ligue

**Action recommandée** :
- Enrichir la table de détection (`TEAM_LEAGUE_MAP`)
- Améliorer l'OCR pour capturer plus de noms d'équipes

**Exemple** :
```
Total Unknown: 66/79 matchs
Ratio: 83.5%
⚠️ Trop de matchs Unknown !
```

### 2. Diversité des Scores

**Objectif** : S'assurer qu'il n'y a pas de sur-représentation d'un score particulier.

**Seuil** : Aucun score ne doit représenter > 25% du total

**Alerte si** : Un même score apparaît trop souvent

**Action recommandée** :
- Vérifier les priors du système UFA
- Analyser si le modèle converge vers un score particulier

**Exemple** :
```
Score le plus fréquent: 1-1 (8 fois, 10.1%)
✅ Diversité des scores acceptable

Top 5:
  1-1 : 8 fois (10.1%)
  2-0 : 8 fois (10.1%)
  2-1 : 7 fois (8.9%)
```

### 3. Distribution 1X2

**Objectif** : Vérifier la cohérence des résultats (domicile/nul/extérieur).

**Distribution attendue** :
- Victoire domicile : ~45% (35-55%)
- Match nul : ~25% (15-35%)
- Victoire extérieur : ~30% (20-40%)

**Alerte si** : Distribution anormale

**Exemple** :
```
Victoire domicile (1): 36 matchs (45.6%)
Match nul (X):         22 matchs (27.8%)
Victoire extérieur (2): 21 matchs (26.6%)
✅ Distribution 1X2 cohérente
```

### 4. Moyenne de Buts par Ligue

**Objectif** : Détecter les anomalies dans le nombre moyen de buts.

**Seuils** :
- Minimum : 2.0 buts
- Maximum : 3.3 buts

**Statuts** :
- ✅ : Dans la plage normale
- ⚠️ : Trop bas ou trop élevé
- ℹ️ : Peu de données (< 3 matchs)

**Exemple** :
```
✅ Unknown         → 2.59 buts (σ=1.65, n=66)
✅ Eredivisie      → 2.40 buts (σ=0.89, n=5)
ℹ️ LaLiga          → 3.00 buts (σ=0.00, n=1)
   └─ Peu de données
```

## 🚀 Utilisation

### Exécution Manuelle

```bash
# Depuis le terminal
python3 /app/backend/ufa/ufa_check_balance.py
```

**Sortie** : Rapport détaillé dans le terminal + fichier JSON

### Via API

#### Consulter le dernier rapport

```bash
curl http://localhost:8001/api/ufa/balance
```

**Réponse** :
```json
{
  "success": true,
  "report": {
    "timestamp": "2025-11-08T23:29:26",
    "total_matches": 79,
    "unknown_ratio": 0.835,
    "alerts": ["Ratio Unknown trop élevé: 83.5%"],
    "league_stats": {...}
  }
}
```

#### Lancer une nouvelle analyse

```bash
curl -X POST http://localhost:8001/api/ufa/balance/run
```

**Réponse** :
```json
{
  "success": true,
  "message": "Vérification d'équilibre terminée",
  "report": {...}
}
```

### Intégration dans le Scheduler

L'analyse est **automatiquement exécutée** chaque nuit à 3h00 après :
1. Mise à jour des ligues
2. Validation des prédictions
3. Training UFA
4. **Vérification d'équilibre** ← Ajouté

**Logs dans** : `/var/log/supervisor/backend.out.log`

## 📄 Format du Rapport JSON

```json
{
  "timestamp": "2025-11-08T23:29:26.846929",
  "total_matches": 79,
  "unknown_ratio": 0.835,
  "top_score": {
    "score": "1-1",
    "frequency": 0.101
  },
  "results_distribution": {
    "home": 36,
    "draw": 22,
    "away": 21
  },
  "league_stats": {
    "LaLiga": {
      "avg_goals": 3.0,
      "std_dev": 0.0,
      "matches": 1,
      "status": "ℹ️"
    }
  },
  "alerts": [
    "Ratio Unknown trop élevé: 83.5%"
  ]
}
```

## ⚠️ Alertes Possibles

### Alerte 1 : Ratio Unknown Élevé

**Message** : `"Ratio Unknown trop élevé: X%"`

**Cause** :
- Beaucoup de matchs sans ligue identifiée
- OCR n'a pas capturé les noms d'équipes

**Solutions** :
1. Enrichir `TEAM_LEAGUE_MAP` dans `migrate_learning_phase1_to_ufa.py`
2. Améliorer l'OCR (`ocr_engine.py`)
3. Utiliser `/api/save-real-score` avec paramètre `league` explicite

### Alerte 2 : Score Trop Fréquent

**Message** : `"Score X-Y trop fréquent: Z%"`

**Cause** :
- Le modèle converge vers un score particulier
- Priors UFA mal calibrés

**Solutions** :
1. Vérifier `avg_goals` dans `/app/backend/ufa/training/state.json`
2. Ajuster manuellement les priors dans `ufa/analyzer.py`
3. Augmenter la diversité des données d'entraînement

### Alerte 3 : Moyenne Anormale

**Message** : Affiché dans les stats par ligue avec ⚠️

**Cause** :
- Ligue avec comportement atypique
- Données biaisées

**Solutions** :
1. Analyser les matchs de cette ligue spécifiquement
2. Vérifier si les scores réels sont corrects
3. Ajuster les priors spécifiques à cette ligue (fonctionnalité future)

## 📈 Interprétation des Résultats

### Bon État du Système

```
✅ Ratio Unknown: < 35%
✅ Diversité des scores: Aucun score > 25%
✅ Distribution 1X2: Cohérente (45%/25%/30%)
✅ Moyennes par ligue: Entre 2.0 et 3.3 buts
```

### État Nécessitant Attention

```
⚠️ Ratio Unknown: > 35%
→ Améliorer la détection de ligue

⚠️ Score 2-1: 30%
→ Modèle trop convergent

⚠️ SerieA: 1.5 buts (trop bas)
→ Vérifier les données ou ajuster priors
```

## 🔄 Évolution Future

### Améliorations Prévues

1. **Priors par ligue** : Ajuster automatiquement les priors selon chaque ligue
2. **Détection de dérive** : Comparer les prédictions avec les statistiques réelles des ligues
3. **Alertes par email** : Notification automatique en cas d'anomalie
4. **Dashboard web** : Interface graphique pour visualiser les rapports
5. **Historique des rapports** : Tracer l'évolution des métriques dans le temps

### Fréquence des Analyses

**Actuel** : Quotidienne (3h00)

**Recommandé selon le volume** :
- < 100 matchs : Hebdomadaire
- 100-500 matchs : Quotidienne
- > 500 matchs : Bi-quotidienne

## 💡 Bonnes Pratiques

1. **Consulter régulièrement** : Vérifier le rapport au moins une fois par semaine
2. **Agir sur les alertes** : Ne pas ignorer les anomalies répétées
3. **Documenter les changements** : Noter les ajustements de priors effectués
4. **Comparer avec réalité** : Vérifier que les moyennes correspondent aux statistiques réelles
5. **Enrichir progressivement** : Ajouter régulièrement des équipes dans TEAM_LEAGUE_MAP

## 📞 Support

En cas de questions ou d'anomalies :
1. Consulter `/app/data/ufa_balance_report.json`
2. Vérifier les logs : `/var/log/supervisor/backend.out.log`
3. Lancer une analyse manuelle pour debug
4. Consulter la documentation UFA complète

## ✅ Checklist de Maintenance

- [ ] Vérifier le rapport hebdomadairement
- [ ] Enrichir TEAM_LEAGUE_MAP mensuellement
- [ ] Ajuster les seuils si nécessaire
- [ ] Comparer avec statistiques réelles (Opta, WhoScored)
- [ ] Documenter les anomalies persistantes
- [ ] Archiver les rapports anciens (> 3 mois)

---

**Version** : 1.0
**Dernière mise à jour** : 2025-11-08
**Maintenu par** : Système UFA

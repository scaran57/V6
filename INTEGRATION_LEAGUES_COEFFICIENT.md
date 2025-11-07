# 🏆 Système de Coefficients de Ligue - Documentation Complète

## Vue d'ensemble

Le système de coefficients de ligue permet d'ajuster dynamiquement les prédictions de scores en fonction du classement des équipes dans leur ligue respective. Plus une équipe est bien classée, plus son coefficient est élevé, ce qui influence positivement les probabilités de victoire.

## Architecture du Système

### 1. Modules Backend

#### `league_fetcher.py`
- **Rôle**: Récupération automatique des classements depuis Wikipedia
- **Fonctionnalités**:
  - Scraping des classements pour 8 ligues
  - Cache local avec TTL de 24h
  - Sauvegarde dans `/app/data/leagues/*.json`
  - Fallback sur cache en cas d'erreur réseau

#### `league_coeff.py`
- **Rôle**: Calcul des coefficients d'équipe
- **Formule linéaire**: `coeff = 0.85 + ((N - pos) / (N - 1)) * 0.45`
- **Plage**: 0.85 (dernier) à 1.30 (premier)
- **Fallback intelligent**:
  - Compétitions européennes → cherche dans ligues nationales
  - Équipe non trouvée → bonus européen 1.05

#### `league_updater.py`
- **Rôle**: Orchestration des mises à jour
- **Fonctionnalités**:
  - Mise à jour séquentielle de toutes les ligues
  - Gestion des erreurs par ligue
  - Vidage du cache des coefficients après mise à jour

#### `league_scheduler.py`
- **Rôle**: Planificateur automatique quotidien
- **Fonctionnalités**:
  - Thread d'arrière-plan (daemon)
  - Mise à jour quotidienne à 3h00
  - Mise à jour initiale au démarrage si nécessaire
  - API pour déclencher des mises à jour manuelles

## Ligues Supportées

### Ligues Nationales (6)
1. **LaLiga** (Espagne) - 20 équipes
2. **PremierLeague** (Angleterre) - 20 équipes
3. **SerieA** (Italie) - En cours d'implémentation
4. **Ligue1** (France) - En cours d'implémentation
5. **Bundesliga** (Allemagne) - En cours d'implémentation
6. **PrimeiraLiga** (Portugal) - En cours d'implémentation

### Compétitions Européennes (2)
7. **ChampionsLeague** - 36 équipes (nouveau format)
8. **EuropaLeague** - 36 équipes (nouveau format)

## Système de Fallback Intelligent

### Pour les Ligues Nationales
```
Équipe spécifiée → Cherche dans la ligue → Coefficient calculé
                                         → Si non trouvée: 1.0 (neutre)
```

### Pour les Compétitions Européennes
```
Équipe spécifiée → Cherche dans toutes les ligues nationales
                → Trouvée: Utilise coefficient de la ligue nationale
                → Non trouvée: Applique bonus européen (1.05)
```

### Exemples

#### Équipes dans Ligues Nationales
- **Real Madrid** (Champions League)
  - Cherche dans: LaLiga, PremierLeague, SerieA, Ligue1, Bundesliga, PrimeiraLiga
  - Trouvé dans: LaLiga (position 1)
  - Coefficient: **1.300** (source: LaLiga)

- **Liverpool** (Champions League)
  - Trouvé dans: PremierLeague (position 2)
  - Coefficient: **1.276** (source: PremierLeague)

#### Équipes Étrangères (Bonus Européen)
- **Galatasaray** (Champions League)
  - Non trouvé dans ligues nationales
  - Coefficient: **1.05** (source: european_fallback)

- **Red Star Belgrade** (Champions League)
  - Non trouvé dans ligues nationales
  - Coefficient: **1.05** (source: european_fallback)

## Intégration dans les Prédictions

### Dans `score_predictor.py`

Le coefficient de ligue est appliqué lors du calcul des probabilités:

```python
# Appliquer les coefficients de ligue
if league_coeffs_applied:
    if home > away:
        # Victoire domicile : appliquer home_coeff
        league_weight = home_coeff / ((home_coeff + away_coeff) / 2)
    elif away > home:
        # Victoire extérieur : appliquer away_coeff
        league_weight = away_coeff / ((home_coeff + away_coeff) / 2)
    else:
        # Nul : moyenne des deux
        league_weight = (home_coeff + away_coeff) / 2

weighted[score] = p * weight * league_weight
```

### Impact sur les Probabilités

#### Exemple: Real Madrid (1.30) vs Granada (0.85)
- Les scores avec victoire de Real Madrid sont **favorisés**
- Les scores avec victoire de Granada sont **pénalisés**
- Les nuls sont ajustés selon la moyenne des coefficients

#### Exemple: Galatasaray (1.05) vs Red Star Belgrade (1.05)
- Coefficients équilibrés (bonus européen égal)
- Prédictions neutres sans biais de ligue

## API Endpoints

### Administration des Ligues

#### Liste des ligues disponibles
```bash
GET /api/admin/league/list
Response: {
  "success": true,
  "leagues": ["LaLiga", "PremierLeague", ..., "ChampionsLeague", "EuropaLeague"]
}
```

#### Récupérer un classement
```bash
GET /api/admin/league/standings?league=LaLiga
Response: {
  "success": true,
  "league": "LaLiga",
  "teams_count": 20,
  "standings": [
    {"team": "Real Madrid", "position": 1},
    ...
  ]
}
```

#### Mettre à jour une ligue
```bash
POST /api/admin/league/update?league=LaLiga&force=true
Response: {
  "success": true,
  "league": "LaLiga",
  "teams_count": 20,
  "message": "Classement LaLiga mis à jour avec succès"
}
```

#### Mettre à jour toutes les ligues
```bash
POST /api/admin/league/update-all?force=false
Response: {
  "success": true,
  "updated": {
    "LaLiga": 20,
    "PremierLeague": 20,
    ...
  }
}
```

#### Déclencher une mise à jour manuelle
```bash
POST /api/admin/league/trigger-update
Response: {
  "success": true,
  "message": "Mise à jour manuelle déclenchée en arrière-plan"
}
```

### Coefficient d'Équipe

#### Obtenir le coefficient d'une équipe
```bash
GET /api/league/team-coeff?team=Real%20Madrid&league=ChampionsLeague&mode=linear
Response: {
  "success": true,
  "team": "Real Madrid",
  "league": "ChampionsLeague",
  "position": 1,
  "coefficient": 1.300,
  "source": "LaLiga",
  "mode": "linear",
  "note": "Source indique d'où provient le coefficient"
}
```

### Statut du Scheduler

```bash
GET /api/admin/league/scheduler-status
Response: {
  "success": true,
  "scheduler": {
    "is_running": true,
    "update_time": "03:00",
    "last_update": "2025-11-07T03:00:00",
    "next_update": "2025-11-08T03:00:00"
  }
}
```

### Intégration dans `/api/analyze`

#### Avec ligue spécifiée
```bash
POST /api/analyze?league=LaLiga
FormData: file=@image.jpg

Response: {
  "success": true,
  "league": "LaLiga",
  "leagueCoeffsApplied": true,
  "mostProbableScore": "2-1",
  ...
}
```

#### Désactiver les coefficients
```bash
POST /api/analyze?disable_league_coeff=true
FormData: file=@image.jpg

Response: {
  "success": true,
  "leagueCoeffsApplied": false,
  ...
}
```

## Auto-détection de Ligue

Le système peut détecter automatiquement la ligue/compétition:

### Par Bookmaker
- Si bookmaker contient "Champions" ou "UCL" → Champions League
- Si bookmaker contient "Europa" ou "UEL" → Europa League

### Par Équipes
- Équipes espagnoles → LaLiga
- Équipes anglaises → PremierLeague
- (Extensible pour autres ligues)

## Cache et Performance

### Cache des Classements
- **Localisation**: `/app/data/leagues/*.json`
- **TTL**: 24 heures
- **Format**:
```json
{
  "league": "LaLiga",
  "updated": "2025-11-07T00:00:00Z",
  "teams": [
    {"name": "Real Madrid", "rank": 1, "points": 33},
    ...
  ]
}
```

### Cache des Coefficients
- **Localisation**: `/app/data/leagues/coeff_cache.json`
- **Clé**: `{league}:{team_name}`
- **Vidage**: Automatique après mise à jour des classements

## Maintenance

### Vérifier les fichiers de données
```bash
ls -la /app/data/leagues/
# LaLiga.json, PremierLeague.json, ChampionsLeague.json, EuropaLeague.json, etc.
```

### Vider le cache des coefficients
```bash
POST /api/admin/league/clear-cache
```

### Forcer une mise à jour immédiate
```bash
POST /api/admin/league/trigger-update
```

### Logs du Scheduler
```bash
tail -f /var/log/supervisor/backend.*.log | grep -E "(League|Scheduler|Coefficient)"
```

## Tests de Validation

### Test 1: Ligues Disponibles
```bash
curl https://matchpredictor-31.preview.emergentagent.com/api/admin/league/list
# Attendu: 8 ligues
```

### Test 2: Coefficient avec Fallback
```bash
curl "https://matchpredictor-31.preview.emergentagent.com/api/league/team-coeff?team=Real%20Madrid&league=ChampionsLeague"
# Attendu: coefficient ~1.30, source: LaLiga
```

### Test 3: Bonus Européen
```bash
curl "https://matchpredictor-31.preview.emergentagent.com/api/league/team-coeff?team=Galatasaray&league=ChampionsLeague"
# Attendu: coefficient 1.05, source: european_fallback
```

## Évolutions Futures

### Phase 3 (À venir)
1. Implémenter les parsers pour:
   - SerieA
   - Ligue1
   - Bundesliga
   - PrimeiraLiga

2. Améliorer le scraping Champions/Europa League:
   - Parser les classements de phase de ligue
   - Utiliser les coefficients UEFA

3. Interface Frontend:
   - Toggle pour activer/désactiver coefficients
   - Dropdown pour sélectionner la ligue
   - Affichage des coefficients dans les résultats

4. Statistiques avancées:
   - Historique des coefficients
   - Impact des coefficients sur les prédictions
   - Analyse de performance

## Dépannage

### Problème: Équipe non trouvée
**Solution**: Vérifier l'orthographe, utiliser le nom complet, vérifier le fichier de données de la ligue

### Problème: Scheduler ne se lance pas
**Solution**: Vérifier les logs backend, redémarrer le service
```bash
sudo supervisorctl restart backend
```

### Problème: Classements obsolètes
**Solution**: Forcer une mise à jour manuelle
```bash
POST /api/admin/league/trigger-update
```

---

**Date de création**: 7 novembre 2025  
**Version**: 2.0  
**Auteur**: AI Engineer (Emergent)  
**Status**: ✅ Opérationnel

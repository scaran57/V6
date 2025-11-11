# 🎯 Guide d'Utilisation - Analyses avec Coefficients de Ligue

## 📊 État Actuel de Vos Analyses

D'après votre rapport, vous avez effectué :
- **15 analyses en mode "Analyzer UEFA"**
- **3 analyses en mode "Production"**

⚠️ **Problème détecté** : Le système de cache est actuellement vide, ce qui signifie que les analyses n'ont pas été sauvegardées.

## 🔍 Pourquoi le cache est vide ?

### Causes possibles :
1. **Cache désactivé** : Le paramètre `disable_cache=true` était actif
2. **Erreurs OCR** : Les images n'ont pas pu être analysées correctement
3. **Nettoyage récent** : Le cache a été vidé manuellement
4. **Rechargement de page** : Analyses faites sans sauvegarde

## ✅ Comment Faire des Analyses avec Coefficients de Ligue

### 📍 Où Uploader vos Images ?

#### Option 1 : Mode Production (Recommandé)
```
URL: https://aiscore-oracle.preview.emergentagent.com/
```

**Étapes :**
1. Cliquez sur le bouton **"Mode Production"** (bleu, en haut)
2. Cliquez sur **"Choisir une image"**
3. Sélectionnez votre image de bookmaker
4. *(Optionnel)* Entrez le nom du match si l'OCR échoue
5. Cliquez sur **"Analyser & Prédire"**

**Avantages :**
- ✅ Interface simple et rapide
- ✅ Coefficients appliqués automatiquement
- ✅ Résultats mis en cache (consultables ultérieurement)
- ✅ Détection automatique de la ligue

#### Option 2 : Analyzer UEFA (Pour analyses détaillées)
```
URL: https://aiscore-oracle.preview.emergentagent.com/
Cliquez sur "Analyzer UEFA" (orange)
```

**Étapes :**
1. Cliquez sur **"Analyzer UEFA"** en haut à droite
2. Uploadez votre image
3. Consultez les coefficients de ligue dans l'interface
4. Voyez l'impact des coefficients sur les prédictions

**Avantages :**
- ✅ Vue détaillée des coefficients
- ✅ Statistiques par ligue
- ✅ Validation du système de coefficients
- ✅ Interface d'analyse approfondie

#### Option 3 : Mode Test (Pour debugging)
```
URL: https://aiscore-oracle.preview.emergentagent.com/
Cliquez sur "Mode Test" (vert)
```

**Étapes :**
1. Cliquez sur **"Mode Test"**
2. Uploadez votre image
3. **Décochez** "Désactiver le cache" si vous voulez sauvegarder
4. Voyez les informations techniques détaillées

**Avantages :**
- ✅ Contrôle du cache
- ✅ Métadonnées techniques visibles
- ✅ Logs de debugging
- ✅ Badge indiquant si résultat vient du cache

## 🎨 Formats d'Images Acceptés

### ✅ Formats supportés :
- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **WebP** (.webp)

### 📏 Qualité recommandée :
- **Résolution** : Minimum 800x600 pixels
- **Taille** : Maximum 10 MB
- **Lisibilité** : Texte net et contrasté

### 📸 Types d'images fonctionnelles :
- ✅ Screenshots de bookmakers (Unibet, Winamax, BetClic, etc.)
- ✅ Photos de grilles de paris
- ✅ Captures d'écran mobiles
- ✅ Images avec scores et cotes visibles

### ❌ À éviter :
- ❌ Images floues ou de mauvaise qualité
- ❌ Images trop sombres ou surexposées
- ❌ Captures partielles (scores coupés)
- ❌ Images avec trop de reflets

## 🔧 Comment Vérifier que les Coefficients sont Appliqués ?

### 1. Via l'API (Backend)
```bash
# Tester avec une image
curl -X POST https://aiscore-oracle.preview.emergentagent.com/api/analyze \
  -F "file=@votre_image.jpg" \
  | jq '.leagueCoeffsApplied, .league, .matchName'
```

**Résultat attendu :**
```json
{
  "leagueCoeffsApplied": true,
  "league": "LaLiga",
  "matchName": "Real Madrid - Barcelona"
}
```

### 2. Via l'Interface Web

**Mode Production :**
- Les coefficients sont appliqués automatiquement en arrière-plan
- Vous voyez directement les scores les plus probables ajustés

**Analyzer UEFA :**
- Affiche explicitement les coefficients de chaque équipe
- Montre l'impact sur les probabilités
- Interface dédiée à la visualisation des coefficients

**Mode Test :**
- Section "Informations Techniques" → cherchez `leagueCoeffsApplied: true`
- Détails complets dans les métadonnées JSON

### 3. Via les Logs Backend
```bash
tail -f /var/log/supervisor/backend.err.log
```

**Cherchez ces lignes lors de l'analyse :**
```
✅ Équipes détectées: Real Madrid vs Barcelona
✅ Ligue détectée: LaLiga
🧮 Calcul des probabilités avec... league=LaLiga, use_league_coeff=True...
```

## 📂 Où sont Stockées les Analyses ?

### Cache des Analyses
```
Fichier: /app/data/matches_memory.json
Format: JSON
Contenu: Tous les matchs analysés avec leurs prédictions
```

**Pour consulter le cache :**
```bash
cat /app/data/matches_memory.json | jq '.'
```

**Pour compter les analyses :**
```bash
cat /app/data/matches_memory.json | jq 'length'
```

### Scores Réels (Pour Training)
```
Fichier: /app/data/real_scores.jsonl
Format: JSONL (une ligne par match)
Contenu: Scores réels pour l'entraînement UFA
```

**Pour voir les derniers scores :**
```bash
tail -10 /app/data/real_scores.jsonl
```

## 🚀 Workflow Recommandé pour Vos Analyses

### Scénario 1 : Analyse Rapide (Mode Production)
```
1. Ouvrir https://aiscore-oracle.preview.emergentagent.com/
2. Cliquer sur "Mode Production"
3. Uploader l'image du bookmaker
4. Voir immédiatement le Top 3 des scores
5. Les coefficients sont appliqués automatiquement ✅
```

### Scénario 2 : Analyse Approfondie (Analyzer UEFA)
```
1. Cliquer sur "Analyzer UEFA"
2. Uploader l'image
3. Consulter :
   - Coefficients des équipes
   - Impact sur les probabilités
   - Statistiques de la ligue
4. Valider que les coefficients sont corrects
```

### Scénario 3 : Debugging (Mode Test)
```
1. Cliquer sur "Mode Test"
2. Uploader l'image
3. Décocher "Désactiver le cache" (pour sauvegarder)
4. Analyser les métadonnées techniques
5. Vérifier leagueCoeffsApplied: true
```

## 🎯 Exemples Concrets

### Exemple 1 : Match LaLiga
```
Image: Real Madrid vs Barcelona
Attendu:
  - home_team: "real madrid"
  - away_team: "barcelona"
  - league: "LaLiga"
  - leagueCoeffsApplied: true
  - home_coeff: 1.30 (1ère place)
  - away_coeff: 1.25 (3ème place)
```

### Exemple 2 : Match Premier League
```
Image: Manchester City vs Liverpool
Attendu:
  - home_team: "manchester city"
  - away_team: "liverpool"
  - league: "PremierLeague"
  - leagueCoeffsApplied: true
  - home_coeff: 1.30
  - away_coeff: 1.28
```

### Exemple 3 : Match Ligue 1
```
Image: PSG vs Marseille
Attendu:
  - home_team: "psg"
  - away_team: "olympique de marseille"
  - league: "Ligue1"
  - leagueCoeffsApplied: true
  - home_coeff: ~1.25
  - away_coeff: ~1.15
```

## ❓ FAQ - Questions Fréquentes

### Q1 : Mes analyses ne sont pas sauvegardées, pourquoi ?
**R:** Vérifiez que le cache n'est pas désactivé. En Mode Test, décochez "Désactiver le cache".

### Q2 : Comment savoir si les coefficients sont appliqués ?
**R:** 
- Mode Production : Toujours appliqués automatiquement
- Analyzer UEFA : Affichés explicitement
- Mode Test : Vérifiez `leagueCoeffsApplied: true` dans les métadonnées

### Q3 : Les équipes ne sont pas détectées, que faire ?
**R:** 
1. Vérifiez la qualité de l'image (nette, contrastée)
2. Entrez manuellement le nom du match dans le champ "Nom du match"
3. Utilisez le format : "Équipe1 - Équipe2"

### Q4 : La ligue détectée est "Unknown", pourquoi ?
**R:** 
- Les équipes ne sont pas dans la base team_map.json (133 équipes)
- Solution : Entrez manuellement le nom correct des équipes connues
- Le système fera un fuzzy matching automatique

### Q5 : Où sont mes 15+3 analyses ?
**R:** 
- Si le cache était désactivé → Analyses non sauvegardées
- Si erreurs OCR → Analyses échouées (pas de sauvegarde)
- Solution : Refaire les analyses avec cache activé

### Q6 : Comment vider le cache ?
**R:** 
- Mode Test : Bouton "Vider le Cache"
- API : `DELETE /api/admin/clear-analysis-cache`
- Manuel : Supprimer `/app/data/matches_memory.json`

## 🔧 Troubleshooting

### Problème : "Aucune cote détectée dans l'image"
**Solutions :**
1. Vérifier la qualité de l'image
2. S'assurer que les scores sont visibles
3. Essayer avec une autre image du même match
4. Vérifier que l'image n'est pas trop sombre/claire

### Problème : "Match non détecté"
**Solutions :**
1. Entrer manuellement le nom dans "Nom du match (optionnel)"
2. Format : "Real Madrid - Barcelona"
3. Vérifier l'orthographe des équipes
4. Utiliser des noms standards (ex: "PSG" plutôt que "Paris Saint-Germain")

### Problème : Coefficients non appliqués (leagueCoeffsApplied: false)
**Causes :**
1. Équipes non détectées → Entrez manuellement
2. Ligue = "Unknown" → Équipes inconnues
3. Cache désactivé → Réanalyser avec cache activé

**Solution :**
```
1. Mode Test → Upload image
2. Vérifier leagueCoeffsApplied dans les métadonnées
3. Si false → Vérifier matchName et league
4. Réanalyser si nécessaire
```

## 📊 Dashboard de Monitoring (À venir)

Pour suivre vos analyses en temps réel :

```bash
# Nombre total d'analyses
cat /app/data/matches_memory.json | jq 'length'

# Dernières analyses
cat /app/data/matches_memory.json | jq '.[] | {match: .match_name, score: .top3[0].score, league: .league}'

# Analyses par ligue
cat /app/data/matches_memory.json | jq -r '.[] | .league' | sort | uniq -c
```

## 🎓 Bonnes Pratiques

### ✅ À Faire :
1. **Toujours utiliser des images nettes et lisibles**
2. **Vérifier la détection dans Mode Test avant production**
3. **Garder le cache activé pour historiser les analyses**
4. **Utiliser Analyzer UEFA pour valider les coefficients**
5. **Entrer manuellement le nom si OCR échoue**

### ❌ À Éviter :
1. **Ne pas uploader d'images floues**
2. **Ne pas désactiver le cache sans raison**
3. **Ne pas ignorer les messages d'erreur OCR**
4. **Ne pas oublier de vérifier leagueCoeffsApplied**
5. **Ne pas utiliser des noms d'équipes fantaisistes**

## 🚀 Actions Immédiates Recommandées

### Pour vérifier vos 18 analyses :

1. **Vérifier le cache :**
```bash
cat /app/data/matches_memory.json | jq 'length'
```
Si = 0 → Analyses non sauvegardées

2. **Vérifier les logs :**
```bash
grep "POST /api/analyze" /var/log/supervisor/backend.err.log | wc -l
```
Devrait montrer ~18 lignes si analyses faites

3. **Refaire une analyse test :**
- Mode Production → Upload une image test
- Vérifier que le résultat s'affiche
- Revérifier le cache

4. **Pour retrouver vos images :**
```bash
ls -lht /app/backend/uploads/ 2>/dev/null
ls -lht /app/uploads/ 2>/dev/null
```

## 📞 Support

Si problème persiste :
1. Fournir une capture d'écran de l'interface
2. Partager les logs : `tail -50 /var/log/supervisor/backend.err.log`
3. Indiquer le mode utilisé (Production/Test/UEFA)
4. Décrire l'image uploadée (bookmaker, type de match)

---

**🎯 Résumé : Pour bénéficier des analyses avec coefficients actifs, utilisez le Mode Production ou Analyzer UEFA et assurez-vous que le cache est activé !**

# 📚 Documentation - Application de Prédiction de Scores

## 🎯 Vue d'ensemble

Cette application permet d'analyser des images de bookmakers et de prédire les scores les plus probables d'un match en utilisant :
- **OCR avancé** (extraction des cotes depuis les images)
- **Algorithme de prédiction** (Poisson weighting, adaptive draw correction)
- **Apprentissage adaptatif** (ajustement automatique du paramètre `diffExpected`)
- **Système de cache** (mémorisation des analyses pour optimiser les performances)

---

## 🚀 Modes de fonctionnement

L'application propose **deux modes d'utilisation** accessibles via la barre de navigation en haut de la page :

### 1️⃣ Mode Production 🎯

**Utilisation recommandée :** Utilisation quotidienne normale

**Caractéristiques :**
- Interface utilisateur standard optimisée
- Cache d'analyse activé automatiquement
- Analyse rapide grâce à la mémorisation des résultats précédents
- Expérience utilisateur fluide et performante

**Quand l'utiliser :**
- Pour l'utilisation normale de l'application
- Lorsque vous souhaitez des réponses rapides
- Quand vous analysez plusieurs fois la même image

**Fonctionnalités disponibles :**
- Upload d'image de bookmaker
- Affichage du score prédit le plus probable
- Affichage du Top 3 des scores
- Informations sur le match et le bookmaker
- Niveau de confiance de la prédiction

---

### 2️⃣ Mode Test 🧪

**Utilisation recommandée :** Tests, débogage, et validation des calculs

**Caractéristiques :**
- Interface avec contrôles avancés du cache
- Possibilité de désactiver le cache pour forcer un nouveau calcul
- Badge indiquant si le résultat provient du cache ou d'un nouveau calcul
- Bouton pour vider complètement le cache des analyses
- Informations techniques détaillées (Match ID, timestamp, etc.)

**Quand l'utiliser :**
- Pour tester l'algorithme de prédiction avec différents paramètres
- Lorsque vous voulez forcer un nouveau calcul OCR complet
- Pour vérifier si les résultats sont cohérents
- Pour le débogage et la validation des fonctionnalités
- Après avoir modifié l'algorithme de prédiction ou les paramètres d'apprentissage

**Fonctionnalités supplémentaires :**
- ✅ Toutes les fonctionnalités du Mode Production
- 🔄 **Switch "Mode Test"** : Désactive temporairement le cache pour cette analyse
- 🧹 **Bouton "Vider le cache"** : Supprime toutes les analyses mémorisées
- 📊 **Badges de source** : Indique si le résultat vient du cache ou d'un nouveau calcul
- 🔧 **Informations techniques** : Match ID, timestamp d'analyse, etc.

---

## 🧰 Contrôles du Cache (Mode Test uniquement)

### Qu'est-ce que le cache d'analyse ?

Le cache d'analyse est un système de mémorisation qui stocke les résultats d'analyse pour chaque image unique. Lorsqu'une image est analysée :
1. Un identifiant unique (hash MD5) est calculé à partir de l'image
2. Le résultat de l'analyse (OCR + prédiction) est sauvegardé dans `/app/backend/data/matches_memory.json`
3. Si la même image est re-soumise, le résultat est récupéré directement du cache

**Avantages du cache :**
- ⚡ Réponses quasi-instantanées pour les images déjà analysées
- 💰 Économie de ressources de calcul (OCR et algorithmes de prédiction coûteux)
- 🎯 Cohérence des résultats pour une même image

### Switch "Mode Test" (Désactiver le cache)

**Fonction :** Force un nouveau calcul complet en ignorant le cache

**Comment l'utiliser :**
1. Dans le Mode Test, cochez la case "Mode Test : Recalculer entièrement (désactiver le cache)"
2. Uploadez votre image
3. Cliquez sur "🎯 Analyser"

**Quand désactiver le cache :**
- ✅ Vous avez modifié l'algorithme de prédiction
- ✅ Vous avez ajusté le paramètre `diffExpected`
- ✅ Vous voulez vérifier si l'OCR fonctionne correctement
- ✅ Vous testez différentes versions de l'algorithme
- ✅ Vous souhaitez voir les logs de calcul complets dans le backend

**Indicateurs visuels :**
- Badge **"Nouveau calcul complet"** (vert) : L'analyse a été recalculée
- Badge **"Cache désactivé"** (jaune) : Le cache a été désactivé pour cette requête

### Bouton "Vider le cache"

**Fonction :** Supprime toutes les analyses mémorisées

**Comment l'utiliser :**
1. Dans le Mode Test, cliquez sur le bouton "🧹 Vider le cache"
2. Confirmez l'action dans la boîte de dialogue

**Quand vider le cache :**
- ✅ Après une mise à jour majeure de l'algorithme de prédiction
- ✅ Lorsque le cache contient trop d'analyses obsolètes
- ✅ Pour libérer de l'espace disque
- ✅ Avant de faire des tests de performance complets
- ✅ Si vous soupçonnez que le cache contient des données corrompues

**⚠️ Attention :** Cette action est irréversible. Toutes les analyses devront être recalculées.

---

## 🏗️ Architecture Technique

### Frontend (React)

```
/app/frontend/src/
├── index.js              # Point d'entrée - Monte AppRouter
├── AppRouter.js          # Routeur principal avec navigation entre modes
├── TestMode.js           # Wrapper pour le mode test avec bandeau d'info
├── App.js                # Application principale (Mode Production)
├── components/
│   └── AnalyzePage.jsx   # Page d'analyse avec contrôles de cache
```

**Navigation entre les modes :**
- Gérée par un state local dans `AppRouter.js`
- Basculement via deux boutons dans la navbar
- Pas de rechargement de page (SPA - Single Page Application)

### Backend (FastAPI)

```
/app/backend/app/
├── server.py                    # API REST avec endpoints
├── ocr_engine.py                # Extraction OCR des cotes et infos
├── score_predictor.py           # Algorithme de prédiction
├── learning.py                  # Système d'apprentissage adaptatif
├── modules/
│   └── local_learning_safe.py   # Système sécurisé d'apprentissage
├── data/
│   ├── teams_data.json          # Données historiques des équipes
│   ├── matches_memory.json      # Cache des analyses
│   ├── learning_events.jsonl    # Log append-only des événements
│   └── learning_meta.json       # Métadonnées (diffExpected, version)
```

### Endpoints API

| Endpoint | Méthode | Description | Paramètres |
|----------|---------|-------------|------------|
| `/api/analyze` | POST | Analyse une image de bookmaker | `file` (multipart), `disable_cache` (query param optionnel) |
| `/api/admin/clear-analysis-cache` | DELETE | Vide le cache des analyses | Aucun |
| `/api/diff` | GET | Récupère la valeur actuelle de diffExpected | Aucun |
| `/api/learn` | POST | Enregistre un apprentissage | `predicted_score`, `real_score` |
| `/api/health` | GET | Vérification de santé de l'API | Aucun |
| `/api/diagnostic/last-analysis` | GET | Récupère les détails de la dernière analyse | Aucun |

---

## 📖 Guide d'utilisation

### Scénario 1 : Analyse normale d'une image

1. Sélectionnez **"🎯 Mode Production"** dans la navbar
2. Uploadez une image de bookmaker (capture d'écran)
3. Attendez les résultats (quelques secondes pour la première analyse, instantané ensuite)
4. Consultez :
   - Le score le plus probable
   - Le niveau de confiance
   - Le Top 3 des scores prédits
   - Les informations du match et du bookmaker

### Scénario 2 : Test de l'algorithme après modification

1. Sélectionnez **"🧪 Mode Test"** dans la navbar
2. **Cochez** la case "Mode Test : Recalculer entièrement"
3. Uploadez votre image
4. Cliquez sur "🎯 Analyser"
5. Vérifiez le badge **"Nouveau calcul complet"** (vert)
6. Analysez les résultats et comparez avec les valeurs attendues
7. Consultez les logs backend si nécessaire : `tail -f /var/log/supervisor/backend.*.log`

### Scénario 3 : Réinitialisation complète du cache

1. Sélectionnez **"🧪 Mode Test"** dans la navbar
2. Cliquez sur **"🧹 Vider le cache"**
3. Confirmez l'action
4. Attendez le message de confirmation
5. Toutes les prochaines analyses seront recalculées

---

## 🔍 Comprendre les résultats

### Score le plus probable
Le score prédit avec la probabilité la plus élevée selon l'algorithme de Poisson avec correction adaptative.

### Niveau de confiance
Indique la certitude de la prédiction :
- **> 80%** : Prédiction très fiable
- **60-80%** : Prédiction fiable
- **40-60%** : Prédiction modérée
- **< 40%** : Prédiction incertaine (plusieurs scores possibles)

### Top 3 des scores
Les trois scores les plus probables avec leurs probabilités respectives. La somme des probabilités du Top 3 est toujours inférieure ou égale à 100%.

### Match et Bookmaker
Informations extraites par OCR de l'image :
- **Match** : Nom des équipes (format "Équipe A - Équipe B")
- **Bookmaker** : Nom de la plateforme de paris (Unibet, Winamax, BetClic, etc.)

---

## 🛠️ Dépannage

### Le résultat ne change pas après avoir modifié l'algorithme

**Solution :** Le cache est probablement activé.
1. Passez en Mode Test
2. Cochez "Mode Test : Recalculer entièrement"
3. Réanalysez l'image

### Le bouton "Analyser" reste grisé

**Solution :** Vous n'avez pas sélectionné d'image.
1. Cliquez sur le champ "Image du bookmaker"
2. Sélectionnez un fichier image valide

### Erreur "Aucune cote détectée dans l'image"

**Causes possibles :**
- L'image est de mauvaise qualité (floue, pixelisée)
- Le format du bookmaker n'est pas reconnu
- L'image ne contient pas de grille de cotes

**Solutions :**
1. Vérifiez que l'image contient bien une grille de cotes visibles
2. Assurez-vous que l'image est nette et lisible
3. Essayez avec une capture d'écran de meilleure qualité

### Le cache ne se vide pas

**Solution :**
1. Vérifiez que l'API backend est accessible
2. Consultez les logs : `tail -f /var/log/supervisor/backend.*.log`
3. Redémarrez le backend si nécessaire : `sudo supervisorctl restart backend`

---

## 📝 Bonnes pratiques

### Pour les utilisateurs finaux
- ✅ Utilisez le **Mode Production** pour l'usage quotidien
- ✅ Prenez des captures d'écran nettes et bien cadrées
- ✅ Attendez que l'analyse soit terminée avant de soumettre une nouvelle image

### Pour les développeurs/testeurs
- ✅ Utilisez le **Mode Test** pour valider les modifications
- ✅ Désactivez le cache lors des tests de l'algorithme
- ✅ Videz le cache après les mises à jour majeures
- ✅ Consultez les logs backend pour le débogage approfondi
- ✅ Testez avec différents bookmakers pour valider la robustesse de l'OCR

---

## 📞 Support

Pour toute question ou problème :
1. Consultez d'abord cette documentation
2. Vérifiez les logs backend : `tail -f /var/log/supervisor/backend.*.log`
3. Testez en Mode Test avec le cache désactivé
4. Contactez l'équipe de développement si le problème persiste

---

## 🔄 Historique des versions

**Version actuelle : 1.2**
- ✅ Mode Production et Mode Test avec navigation
- ✅ Contrôles avancés du cache (désactivation et vidage)
- ✅ Extraction du nom du match et du bookmaker
- ✅ Algorithme de prédiction amélioré avec Poisson weighting
- ✅ Système d'apprentissage adaptatif sécurisé
- ✅ Cache d'analyse avec badges de source
- ✅ Interface utilisateur optimisée et responsive

---

*Cette documentation couvre les fonctionnalités principales de l'application. Pour des informations techniques détaillées sur l'architecture backend ou le développement, consultez les commentaires dans le code source.*

# Dashboard React - Guide d'intégration

## 📋 Vue d'ensemble

Dashboard complet pour le système de prédiction football avec 3 pages principales :
- **📸 Analyser** : Upload et analyse d'images bookmaker
- **📋 Historique** : Visualisation des analyses passées
- **⚙️ Système** : Monitoring du scheduler et diagnostic

---

## 📁 Fichiers créés

```
/app/frontend/src/pages/
├── DashboardPage.jsx    # Navigation principale
├── UploadPage.jsx       # Page d'upload
├── HistoryPage.jsx      # Page historique
└── SystemPage.jsx       # Page système
```

---

## 🔌 Endpoints backend requis

Le dashboard communique avec les endpoints suivants (déjà créés) :

### Upload & Analyse
- `POST /api/upload-image-advanced` - Upload et analyse d'image
  - Params: file, league, home_team, away_team, bookmaker, prefer_gpt_vision

### Historique
- `GET /api/last-uploads?limit=50` - Liste des images uploadées
- `GET /api/last-analyses?limit=50` - Liste des analyses

### Système
- `GET /api/admin/league/scheduler-status` - Statut du scheduler
- `POST /api/admin/league/trigger-update` - Force une mise à jour
- `GET /api/diagnostic` - Lance le diagnostic système
- `GET /api/learning-stats?days=30` - Statistiques d'apprentissage

---

## 🚀 Intégration dans App.jsx

### Option 1 : Route dédiée (recommandé)

```jsx
// /app/frontend/src/App.jsx
import DashboardPage from './pages/DashboardPage';

// Ajouter une route
<Route path="/dashboard" element={<DashboardPage />} />
```

### Option 2 : Remplacer la page d'accueil

```jsx
// /app/frontend/src/App.jsx
import DashboardPage from './pages/DashboardPage';

function App() {
  return <DashboardPage />;
}
```

---

## 🎨 Styling

Le dashboard utilise **Tailwind CSS** qui est déjà configuré dans le projet.

Classes utilisées :
- Layout: `min-h-screen`, `max-w-7xl`, `mx-auto`
- Composants: `bg-white`, `shadow-lg`, `rounded-lg`
- Boutons: `bg-blue-600`, `hover:bg-blue-700`, `text-white`
- Grilles: `grid`, `grid-cols-2`, `gap-4`

---

## 🔧 Configuration

### Variables d'environnement

Le dashboard utilise `REACT_APP_BACKEND_URL` pour pointer vers le backend :

```bash
# /app/frontend/.env
REACT_APP_BACKEND_URL=http://localhost:8001
```

En production, cette variable est automatiquement définie.

---

## 📱 Fonctionnalités

### Page Upload
- ✅ Drag & drop d'image
- ✅ Preview de l'image
- ✅ Sélection de ligue
- ✅ Saisie équipes et bookmaker
- ✅ Toggle GPT-Vision / Tesseract
- ✅ Affichage résultats détaillés

### Page Historique
- ✅ Liste des images uploadées
- ✅ Liste des analyses
- ✅ Filtres et tri
- ✅ Détails de chaque analyse

### Page Système
- ✅ Statut du scheduler
- ✅ Forcer une mise à jour
- ✅ Lancer un diagnostic
- ✅ Statistiques d'apprentissage
- ✅ Taux de réussite des tests

---

## 🧪 Test local

```bash
# 1. Démarrer le backend
cd /app/backend
sudo supervisorctl restart backend

# 2. Démarrer le frontend
cd /app/frontend
yarn start

# 3. Ouvrir le navigateur
# http://localhost:3000/dashboard
```

---

## 📊 Exemples d'utilisation

### 1. Analyser une image

1. Cliquer sur "📸 Analyser"
2. Sélectionner une image bookmaker
3. Remplir les champs (optionnel)
4. Cocher "GPT-4 Vision prioritaire"
5. Cliquer "🚀 Lancer l'analyse"

### 2. Voir l'historique

1. Cliquer sur "📋 Historique"
2. Basculer entre "Images" et "Analyses"
3. Voir tous les détails des analyses passées

### 3. Monitorer le système

1. Cliquer sur "⚙️ Système"
2. Voir le statut du scheduler
3. Forcer une mise à jour si nécessaire
4. Lancer un diagnostic pour vérifier la santé du système

---

## 🐛 Dépannage

### Le dashboard ne charge pas
- Vérifier que le backend est démarré: `sudo supervisorctl status backend`
- Vérifier l'URL dans `.env`: `REACT_APP_BACKEND_URL`

### Erreur CORS
- Le backend doit autoriser l'origine du frontend
- Vérifier les headers CORS dans `server.py`

### Upload ne fonctionne pas
- Vérifier que `/app/data/uploads` existe et a les permissions
- Vérifier les logs backend: `tail -f /var/log/supervisor/backend.out.log`

---

## 🎯 Prochaines améliorations

- [ ] Authentification utilisateur
- [ ] Pagination de l'historique
- [ ] Graphiques de statistiques
- [ ] Notifications en temps réel
- [ ] Export CSV des analyses
- [ ] Mode sombre

---

## ✅ Checklist d'intégration

- [x] Créer les 4 fichiers .jsx
- [x] Endpoints backend disponibles
- [x] Tailwind CSS configuré
- [ ] Intégrer dans App.jsx
- [ ] Tester upload d'image
- [ ] Tester historique
- [ ] Tester diagnostic système
- [ ] Déployer en production

---

**Date:** 18 novembre 2025
**Version:** 1.0
**Status:** ✅ Prêt pour intégration

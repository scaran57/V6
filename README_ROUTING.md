# 🔀 Documentation Technique - Système de Routage

## 📋 Vue d'ensemble

Ce document explique l'architecture technique du système de routage mis en place pour supporter les deux modes d'utilisation de l'application : Mode Production et Mode Test.

---

## 🏗️ Architecture

### Structure des fichiers

```
/app/frontend/src/
├── index.js              # Point d'entrée - Monte <AppRouter />
├── AppRouter.js          # Composant de routage principal
├── TestMode.js           # Wrapper pour le mode test
├── App.js                # Application principale (mode production)
└── components/
    └── AnalyzePage.jsx   # Composant d'analyse avec contrôles cache
```

### Flux de navigation

```
index.js
    └─> AppRouter (state: mode = "production" | "test")
            ├─> Mode Production → <App />
            └─> Mode Test → <TestMode>
                                └─> <AnalyzePage />
```

---

## 📄 Détails des composants

### 1. `index.js`

**Rôle :** Point d'entrée de l'application React

**Modification effectuée :**
```jsx
// AVANT
import App from "@/App";
root.render(<App />);

// APRÈS
import AppRouter from "@/AppRouter";
root.render(<AppRouter />);
```

**Justification :** 
- Permet d'introduire le système de routage sans casser l'existant
- `AppRouter` affiche `App` par défaut (mode production)
- Migration transparente pour les utilisateurs existants

---

### 2. `AppRouter.js`

**Rôle :** Gestionnaire de navigation entre les modes

**Architecture :**
```jsx
function AppRouter() {
  const [mode, setMode] = useState("production");
  
  return (
    <div>
      {/* Navbar avec boutons de navigation */}
      <nav>
        <button onClick={() => setMode("production")}>Mode Production</button>
        <button onClick={() => setMode("test")}>Mode Test</button>
      </nav>
      
      {/* Affichage conditionnel selon le mode */}
      {mode === "production" ? <App /> : <TestMode />}
    </div>
  );
}
```

**Caractéristiques :**
- **State local** : `mode` géré par `useState` (pas de bibliothèque de routage externe)
- **Navbar persistante** : Visible sur toutes les pages pour basculer facilement
- **Composants isolés** : `App` et `TestMode` sont complètement indépendants
- **Pas de rechargement** : Navigation fluide en SPA (Single Page Application)

**Design de la navbar :**
- Fond gris foncé (`bg-gray-800`)
- Boutons avec états actif/inactif
- Icônes pour chaque mode (🎯 Production, 🧪 Test)
- Responsive avec `max-w-7xl mx-auto`

---

### 3. `TestMode.js`

**Rôle :** Wrapper pour le mode test avec contexte visuel

**Architecture :**
```jsx
function TestMode() {
  return (
    <div>
      {/* Bandeau d'avertissement */}
      <div className="bg-yellow-100 border-l-4 border-yellow-500">
        <p>🧪 Mode Test Activé</p>
        <p>Cette page permet de tester avec contrôle du cache...</p>
      </div>
      
      {/* Composant d'analyse */}
      <AnalyzePage />
    </div>
  );
}
```

**Justification :**
- Sépare la logique du bandeau d'info et le composant d'analyse
- Facilite la maintenance et les futurs ajouts de fonctionnalités
- Permet d'ajouter facilement d'autres éléments au mode test (stats, logs, etc.)

**Design :**
- Bandeau jaune avec bordure gauche épaisse
- Message clair expliquant le mode test
- Icône 🧪 pour identification visuelle rapide

---

### 4. `AnalyzePage.jsx`

**Rôle :** Composant d'analyse avec contrôles avancés du cache

**Features principales :**

#### 4.1. State Management
```jsx
const [file, setFile] = useState(null);           // Image uploadée
const [result, setResult] = useState(null);       // Résultat de l'analyse
const [loading, setLoading] = useState(false);    // État de chargement
const [disableCache, setDisableCache] = useState(false); // Contrôle cache
```

#### 4.2. Fonction d'analyse
```jsx
const handleAnalyze = async () => {
  const formData = new FormData();
  formData.append("file", file);
  
  const url = `${backendUrl}/api/analyze${
    disableCache ? "?disable_cache=true" : ""
  }`;
  
  const res = await axios.post(url, formData);
  setResult(res.data);
};
```

**Points clés :**
- Utilise `FormData` pour l'upload de fichier
- Ajoute `?disable_cache=true` si le switch est activé
- Récupère `REACT_APP_BACKEND_URL` depuis `.env`
- Gestion d'erreur avec `try/catch` et messages utilisateur

#### 4.3. Fonction de vidage du cache
```jsx
const clearCache = async () => {
  if (!window.confirm("Voulez-vous vraiment vider le cache ?")) {
    return;
  }
  
  await axios.delete(`${backendUrl}/api/admin/clear-analysis-cache`);
  alert("✅ Cache vidé avec succès !");
};
```

**Sécurité :** Double confirmation via `window.confirm` avant suppression

#### 4.4. Interface utilisateur

**Section Configuration :**
- Upload de fichier avec design personnalisé
- Switch pour désactiver le cache (checkbox stylisée)
- Message d'info contextuel quand le cache est désactivé
- Bouton "Analyser" avec spinner de chargement
- Bouton "Vider le cache" avec icône

**Section Résultats :**
- Badges de source (cache vs nouveau calcul)
- Informations du match et bookmaker
- Score prédit et niveau de confiance
- Top 3 des scores avec médailles (🥇🥈🥉)
- Section technique dépliable avec `<details>`

---

## 🔗 Intégration Backend

### Endpoints utilisés

#### 1. POST `/api/analyze`
```python
@app.post("/api/analyze")
async def analyze(
    file: UploadFile,
    disable_cache: bool = Query(False)
):
    # Si disable_cache=True, force nouveau calcul
    # Sinon, vérifie matches_memory.json
    ...
```

**Query parameter :**
- `disable_cache` (optionnel) : Boolean pour désactiver le cache

**Réponse :**
```json
{
  "matchName": "PSG - Marseille",
  "bookmaker": "Winamax",
  "mostProbableScore": "1-1",
  "confidence": 0.87,
  "top3": [...],
  "fromMemory": false,
  "cacheDisabled": true,
  "matchId": "abc123",
  "analyzedAt": "2025-01-15T10:30:00Z"
}
```

#### 2. DELETE `/api/admin/clear-analysis-cache`
```python
@app.delete("/api/admin/clear-analysis-cache")
async def clear_analysis_cache():
    # Réinitialise matches_memory.json
    memory_path = Path(__file__).parent / "data" / "matches_memory.json"
    with open(memory_path, "w") as f:
        json.dump({}, f)
    return {"status": "success", "message": "Cache vidé"}
```

---

## 🎨 Design et UX

### Principes appliqués

1. **Cohérence visuelle**
   - Palette de couleurs cohérente (indigo, blue, yellow, green, purple)
   - Icônes significatives pour chaque action
   - Espacement uniforme avec Tailwind CSS

2. **Feedback utilisateur**
   - Badges visuels pour l'état du cache
   - Spinner de chargement pendant l'analyse
   - Messages de confirmation pour les actions critiques
   - États hover sur tous les boutons

3. **Accessibilité**
   - Contraste de couleurs suffisant
   - Labels explicites pour les inputs
   - Messages d'erreur clairs
   - Navigation au clavier possible

4. **Responsive design**
   - Layout adaptatif avec `max-w-4xl mx-auto`
   - Grid responsive pour les cartes de résultats
   - Navbar responsive avec flexbox

---

## 🧪 Scénarios de test

### Test 1 : Navigation entre modes
1. Charger l'application
2. Vérifier que le Mode Production est affiché par défaut
3. Cliquer sur "🧪 Mode Test"
4. Vérifier que le bandeau jaune apparaît
5. Revenir au Mode Production
6. Vérifier qu'aucune navbar n'est dupliquée

### Test 2 : Analyse avec cache activé
1. Passer en Mode Test
2. Ne PAS cocher "Mode Test : Recalculer entièrement"
3. Uploader une image
4. Analyser
5. Vérifier le badge "Récupéré depuis le cache" (si déjà analysée) ou "Nouveau calcul complet"

### Test 3 : Analyse avec cache désactivé
1. Passer en Mode Test
2. Cocher "Mode Test : Recalculer entièrement"
3. Uploader une image déjà analysée
4. Analyser
5. Vérifier les badges "Nouveau calcul complet" ET "Cache désactivé"

### Test 4 : Vidage du cache
1. Passer en Mode Test
2. Cliquer sur "🧹 Vider le cache"
3. Confirmer l'action
4. Vérifier le message de succès
5. Réanalyser une image précédemment mise en cache
6. Vérifier qu'elle est recalculée

---

## 🔒 Sécurité et bonnes pratiques

### Variables d'environnement
```jsx
const backendUrl = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";
```
- Ne jamais hardcoder les URLs
- Toujours utiliser `.env` pour la configuration
- Fallback sur localhost pour le développement

### Gestion d'erreur
```jsx
try {
  // API call
} catch (err) {
  console.error(err);
  alert("Erreur lors de l'analyse !");
}
```
- Tous les appels API sont dans des `try/catch`
- Messages utilisateur explicites en cas d'erreur
- Logs console pour le débogage

### Confirmation des actions destructives
```jsx
if (!window.confirm("Voulez-vous vraiment vider le cache ?")) {
  return;
}
```
- Double confirmation avant suppression du cache
- Message clair sur la conséquence de l'action

---

## 📈 Évolutions futures possibles

### Court terme
- [ ] Ajout d'un historique des analyses dans le Mode Test
- [ ] Statistiques de performance (temps d'analyse, taux de cache hit)
- [ ] Export des résultats en JSON/CSV

### Moyen terme
- [ ] Mode "Comparaison" pour comparer deux analyses
- [ ] Visualisation graphique des probabilités
- [ ] Logs backend accessibles depuis le frontend

### Long terme
- [ ] Utilisation de React Router pour des URLs distinctes
- [ ] Mode "Admin" avec gestion des paramètres diffExpected
- [ ] Dashboard de monitoring en temps réel

---

## 🛠️ Maintenance

### Ajout d'un nouveau mode

1. **Créer le composant du mode**
   ```jsx
   // NewMode.js
   function NewMode() {
     return <div>Nouveau mode...</div>;
   }
   export default NewMode;
   ```

2. **Mettre à jour AppRouter.js**
   ```jsx
   import NewMode from "./NewMode";
   
   // Ajouter au state
   const [mode, setMode] = useState("production");
   
   // Ajouter un bouton dans la navbar
   <button onClick={() => setMode("new")}>Nouveau Mode</button>
   
   // Ajouter dans le rendering conditionnel
   {mode === "production" ? <App /> : 
    mode === "test" ? <TestMode /> :
    mode === "new" ? <NewMode /> : null}
   ```

### Modification de la navbar

Editer `AppRouter.js` section `<nav>` :
```jsx
<nav className="bg-gray-800 text-white p-4 shadow-lg">
  <div className="max-w-7xl mx-auto flex items-center justify-between">
    <h1>Mon titre personnalisé</h1>
    {/* Boutons de navigation */}
  </div>
</nav>
```

---

## 📞 Questions fréquentes

**Q : Pourquoi ne pas utiliser React Router ?**
R : Pour ce cas d'usage simple (2 modes), un state local suffit. React Router sera pertinent si on ajoute des URLs distinctes, des paramètres d'URL, ou plus de 4-5 pages.

**Q : Peut-on accéder directement au Mode Test via une URL ?**
R : Actuellement non. On pourrait implémenter cela avec React Router et des routes comme `/production` et `/test`.

**Q : Le cache est-il partagé entre les deux modes ?**
R : Oui, le cache est géré côté backend et partagé entre tous les modes. Seul le Mode Test permet de le contrôler.

**Q : Peut-on ajouter une authentification ?**
R : Oui, on pourrait wrapper `AppRouter` avec un composant d'authentification ou ajouter une protection sur les routes sensibles (comme les endpoints admin).

---

*Document créé le : 2025-01-15*  
*Dernière mise à jour : 2025-01-15*  
*Version : 1.0*

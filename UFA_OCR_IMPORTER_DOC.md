# 📸 UFA OCR Importer v1.0 - Documentation

## Vue d'ensemble

Le module **UFA OCR Importer** automatise la saisie des scores réels en lisant automatiquement les captures d'écran de résultats (ex: FDJ, bookmakers).

## 🎯 Objectifs

1. **Automatiser la saisie** : Plus besoin de taper manuellement les scores
2. **Traitement par lot** : Analyser plusieurs images d'un coup
3. **Intégration UFA** : Ajouter automatiquement les scores au système d'apprentissage
4. **Flexibilité** : Fonctionnement en ligne de commande ou via API

## 📁 Fichiers

### Module principal
- **Emplacement** : `/app/backend/ufa/ufa_ocr_importer.py`
- **Fonction principale** : `process_image()`, `process_folder()`
- **Dossier d'upload** : `/app/uploads/fdj_captures/`

### API Endpoints
- `POST /api/ufa/ocr/upload` - Upload une image
- `POST /api/ufa/ocr/process-folder` - Traiter un dossier

## 🔧 Fonctionnement

### Pré-traitement d'Image

L'image est optimisée pour l'OCR :

1. **Conversion en niveaux de gris** : Simplifie l'analyse
2. **Amélioration du contraste** : ×2
3. **Amélioration de la netteté** : ×2
4. **Filtre SHARPEN** : Affine les contours

### Détection de Score

Le module utilise plusieurs patterns regex :

```python
# Pattern 1 : 3-1, 3:1, 3–1
r"\b([0-9])\s*[-:–—]\s*([0-9])\b"

# Pattern 2 : 3 1 (avec espace)
r"\b([0-9])\s+([0-9])\b"
```

**Validation** : Les scores doivent être entre 0 et 9.

### Ajout au Système UFA

Le score détecté est automatiquement ajouté à `/app/data/real_scores.jsonl` :

```json
{
  "league": "LaLiga",
  "home_team": "Real Madrid",
  "away_team": "Barcelona",
  "home_goals": 2,
  "away_goals": 1,
  "timestamp": "2025-11-08T23:40:43",
  "source": "ocr_importer"
}
```

## 🚀 Utilisation

### Méthode 1 : Ligne de Commande

#### Traiter un dossier

```bash
# Traiter le dossier par défaut
python3 /app/backend/ufa/ufa_ocr_importer.py

# Traiter un dossier spécifique
python3 /app/backend/ufa/ufa_ocr_importer.py /path/to/images
```

**Exemple de sortie** :
```
╔====================================================================╗
║                    UFA OCR IMPORTER v1.0                           ║
╚====================================================================╝

======================================================================
🔄 TRAITEMENT DU DOSSIER: /app/uploads/fdj_captures
======================================================================

📸 Traitement de match1.png...
✅ Match ajouté : Unknown vs Unknown (3-1)

📸 Traitement de match2.png...
✅ Match ajouté : Unknown vs Unknown (1-1)

======================================================================
📊 RÉSUMÉ:
   Total d'images traitées: 2
   Scores détectés: 2/2 (100.0%)
   Échecs: 0
======================================================================
```

### Méthode 2 : API Upload

#### Upload une seule image

```bash
curl -X POST "http://localhost:8001/api/ufa/ocr/upload" \
  -F "file=@/path/to/image.png" \
  -F "home_team=Real Madrid" \
  -F "away_team=Barcelona" \
  -F "league=LaLiga"
```

**Réponse** :
```json
{
  "success": true,
  "message": "Score détecté et ajouté: 2-1",
  "score": "2-1",
  "entry": {
    "league": "LaLiga",
    "home_team": "Real Madrid",
    "away_team": "Barcelona",
    "home_goals": 2,
    "away_goals": 1,
    "timestamp": "2025-11-08T23:40:43",
    "source": "ocr_importer"
  }
}
```

#### Traiter un dossier via API

```bash
curl -X POST "http://localhost:8001/api/ufa/ocr/process-folder" \
  -F "folder_path=/app/uploads/fdj_captures" \
  -F "home_team=Unknown" \
  -F "away_team=Unknown" \
  -F "league=Unknown"
```

**Réponse** :
```json
{
  "success": true,
  "message": "Dossier traité: 5/7 scores détectés",
  "report": {
    "total": 7,
    "detected": 5,
    "failed": 2,
    "results": [...]
  }
}
```

### Méthode 3 : Intégration Frontend (à venir)

**Composant React** :
```javascript
const UploadScore = () => {
  const handleUpload = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('league', selectedLeague);
    
    const response = await fetch(`${API_URL}/api/ufa/ocr/upload`, {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    if (result.success) {
      alert(`Score détecté: ${result.score}`);
    }
  };
  
  return <input type="file" onChange={e => handleUpload(e.target.files[0])} />;
};
```

## 📊 Workflow Complet

```
1. Capture d'écran FDJ
   ↓
2. Upload via API ou dépose dans dossier
   ↓
3. Pré-traitement de l'image
   ↓
4. OCR avec Tesseract
   ↓
5. Détection du score via regex
   ↓
6. Validation (0-9 pour chaque équipe)
   ↓
7. Ajout à real_scores.jsonl
   ↓
8. Training UFA automatique (3h00)
   ↓
9. Amélioration du modèle
```

## 🔍 Dépannage

### Problème : Aucun score détecté

**Causes possibles** :
1. Image de mauvaise qualité
2. Texte trop petit
3. Contraste faible
4. Format de score inhabituel

**Solutions** :
```bash
# Vérifier le texte détecté
python3 << EOF
from ufa.ufa_ocr_importer import extract_score_from_image
home, away, text = extract_score_from_image('/path/to/image.png')
print(f"Texte détecté: {text}")
EOF

# Améliorer l'image manuellement
# - Augmenter la taille
# - Améliorer le contraste
# - Recadrer autour du score
```

### Problème : Mauvais score détecté

**Exemple** : Détecte "8" au lieu de "3"

**Solutions** :
1. Améliorer la qualité de l'image source
2. Recadrer pour isoler le score
3. Saisir manuellement si l'OCR échoue régulièrement

### Problème : Tesseract non trouvé

**Erreur** : `tesseract_cmd is not installed`

**Solution** :
```bash
# Installer Tesseract
sudo apt-get install tesseract-ocr

# Vérifier l'installation
which tesseract
# → /usr/bin/tesseract

# Installer les langues
sudo apt-get install tesseract-ocr-fra tesseract-ocr-eng
```

## 📈 Performances

### Taux de Réussite Attendu

| Type d'image | Taux de succès |
|--------------|----------------|
| Screenshot FDJ clair | 90-95% |
| Photo d'écran | 70-80% |
| Image floue | 40-60% |
| Score manuscrit | 10-30% |

### Temps de Traitement

- **Une image** : ~1-2 secondes
- **10 images** : ~10-20 secondes
- **100 images** : ~2-3 minutes

## 💡 Bonnes Pratiques

### 1. Qualité des Images

✅ **Recommandé** :
- Screenshots directs (pas de photos d'écran)
- Résolution minimale : 800x600
- Format PNG ou JPEG
- Score bien visible et isolé

❌ **À éviter** :
- Photos d'écran avec reflets
- Images floues ou pixelisées
- Scores manuscrits
- Captures avec beaucoup de texte parasité

### 2. Organisation des Fichiers

```
/app/uploads/fdj_captures/
├── 2025-11-08/
│   ├── match1_laliga.png
│   ├── match2_laliga.png
│   └── match3_ligue1.png
├── 2025-11-09/
│   └── ...
└── processed/
    └── ... (optionnel)
```

### 3. Nommage des Fichiers

**Convention recommandée** :
```
{date}_{league}_{home}_{away}.png

Exemples :
- 2025-11-08_LaLiga_RealMadrid_Barcelona.png
- 2025-11-08_Ligue1_PSG_Marseille.png
```

### 4. Vérification Manuelle

Après traitement automatique, vérifier :
```bash
# Voir les 5 derniers scores ajoutés
tail -5 /app/data/real_scores.jsonl | python3 -m json.tool
```

## 🔄 Intégration avec le Système

### Cycle Complet

```
Jour J :
09:00 - Captures FDJ uploadées
09:05 - OCR traite les images
09:10 - Scores ajoutés à real_scores.jsonl

Jour J+1 :
03:00 - Training UFA automatique
03:05 - Priors ajustés selon les nouveaux scores
03:10 - Balance check effectué
```

### Vérification

```bash
# Compter les scores ajoutés aujourd'hui
grep "2025-11-08" /app/data/real_scores.jsonl | wc -l

# Lancer le training manuellement
python3 /app/backend/ufa/training/trainer.py

# Vérifier l'impact
curl http://localhost:8001/api/ufa/balance
```

## 🚧 Limitations Actuelles

1. **Noms d'équipes** : Non détectés par OCR (reste "Unknown")
2. **Ligue** : Doit être spécifiée manuellement ou reste "Unknown"
3. **Scores > 9** : Non supportés (rare en football)
4. **Mi-temps** : Non détecté (score final uniquement)

## 🎯 Évolutions Futures

### Phase 2 : OCR Complet

- Détection automatique des noms d'équipes
- Extraction de la ligue depuis l'image
- Support des scores > 9 (handball, basketball)

### Phase 3 : IA Avancée

- Modèle de détection d'objets (YOLO) pour localiser les scores
- Reconnaissance des logos d'équipes
- Classification automatique de la ligue

### Phase 4 : Automation Complète

- Monitoring automatique des sites de bookmakers
- Scraping des résultats en temps réel
- Validation croisée entre sources

## 📞 Support

### Logs

```bash
# Logs du backend
tail -f /var/log/supervisor/backend.out.log | grep OCR

# Fichier de sortie UFA
tail -f /app/data/real_scores.jsonl
```

### Debug

```python
# Test manuel d'une image
python3 << EOF
import sys
sys.path.insert(0, '/app/backend')
from ufa.ufa_ocr_importer import extract_score_from_image

home, away, text = extract_score_from_image('/path/to/image.png')
print(f"Score: {home}-{away}")
print(f"Texte complet:\n{text}")
EOF
```

## ✅ Checklist d'Utilisation

- [ ] Tesseract installé et fonctionnel
- [ ] Dossier `/app/uploads/fdj_captures/` créé
- [ ] Images de bonne qualité (screenshots)
- [ ] Tester avec une image simple d'abord
- [ ] Vérifier les scores ajoutés dans real_scores.jsonl
- [ ] Lancer le training pour voir l'impact
- [ ] Vérifier le balance check

---

**Version** : 1.0
**Dernière mise à jour** : 2025-11-08
**Dépendances** : pytesseract, Pillow, tesseract-ocr

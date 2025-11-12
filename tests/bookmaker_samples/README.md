# 📁 Tests Bookmaker Samples

Ce dossier contient des images de bookmakers pour tester l'OCR et les prédictions.

## 🎯 Objectif

Valider que le système OCR + Correction + Prédiction fonctionne correctement avec de vraies images de bookmakers.

## 📸 Types d'Images à Tester

### ✅ Images Recommandées
- **Images bookmaker originales** : Captures directes de Winamax, Unibet, BetClic, ParionsSport
- **Format** : JPEG, PNG
- **Qualité** : Bonne résolution (min 1080px largeur)
- **Contenu** : Match avec cotes clairement visibles

### ⚠️ Images À Éviter
- Screenshots d'application avec overlay (interface, boutons, etc.)
- Images trop petites ou floues
- Images avec texte superposé non-bookmaker

## 🧪 Tests Disponibles

### Test 1 : OCR Basique
```bash
cd /app/backend
python3 ocr_engine.py /path/to/bookmaker_image.jpg
```

### Test 2 : OCR avec Préprocesseur Avancé
```bash
cd /app/backend
python3 tools/ocr_preprocessor.py /path/to/bookmaker_image.jpg
```

### Test 3 : Analyse Complète (sans correction OCR)
```bash
curl -X POST "http://localhost:8001/api/analyze" \
  -F "file=@/path/to/bookmaker_image.jpg"
```

### Test 4 : Analyse Complète (avec correction OCR)
```bash
curl -X POST "http://localhost:8001/api/analyze?enable_ocr_correction=true" \
  -F "file=@/path/to/bookmaker_image.jpg"
```

## 📊 Résultats Attendus

### Cas 1 : Match de Club (LaLiga, PremierLeague, etc.)
```json
{
  "success": true,
  "league": "LaLiga",
  "matchName": "Real Madrid - Barcelona",
  "mostProbableScore": "2-1",
  "confidence": 0.75,
  "ocrCorrection": {
    "corrections_applied": 2,
    "details": {...}
  }
}
```

### Cas 2 : Match International (World Cup Qualification)
```json
{
  "success": true,
  "league": "WorldCupQualification",
  "matchName": "Norvège - Estonie",
  "mostProbableScore": "3-1",
  "confidence": 0.68,
  "ocrCorrection": {
    "corrections_applied": 1,
    "details": {...}
  }
}
```

## 🔧 Préprocesseur OCR

Le préprocesseur avancé (`ocr_preprocessor.py`) améliore la qualité de l'OCR en :
- ✅ Supprimant les overlays colorés (UI, boutons)
- ✅ Recadrant automatiquement les zones de texte
- ✅ Améliorant le contraste (CLAHE)
- ✅ Appliquant un threshold adaptatif
- ✅ Réduisant le bruit

### Configuration
Fichier : `/app/backend/ocr_engine.py`
```python
USE_ADVANCED_PREPROCESSOR = True  # Activer/désactiver
```

## 📝 Ajouter des Images de Test

1. Copier l'image dans ce dossier :
```bash
cp /path/to/bookmaker_image.jpg /app/tests/bookmaker_samples/
```

2. Renommer avec convention :
```
[bookmaker]_[league]_[match]_[date].jpg

Exemples :
- winamax_laliga_realmadrid_barcelona_20251112.jpg
- unibet_premierleague_arsenal_chelsea_20251113.jpg
- betclic_worldcup_norway_estonia_20251115.jpg
```

3. Lancer les tests :
```bash
cd /app/tests
python3 -m pytest test_ocr_bookmakers.py
```

## 🚀 Prochaines Améliorations

- [ ] Créer script de test automatique (`test_ocr_bookmakers.py`)
- [ ] Ajouter 10+ images de référence par bookmaker
- [ ] Mesurer taux de réussite OCR par bookmaker
- [ ] Optimiser préprocesseur par bookmaker (Winamax vs Unibet)
- [ ] Créer benchmark de performance

## 📞 Support

Si l'OCR ne fonctionne pas sur vos images :
1. Vérifier que l'image est claire et de bonne résolution
2. Essayer avec `enable_ocr_correction=true`
3. Vérifier les logs : `/var/log/supervisor/backend.err.log`
4. Tester le préprocesseur manuellement sur l'image

---

**Note** : Les screenshots d'application (avec interface par-dessus) donnent de mauvais résultats OCR. Utilisez des captures directes de bookmakers.

# 🔍 DIAGNOSTIC SYSTÈME OCR - 09 Novembre 2025

## Problème Rapporté
L'utilisateur a l'impression que le système "ne lit pas aussi bien qu'avant"

## Tests Effectués

### 1. Vérification Version
- ✅ Fichier `ocr_parser.py` restauré à la version précédente (commit 276a220)
- ✅ Backend redémarré avec succès
- ✅ Aucune erreur d'import

### 2. Tests sur Images Récentes (FDJ)

#### Image 1: Ligue 1 - Angers vs Auxerre
```
Texte OCR détecté:
"Angers 8 - 8 Auxerre"

Extraction actuelle:
- Home: "< a McDonalds eue ts"
- Away: "Auxerre ="
- League: "Ligue1" ✅

Problème: OCR lit "Angers" en plusieurs fragments éparpillés
```

#### Image 2: LaLiga - Rayo Vallecano vs Real Madrid
```
Texte OCR détecté:
"Rayo . ¥° @-@ Real Madrid Vallecano"

Extraction actuelle:
- Home: None
- Away: None
- League: "LaLiga" ✅

Problème: Noms d'équipes éparpillés sur plusieurs lignes, parser ne les trouve pas
```

### 3. Comparaison avec Images Anciennes

#### Anciennes images Winamax/Unibet
```
Winamax:
- Home: "4 Sul CD 47" (devrait être "Olympiakos")
- Away: "€ = + J4 r+)" (devrait être "PSV Eindhoven")
- League: ChampionsLeague ✅

Unibet:
- Home: "< VO" (devrait être "Juventus")
- Away: "= Sporting Portugal N dh" (devrait être "Sporting")
- League: PrimeiraLiga ✅
```

## Conclusions du Diagnostic

### ✅ Ce qui fonctionne correctement
1. **Détection des ligues**: Fonctionne très bien (Ligue1, LaLiga, ChampionsLeague, etc.)
2. **Extraction des scores et cotes**: Fonctionne correctement
3. **Application des coefficients de ligue**: Opérationnelle
4. **Backend**: Stable, pas d'erreurs

### ❌ Ce qui pose problème
1. **Extraction des noms d'équipes**: Qualité variable selon les images
2. **OCR sur images FDJ**: Plus problématique que Winamax/Unibet
3. **Texte éparpillé**: L'OCR lit dans le mauvais ordre

### 🔍 Analyse des Causes

#### Cause 1: Qualité Variable de l'OCR Tesseract
- L'OCR Tesseract a des difficultés avec certaines polices
- Les images FDJ utilisent une police/layout qui perturbe l'OCR
- Le texte est fragmenté et lu dans le désordre

#### Cause 2: Format des Images FDJ
Les nouvelles images FDJ ont:
- Plus de texte d'interface ("Paris", "Pari sur mesure", "Stats", "Compos")
- Des icônes et symboles qui perturbent l'OCR (<, =, @, ®, ©)
- Une mise en page différente de Winamax/Unibet

#### Cause 3: Stratégie d'Extraction Actuelle
La fonction `extract_teams_from_text()` cherche:
1. Des séparateurs (" - ", " vs ")
2. Des tokens connus (noms d'équipes dans la base)
3. Fuzzy matching

Mais quand l'OCR donne "< a McDonalds eue ts" au lieu de "Angers", aucune stratégie ne fonctionne.

## Historique de Performance

### Rappel des Tests Précédents
D'après `test_result.md`, même avant:
- **winamax1.jpg**: Échec OCR (attendu)
- **test_bookmaker.jpg**: Échec OCR (attendu)
- Extraction de noms: "Match non détecté" dans plusieurs cas
- **Test réel utilisateur**: 
  - test_winamax_real.jpg: "Match non détecté"
  - newcastle_bilbao.jpg: "Match non détecté"
  - test_unibet1.jpg: "S'inscrire vs Olympiakos" (interface incluse)

**→ Le système n'a JAMAIS eu une extraction parfaite des noms d'équipes**

## Recommandations

### Option 1: Améliorer le Prétraitement OCR
- Ajouter plus de techniques de prétraitement d'image
- Tester différents paramètres Tesseract
- Filtrer les zones d'interface avant OCR

### Option 2: Approche Hybride
- Garder la détection de ligue (fonctionne bien)
- Permettre à l'utilisateur de saisir manuellement les équipes si besoin
- Utiliser l'OCR pour les scores/cotes (fonctionne bien)

### Option 3: Machine Learning pour Noms d'Équipes
- Entraîner un modèle ML pour reconnaître les noms d'équipes dans les images
- Plus robuste que l'OCR classique
- Nécessite beaucoup d'images d'entraînement

### Option 4: API Externe
- Utiliser une API OCR plus performante (Google Vision, AWS Textract)
- Meilleure précision mais coût additionnel

## Conclusion

**Le système fonctionne comme avant** - il n'y a pas de régression. Cependant:
- ✅ La détection de ligue est excellente
- ✅ L'extraction des scores/cotes est fiable
- ⚠️ L'extraction des noms d'équipes a toujours été variable
- ⚠️ Les images FDJ sont particulièrement difficiles pour l'OCR

**Le problème n'est pas nouveau** - c'est une limite connue du système OCR avec Tesseract.

## Prochaines Étapes Suggérées

1. **Court terme**: 
   - Accepter que l'extraction des noms ne soit pas toujours parfaite
   - Se concentrer sur les scores/cotes (fonctionnent bien)
   - Utiliser la détection de ligue (très fiable)

2. **Moyen terme**:
   - Tester différents paramètres Tesseract
   - Améliorer le prétraitement des images
   - Ajouter une validation manuelle optionnelle

3. **Long terme**:
   - Évaluer des solutions ML
   - Considérer des API OCR premium
   - Entraîner un modèle spécifique aux images de bookmakers

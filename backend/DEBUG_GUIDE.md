# 🔍 MODE DEBUG - GUIDE D'UTILISATION

## Activation / Désactivation

Le mode DEBUG est contrôlé par une variable dans `/app/backend/debug_logger.py` :

```python
DEBUG_MODE = True   # Actif - Logs détaillés
DEBUG_MODE = False  # Désactivé - Logs minimaux (production)
```

---

## Ce Que Le Mode DEBUG Affiche

### 1️⃣ **ÉTAPE OCR**
```
🔍 [DEBUG - OCR] 17:09:46
  Étape: Scores validés et filtrés
  Scores détectés: 5
  Échantillon (3 premiers): [
    {'score': '2-0', 'odds': 8.0},
    {'score': '2-1', 'odds': 7.5},
    {'score': '1-1', 'odds': 5.0}
  ]
```

### 2️⃣ **PROBABILITÉS BRUTES**
```
🔍 [DEBUG - PRÉDICTION] 17:09:46
  Étape: Probabilités brutes (1/cotes)
  Scores analysés: 5
  Top 5: {
    '1-1': 0.3064,
    '2-1': 0.2043,
    '2-0': 0.1915,
    '0-0': 0.1702,
    'Autre': 0.1277
  }
```

### 3️⃣ **ANALYSE ÉQUILIBRE (Nouveau Calcul)**
```
🔍 [DEBUG - ANALYSE ÉQUILIBRE] 17:09:46
  Somme Victoires: 0.3957
  Somme Défaites: 0.0000
  Somme Nuls: 0.4766
  Balance Factor: 1.0000
  Draw Penalty: 0.5000
  Réduction nuls: 50.0%
```

### 4️⃣ **PROBABILITÉS PONDÉRÉES**
```
🔍 [DEBUG - PRÉDICTION] 17:09:46
  Étape: Probabilités pondérées finales
  Scores analysés: 5
  Top 5: {
    '1-1': 28.29%,
    '2-1': 25.28%,
    'Autre': 23.57%,
    '0-0': 15.72%,
    '2-0': 7.14%
  }
```

### 5️⃣ **RÉSULTAT FINAL**
```
🔍 [DEBUG - RÉSULTAT FINAL] 17:09:46
  🏆 Score le plus probable: 1-1
  Probabilité: 28.29%
  Top 5 complet: {...}
```

---

## Comment Consulter Les Logs

### Méthode 1 - Logs Backend (Temps Réel)
```bash
tail -f /var/log/supervisor/backend.err.log | grep -A 5 "DEBUG"
```

### Méthode 2 - Dernière Analyse
```bash
tail -n 200 /var/log/supervisor/backend.err.log | grep -A 10 "DEBUG"
```

### Méthode 3 - Recherche Spécifique
```bash
# Balance Factor
grep "ANALYSE ÉQUILIBRE" /var/log/supervisor/backend.err.log | tail -5

# Résultats finaux
grep "RÉSULTAT FINAL" /var/log/supervisor/backend.err.log | tail -5
```

---

## Utilisation

### Mode Development (DEBUG_MODE = True)
- ✅ Logs détaillés à chaque étape
- ✅ Voir exactement ce que l'OCR détecte
- ✅ Comprendre le calcul de prédiction
- ✅ Déboguer les problèmes
- ⚠️ Plus de logs = plus de volume

### Mode Production (DEBUG_MODE = False)
- ✅ Logs minimaux
- ✅ Meilleures performances
- ✅ Moins d'espace disque utilisé
- ❌ Moins de visibilité sur le processus

---

## Modification du Mode

**Pour ACTIVER le mode DEBUG:**
```bash
# Éditer le fichier
nano /app/backend/debug_logger.py

# Changer la ligne:
DEBUG_MODE = True

# Sauvegarder (Ctrl+O, Enter, Ctrl+X)
# Le backend recharge automatiquement (hot reload)
```

**Pour DÉSACTIVER:**
```bash
# Même processus
DEBUG_MODE = False
```

---

## Exemple Complet d'Analyse

Quand vous uploadez une image avec DEBUG_MODE = True :

```
[17:09:46] 🔍 OCR: 5 scores extraits
           ↓
[17:09:46] 🔍 PRÉDICTION: Conversion en probabilités
           ↓
[17:09:46] 🔍 ANALYSE ÉQUILIBRE: Balance=1.0, Penalty=0.5
           ↓
[17:09:46] 🔍 PRÉDICTION: Pondération gaussienne
           ↓
[17:09:46] 🔍 RÉSULTAT: 1-1 (28.29%)
```

Vous pouvez suivre **CHAQUE ÉTAPE** du processus !

---

## Troubleshooting

**Logs DEBUG ne s'affichent pas ?**
1. Vérifiez `DEBUG_MODE = True`
2. Redémarrez backend: `sudo supervisorctl restart backend`
3. Consultez les logs: `tail -f /var/log/supervisor/backend.err.log`

**Trop de logs ?**
- Passez en `DEBUG_MODE = False`
- Ou filtrez avec grep

**Besoin de logs pour une analyse spécifique ?**
- Activez DEBUG_MODE
- Faites votre analyse
- Désactivez DEBUG_MODE après

---

*Le mode DEBUG est PARFAIT pour comprendre comment fonctionne l'algorithme et déboguer les problèmes !* 🔍

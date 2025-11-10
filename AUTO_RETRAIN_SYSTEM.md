# 🤖 Système de Réentraînement Automatique UFA

Documentation du système d'apprentissage continu et d'ajustement automatique des coefficients.

## 📋 Vue d'ensemble

Le système de réentraînement automatique UFA effectue quotidiennement:
1. ✅ Réentraînement du modèle avec toutes les données accumulées
2. ✅ Évaluation des performances par ligue
3. ✅ Ajustement progressif des coefficients selon les performances
4. ✅ Génération de rapports détaillés

## 📁 Architecture

### Fichiers principaux

```
/app/backend/ufa/
├── force_retrain_all.py          # Script de réentraînement complet
├── auto_retrain_scheduler.py     # Scheduler automatique (daemon)
├── performance_tracker.py         # Évaluation des performances
└── training/
    └── trainer.py                 # Module d'entraînement UFA

/app/backend/
└── league_coeff.py                # Gestion et ajustement des coefficients

/app/data/
├── training_set.jsonl             # Dataset unifié d'entraînement
├── predicted_matches.jsonl        # Prédictions historiques
├── real_scores.jsonl              # Scores réels validés
├── league_coefficients.json       # Coefficients par ligue (ajustés auto)
├── performance_summary.json       # Performances actuelles par ligue
└── last_retrain.json              # Date du dernier réentraînement

/app/logs/
├── retrain_auto.log               # Logs du scheduler automatique
├── train_report.log               # Rapports de réentraînement
├── coeff_adjustment.log           # Ajustements de coefficients
└── performance_eval.log           # Évaluations de performance

/app/models/
└── ufa_model_v2.pkl               # Modèle UFA entraîné
```

## 🚀 Utilisation

### Mode manuel

```bash
# Réentraînement complet manuel
python3 /app/backend/ufa/force_retrain_all.py

# Évaluation des performances uniquement
python3 /app/backend/ufa/performance_tracker.py

# Test du scheduler (exécution immédiate)
python3 /app/backend/ufa/auto_retrain_scheduler.py --test
```

### Mode automatique (daemon)

```bash
# Lancer le scheduler en arrière-plan
nohup python3 /app/backend/ufa/auto_retrain_scheduler.py > /app/logs/scheduler.out 2>&1 &

# Vérifier les logs en temps réel
tail -f /app/logs/retrain_auto.log

# Arrêter le scheduler
pkill -f auto_retrain_scheduler.py
```

### Via systemd (production)

Créer `/etc/systemd/system/ufa-scheduler.service`:

```ini
[Unit]
Description=UFA Auto Retrain Scheduler
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/app/backend
ExecStart=/usr/bin/python3 /app/backend/ufa/auto_retrain_scheduler.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ufa-scheduler
sudo systemctl start ufa-scheduler
sudo systemctl status ufa-scheduler
```

## ⏰ Planification

Le scheduler s'exécute quotidiennement à **03:05 UTC**:
- Vérification du besoin (24h depuis dernier run)
- Réentraînement complet si nécessaire
- Évaluation + ajustement des coefficients
- Mise à jour des logs et rapports

## 📊 Flux de traitement

```
1. Vérification quotidienne (03:05 UTC)
   ↓
2. Chargement des données
   ├── predicted_matches.jsonl (24 entrées)
   └── real_scores.jsonl (192 entrées)
   ↓
3. Correction automatique
   ├── Fuzzy matching des noms d'équipes
   ├── Normalisation des ligues
   └── Suppression des doublons
   ↓
4. Application des coefficients
   ├── get_coeffs_for_match() (UEFA, FIFA, Ligues)
   └── Création de training_set.jsonl
   ↓
5. Réentraînement UFA
   ├── train_model()
   └── Sauvegarde dans /app/models/ufa_model_v2.pkl
   ↓
6. Évaluation des performances
   ├── Calcul accuracy par ligue
   ├── Erreur moyenne par ligue
   └── Sauvegarde dans performance_summary.json
   ↓
7. Ajustement des coefficients
   ├── Comparaison avec moyenne globale
   ├── Ajustement progressif (±0.002 par %)
   └── Sauvegarde dans league_coefficients.json
   ↓
8. Génération des rapports
   └── Logs détaillés dans /app/logs/
```

## 📈 Logique d'ajustement des coefficients

### Formule

Pour chaque ligue:
```
diff = accuracy_ligue - moyenne_globale
ajustement = diff × 0.002
nouveau_coeff = ancien_coeff + ajustement
```

### Exemple

```
Moyenne globale: 25%
Ligue1: 28% → +3% → ajustement +0.006
SerieA: 22% → -3% → ajustement -0.006
```

### Limites

- Coefficient minimum: **0.80**
- Coefficient maximum: **1.35**
- Ajustement progressif pour éviter les fluctuations brutales

## 📝 Exemple de logs

### retrain_auto.log

```
[2025-11-10 03:05:12] 🚀 CYCLE DE RÉENTRAÎNEMENT AUTOMATIQUE
[2025-11-10 03:05:12] ⏰ Dernier réentraînement il y a 1 jours et 0 heures
[2025-11-10 03:05:12] 🔁 ÉTAPE 1/3: Réentraînement global du modèle
[2025-11-10 03:05:45] ✅ Réentraînement terminé avec succès
[2025-11-10 03:05:45] 🔁 ÉTAPE 2/3: Évaluation des performances
[2025-11-10 03:05:50] ✅ Évaluation terminée: 6 ligues analysées
[2025-11-10 03:05:50] 🔁 ÉTAPE 3/3: Ajustement des coefficients de ligue
[2025-11-10 03:05:51] ✅ Coefficients ajustés selon les performances
[2025-11-10 03:05:51] ✅ CYCLE DE RÉENTRAÎNEMENT AUTOMATIQUE TERMINÉ
```

### coeff_adjustment.log

```
[2025-11-10 03:05:50] ⚙️  AJUSTEMENT AUTOMATIQUE DES COEFFICIENTS
[2025-11-10 03:05:50] 📊 Moyenne globale des performances: 26.5%
[2025-11-10 03:05:50] 📥 6 ligues à ajuster
[2025-11-10 03:05:50] ⚙️  Ligue1: 28.0% (40 matchs) → 1.000 → 1.003 (+0.003)
[2025-11-10 03:05:50] ⚙️  LaLiga: 31.5% (38 matchs) → 1.000 → 1.010 (+0.010)
[2025-11-10 03:05:50] ⚙️  SerieA: 22.0% (33 matchs) → 1.000 → 0.991 (-0.009)
[2025-11-10 03:05:50] ⚙️  PremierLeague: 25.0% (42 matchs) → 1.000 → 0.997 (-0.003)
[2025-11-10 03:05:50] ✅ 6 ligues ajustées selon performances.
```

## 🔧 Configuration

### Variables d'environnement (optionnel)

```bash
# Dossiers
export UFA_DATA_DIR="/app/data"
export UFA_LOGS_DIR="/app/logs"
export UFA_MODELS_DIR="/app/models"

# Paramètres d'ajustement
export COEFF_ADJUST_FACTOR=0.002  # Facteur d'ajustement (default: 0.002)
export MIN_MATCHES_FOR_ADJUST=10  # Minimum de matchs pour ajuster (default: 5)
```

### Fichier de configuration

Créer `/app/config/ufa_scheduler.json`:

```json
{
  "schedule": {
    "hour": 3,
    "minute": 5
  },
  "retrain_interval_hours": 24,
  "coefficient_adjustment": {
    "factor": 0.002,
    "min_matches": 10,
    "min_coeff": 0.80,
    "max_coeff": 1.35
  }
}
```

## 📊 Monitoring

### Vérifier l'état du système

```bash
# Dernier réentraînement
cat /app/data/last_retrain.json

# Performances actuelles
cat /app/data/performance_summary.json | jq .

# Coefficients actuels
cat /app/data/league_coefficients.json | jq .

# Logs récents
tail -50 /app/logs/retrain_auto.log

# Statistiques du modèle
cat /app/models/ufa_model_v2.pkl | jq .
```

### Dashboard de monitoring (à implémenter)

```python
# Exemple endpoint FastAPI
@app.get("/api/ufa/status")
def get_ufa_status():
    return {
        "last_retrain": load_json("/app/data/last_retrain.json"),
        "performance": load_json("/app/data/performance_summary.json"),
        "coefficients": load_json("/app/data/league_coefficients.json"),
        "model_stats": load_json("/app/models/ufa_model_v2.pkl")
    }
```

## 🐛 Dépannage

### Le scheduler ne démarre pas

```bash
# Vérifier les erreurs
python3 /app/backend/ufa/auto_retrain_scheduler.py --test

# Vérifier les permissions
chmod +x /app/backend/ufa/auto_retrain_scheduler.py

# Vérifier les dépendances
pip install -r /app/backend/requirements.txt
```

### Aucun réentraînement n'est effectué

```bash
# Vérifier le schedule
cat /app/data/last_retrain.json

# Forcer un réentraînement manuel
rm /app/data/last_retrain.json
python3 /app/backend/ufa/auto_retrain_scheduler.py --test
```

### Performances à 0%

C'est normal si les prédictions ne correspondent pas exactement aux scores réels.
Le système mesure la **prédiction exacte** (score précis), pas la tendance.

Pour améliorer:
1. Augmenter la taille du dataset
2. Affiner les coefficients manuellement
3. Ajouter plus de features au modèle

## 🔒 Sécurité

- Les fichiers de logs ne contiennent pas de données sensibles
- Les coefficients sont sauvegardés localement uniquement
- Pas d'accès externe aux données d'entraînement

## 📚 Références

- [UFA Training System](./backend/ufa/training/trainer.py)
- [League Coefficients](./backend/league_coeff.py)
- [Force Retrain Script](./backend/ufa/force_retrain_all.py)

## 🆘 Support

En cas de problème:
1. Vérifier les logs dans `/app/logs/`
2. Tester en mode manuel avec `--test`
3. Consulter la documentation technique

---

**Version**: 2.0  
**Dernière mise à jour**: 2025-11-10  
**Auteur**: UFA System Team

# 📊 Module de Rapport de Suivi Automatique

## Vue d'ensemble

Le module de rapport de suivi automatique permet de suivre et d'analyser l'activité du système de prédiction de scores. Il génère des rapports détaillés sur les matchs analysés, les bookmakers utilisés, et la qualité des prédictions.

## 🎯 Fonctionnalités

### 1. Statistiques globales
- **Nombre total de matchs** mémorisés
- **Confiance moyenne** de toutes les prédictions
- **Répartition par bookmaker** avec comptage
- **Date de dernière mise à jour** de la mémoire

### 2. Historique des matchs
- Liste des **5 derniers matchs** analysés
- Pour chaque match :
  - Nom du match
  - Bookmaker utilisé
  - Score prédit (top 1)
  - Niveau de confiance
  - Horodatage de l'analyse

### 3. Indicateurs de santé
- État de la mémoire (opérationnel / vide)
- Persistance des données
- Stabilité du système

## 🔌 API Endpoint

### GET `/api/system/report`

Génère et retourne le rapport complet du système.

**Réponse:**
```json
{
  "timestamp": "2025-11-05T17:59:26.123456",
  "last_update": "2025-11-05 17:59:26",
  "statistics": {
    "total_matches": 2,
    "average_confidence": 0.2220,
    "bookmakers_count": 1,
    "bookmakers_distribution": {
      "Bookmaker inconnu": 2
    }
  },
  "recent_matches": [
    {
      "match_id": "kairatintermilan_bookmakerinconnu_2025-11-05",
      "match_name": "Kairat - Inter Milan",
      "bookmaker": "Bookmaker inconnu",
      "confidence": 0.304,
      "top_score": "3-2",
      "analyzed_at": "2025-11-05T17:51:06.123456"
    }
  ],
  "status": "operational",
  "report_text": "..."
}
```

## 🖥️ Utilisation en ligne de commande

### Script Python

Un script de génération de rapport est disponible : `generate_report.py`

**Utilisation de base:**
```bash
python generate_report.py
```

**Avec statistiques détaillées:**
```bash
python generate_report.py --stats
```

**Avec liste complète des matchs récents:**
```bash
python generate_report.py --recent
```

**Export JSON:**
```bash
python generate_report.py --json > rapport.json
```

**Rapport complet:**
```bash
python generate_report.py --stats --recent
```

## 📋 Exemples de sortie

### Rapport de base
```
===============================
📊 RAPPORT DE SUIVI AUTOMATIQUE
===============================

🕒 Dernière mise à jour : 2025-11-05 17:59:26
📁 Matchs mémorisés : 2
📈 Confiance moyenne : 22.2%

🔸 Répartition par bookmaker :
   - Bookmaker inconnu: 2 match(s)

✅ Mémoire fonctionnelle et stable

📋 2 dernier(s) match(s) analysé(s) :
   • Match non détecté
     Score prédit: 3-1 | Confiance: 14.0%
   • Kairat - Inter Milan
     Score prédit: 3-2 | Confiance: 30.4%

===============================
```

## 🔧 Intégration

### Dans le code Python

```python
from matches_memory import generate_system_report

# Générer le rapport
report = generate_system_report()

# Accéder aux statistiques
total_matches = report['statistics']['total_matches']
avg_confidence = report['statistics']['average_confidence']

# Afficher le rapport textuel
print(report['report_text'])
```

### Via l'API REST

```python
import requests

response = requests.get('http://localhost:8001/api/system/report')
report = response.json()

print(f"Total matchs: {report['statistics']['total_matches']}")
print(f"Confiance: {report['statistics']['average_confidence'] * 100:.1f}%")
```

### Via curl

```bash
curl http://localhost:8001/api/system/report | python -m json.tool
```

## 📊 Cas d'usage

### 1. Monitoring quotidien
Générer un rapport chaque jour pour suivre l'activité :
```bash
python generate_report.py --stats > rapport_$(date +%Y%m%d).txt
```

### 2. Surveillance de la qualité
Vérifier la confiance moyenne des prédictions :
```bash
python generate_report.py --stats | grep "Confiance moyenne"
```

### 3. Analyse par bookmaker
Identifier quel bookmaker est le plus utilisé :
```bash
python generate_report.py --stats | grep -A 10 "Distribution par bookmaker"
```

### 4. Export pour analyse
Exporter les données en JSON pour analyse ultérieure :
```bash
python generate_report.py --json > data.json
```

## 🔄 Automatisation

### Cron job quotidien
Ajouter dans crontab pour un rapport quotidien automatique :
```bash
0 8 * * * cd /app && python generate_report.py --stats --recent > /var/log/rapport_$(date +\%Y\%m\%d).txt
```

### Webhook / Notification
Envoyer le rapport par email ou Slack :
```python
import requests

report = requests.get('http://localhost:8001/api/system/report').json()
stats = report['statistics']

# Notification si confiance moyenne < 20%
if stats['average_confidence'] < 0.20:
    send_alert(f"⚠️ Confiance moyenne faible: {stats['average_confidence']*100:.1f}%")
```

## 📈 Métriques surveillées

| Métrique | Description | Seuil recommandé |
|----------|-------------|------------------|
| **total_matches** | Nombre de matchs en mémoire | > 0 |
| **average_confidence** | Confiance moyenne | > 0.30 (30%) |
| **bookmakers_count** | Diversité des sources | > 2 |
| **status** | État du système | "operational" |

## 🎯 Bonnes pratiques

1. **Générer le rapport régulièrement** pour suivre l'évolution
2. **Surveiller la confiance moyenne** - si elle baisse, vérifier la qualité des données
3. **Archiver les rapports** pour analyse historique
4. **Comparer les bookmakers** pour identifier les sources les plus fiables
5. **Nettoyer la mémoire** périodiquement si elle devient trop volumineuse

## 📝 Notes

- Le rapport est généré en temps réel à partir de la mémoire en cours
- Les données sont persistées dans `backend/data/matches_memory.json`
- Le rapport textuel est formaté pour une lecture humaine
- Les données JSON sont structurées pour un traitement automatisé
- Le système ne nécessite aucune configuration supplémentaire

## 🆘 Dépannage

**Erreur de connexion au serveur:**
```
❌ Impossible de se connecter au serveur backend
```
→ Vérifier que le serveur FastAPI est bien démarré sur le port 8001

**Rapport vide:**
```
⚠️ Aucune donnée encore sauvegardée
```
→ Analyser au moins un match pour initialiser la mémoire

**Erreur de lecture du fichier:**
```
⚠️ Erreur de lecture mémoire
```
→ Vérifier les permissions du fichier `matches_memory.json`

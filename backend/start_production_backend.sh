#!/bin/bash
# Script de lancement backend UFAv3 en mode production
# Mode stable sans hot reload pour éviter les redémarrages intempestifs

echo "🚀 Démarrage du backend UFAv3 en mode production (auto-stable)..."

# Arrêt des anciens processus uvicorn s'il y en a
pkill -f "uvicorn server:app" 2>/dev/null
sleep 2

# Créer le dossier logs si nécessaire
mkdir -p /app/logs

# Lancement en mode production (pas de reload par défaut)
cd /app/backend
nohup python3 -m uvicorn server:app \
  --host 0.0.0.0 \
  --port 8001 \
  --log-level info \
  --timeout-keep-alive 75 \
  > /app/logs/backend_production.log 2>&1 &

# Attendre que le processus démarre
sleep 3

# Vérifier que le backend est bien démarré
if pgrep -f "uvicorn server:app" > /dev/null; then
    echo "✅ Backend lancé en mode production (PID: $(pgrep -f 'uvicorn server:app'))"
    echo "📋 Logs: /app/logs/backend_production.log"
    echo "🌐 URL: http://localhost:8001"
else
    echo "❌ Échec du démarrage du backend"
    echo "Consultez les logs : tail -f /app/logs/backend_production.log"
    exit 1
fi

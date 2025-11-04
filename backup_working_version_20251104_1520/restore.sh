#!/bin/bash
# Script de restauration de la version stable du 04/11/2025 15:20

echo "🔄 RESTAURATION VERSION STABLE"
echo "================================"
echo ""

BACKUP_DIR="/app/backup_working_version_20251104_1520"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Erreur: Dossier de backup introuvable!"
    exit 1
fi

echo "📂 Backup trouvé: $BACKUP_DIR"
echo ""

read -p "⚠️  Cette action va écraser les fichiers actuels. Continuer? (o/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Oo]$ ]]; then
    echo "❌ Annulé"
    exit 1
fi

echo ""
echo "📋 Restauration en cours..."

# Backend
echo "  → ocr_engine.py"
cp $BACKUP_DIR/ocr_engine.py /app/backend/

echo "  → predictor.py"
cp $BACKUP_DIR/predictor.py /app/backend/

echo "  → learning.py"
cp $BACKUP_DIR/learning.py /app/backend/

echo "  → server.py"
cp $BACKUP_DIR/server.py /app/backend/

echo "  → requirements.txt"
cp $BACKUP_DIR/requirements.txt /app/backend/

# Frontend
echo "  → App.js"
cp $BACKUP_DIR/App.js /app/frontend/src/

echo "  → package.json"
cp $BACKUP_DIR/package.json /app/frontend/

echo ""
echo "🔄 Redémarrage des services..."
sudo supervisorctl restart all

sleep 5

echo ""
echo "✅ RESTAURATION TERMINÉE"
echo ""
echo "Vérification:"
curl -s http://localhost:8001/api/health | jq .

echo ""
echo "📊 Status:"
sudo supervisorctl status | grep -E "(backend|frontend)"

echo ""
echo "✅ Version stable restaurée avec succès!"

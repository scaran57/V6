#!/bin/bash

echo "==========================================="
echo "      🚀 EMERGENT AUTO-START SYSTEM       "
echo "==========================================="

# 1) Vérification Node.js
if ! command -v node &> /dev/null
then
    echo "❌ Node.js non détecté ! Installation obligatoire."
    exit 1
else
    echo "✔ Node.js détecté : $(node -v)"
fi

# 2) Vérification Python
if ! command -v python3 &> /dev/null
then
    echo "❌ Python3 non détecté !"
    exit 1
else
    echo "✔ Python détecté : $(python3 --version)"
    fi

# 3) Démarrage BACKEND
echo "-------------------------------------------"
echo "📦 Installation dépendances backend..."
cd /app || exit

pip install -r requirements.txt --quiet

echo "▶ Démarrage BACKEND (FastAPI) sur port 8001..."
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload > backend.log 2>&1 &

sleep 2

# 4) Démarrage FRONTEND
echo "-------------------------------------------"
echo "📦 Installation dépendances frontend..."
cd /app/frontend || exit

npm install --silent

echo "▶ Démarrage FRONTEND (React) sur port 3000..."
nohup npm start > frontend.log 2>&1 &

sleep 3

# 5) Infos utilisateur
echo "-------------------------------------------"
echo "🎉 Le système EMERGENT est lancé !"
echo "-------------------------------------------"
echo "Backend : http://localhost:8001"
echo "Frontend : http://localhost:3000"
echo "Logs backend : /app/backend.log"
echo "Logs frontend : /app/frontend.log"
echo "-------------------------------------------"
echo "✨ Vous pouvez utiliser votre dashboard immédiatement !"
echo "==========================================="

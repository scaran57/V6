#!/bin/bash
# Script d'installation automatique de Tesseract OCR
# S'exécute au démarrage du backend

echo "🔍 Vérification de Tesseract..."

if ! command -v tesseract &> /dev/null; then
    echo "📦 Tesseract non trouvé, installation en cours..."
    
    # Installation silencieuse
    apt-get update -qq > /dev/null 2>&1
    apt-get install -y -qq tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng tesseract-ocr-spa > /dev/null 2>&1
    
    if command -v tesseract &> /dev/null; then
        echo "✅ Tesseract $(tesseract --version 2>&1 | head -1) installé avec succès"
    else
        echo "❌ Erreur lors de l'installation de Tesseract"
        exit 1
    fi
else
    echo "✅ Tesseract déjà installé : $(tesseract --version 2>&1 | head -1)"
fi

echo "🚀 Lancement du backend..."

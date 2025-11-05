import requests
import json
import sys

# URL de l'API
backend_url = "http://localhost:8001"
api_url = f"{backend_url}/api/analyze"

# Image de test
image_path = "/app/backend/test_bookmaker_v2.jpg"

print(f"🧪 Test d'extraction avec: {image_path}\n")

try:
    with open(image_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(api_url, files=files, timeout=60)
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Réponse API reçue avec succès!\n")
        print(f"📊 Match: {data.get('matchName', 'Non détecté')}")
        print(f"🎰 Bookmaker: {data.get('bookmaker', 'Non détecté')}")
        print(f"🏆 Score le plus probable: {data.get('mostProbableScore', 'N/A')}")
        print(f"🎯 Confiance: {data.get('confidence', 0) * 100:.1f}%")
        print(f"\n📈 Top 3:")
        for idx, item in enumerate(data.get('top3', [])[:3], 1):
            print(f"  {idx}. {item['score']} - {item['probability']}%")
    else:
        print(f"❌ Erreur: {response.status_code}")
        print(response.text)
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Erreur lors du test: {str(e)}")
    sys.exit(1)

print("\n✅ Test terminé avec succès!")

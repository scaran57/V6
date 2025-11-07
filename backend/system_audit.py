# /app/backend/system_audit.py
import os, json, time, importlib.util
from datetime import datetime

AUDIT_REPORT = {
    "timestamp": datetime.utcnow().isoformat(),
    "modules_found": [],
    "recent_changes": [],
    "dependencies": [],
    "issues": [],
    "summary": {},
}

# --- 1️⃣ Vérification des modules essentiels ---
core_modules = [
    "learning.py",
    "league_fetcher.py",
    "league_coeff.py",
    "league_updater.py",
    "league_scheduler.py",
    "score_predictor.py",
    "ocr_engine.py",
    "server.py",
]
for m in core_modules:
    path = f"/app/backend/{m}"
    if os.path.exists(path):
        AUDIT_REPORT["modules_found"].append(m)
    else:
        AUDIT_REPORT["issues"].append(f"❌ Module manquant : {m}")

# --- 2️⃣ Recherche de doublons / surcouches d'agents ---
for root, _, files in os.walk("/app/backend"):
    for f in files:
        if f.endswith(".py"):
            if f.count("_copy") or f.count("_backup") or f.count("_old"):
                AUDIT_REPORT["issues"].append(f"⚠️ Fichier redondant : {f}")

# --- 3️⃣ Liste des fichiers modifiés récemment (derniers 3 jours) ---
cutoff = time.time() - (3 * 24 * 3600)
for root, _, files in os.walk("/app"):
    for f in files:
        if f.endswith((".py", ".js", ".jsx", ".json")):
            p = os.path.join(root, f)
            try:
                if os.path.getmtime(p) > cutoff:
                    AUDIT_REPORT["recent_changes"].append(p)
            except:
                pass

# --- 4️⃣ Vérification de la cohérence des dépendances ---
try:
    with open("/app/backend/requirements.txt") as f:
        deps = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        AUDIT_REPORT["dependencies"] = deps
        required_deps = ["requests", "beautifulsoup4", "lxml", "Pillow", "pytesseract"]
        for dep in required_deps:
            found = any(dep.lower() in d.lower() for d in deps)
            if not found:
                AUDIT_REPORT["issues"].append(f"⚠️ Dépendance potentiellement manquante : {dep}")
except FileNotFoundError:
    AUDIT_REPORT["issues"].append("❌ Fichier requirements.txt introuvable")

# --- 5️⃣ Vérification des fichiers de données ---
data_paths = [
    "/app/data/learning_meta.json",
    "/app/data/learning_events.jsonl",
    "/app/data/teams_data.json",
    "/app/data/leagues/LaLiga.json",
    "/app/data/leagues/PremierLeague.json",
    "/app/data/leagues/ChampionsLeague.json",
    "/app/data/leagues/EuropaLeague.json",
]
for p in data_paths:
    if not os.path.exists(p):
        AUDIT_REPORT["issues"].append(f"⚠️ Donnée manquante : {p}")
    else:
        # Vérifier la taille
        size = os.path.getsize(p)
        if size == 0:
            AUDIT_REPORT["issues"].append(f"⚠️ Fichier vide : {p}")

# --- 6️⃣ Détection de surcouche agent/AI ---
for root, _, files in os.walk("/app"):
    for f in files:
        if f.lower().startswith("agent") and f.endswith(".py") and f != "agent.py":
            AUDIT_REPORT["issues"].append(f"⚠️ Fichier agent supplémentaire : {f} dans {root}")

# --- 7️⃣ Vérification des composants frontend ---
frontend_components = [
    "/app/frontend/src/components/MatchAnalyzer.jsx",
    "/app/frontend/src/AppRouter.js",
    "/app/frontend/src/App.js",
]
for comp in frontend_components:
    if os.path.exists(comp):
        AUDIT_REPORT["modules_found"].append(f"frontend:{os.path.basename(comp)}")
    else:
        AUDIT_REPORT["issues"].append(f"⚠️ Composant frontend manquant : {comp}")

# --- 8️⃣ Vérification de la documentation ---
docs = [
    "/app/README.md",
    "/app/INTEGRATION_LEAGUES_COEFFICIENT.md",
    "/app/VERIFICATION_COEFFICIENTS_UEFA.md",
    "/app/VERIFICATION_COMPLETE_SYSTEME.md",
]
docs_found = []
for doc in docs:
    if os.path.exists(doc):
        docs_found.append(os.path.basename(doc))
    
AUDIT_REPORT["documentation"] = docs_found

# --- 9️⃣ Résumé global ---
AUDIT_REPORT["summary"] = {
    "modules_ok": len([m for m in AUDIT_REPORT["modules_found"] if not m.startswith("frontend:")]),
    "frontend_components": len([m for m in AUDIT_REPORT["modules_found"] if m.startswith("frontend:")]),
    "issues_found": len(AUDIT_REPORT["issues"]),
    "recent_files": len(AUDIT_REPORT["recent_changes"]),
    "dependencies_count": len(AUDIT_REPORT["dependencies"]),
    "documentation_files": len(docs_found),
    "health_status": "✅ EXCELLENT" if len(AUDIT_REPORT["issues"]) == 0 else 
                     "⚠️ ATTENTION REQUISE" if len(AUDIT_REPORT["issues"]) < 5 else 
                     "❌ PROBLÈMES CRITIQUES"
}

# --- 🔟 Sauvegarde du rapport ---
output_path = "/app/data/system_audit_report.json"
with open(output_path, "w") as f:
    json.dump(AUDIT_REPORT, f, indent=2)

print("=" * 80)
print("✅ RAPPORT D'AUDIT SYSTÈME GÉNÉRÉ")
print("=" * 80)
print(f"\n📄 Rapport sauvegardé: {output_path}\n")
print("📊 RÉSUMÉ:")
print(f"  - Modules backend trouvés: {AUDIT_REPORT['summary']['modules_ok']}")
print(f"  - Composants frontend: {AUDIT_REPORT['summary']['frontend_components']}")
print(f"  - Fichiers de documentation: {AUDIT_REPORT['summary']['documentation_files']}")
print(f"  - Dépendances: {AUDIT_REPORT['summary']['dependencies_count']}")
print(f"  - Fichiers modifiés (3 jours): {AUDIT_REPORT['summary']['recent_files']}")
print(f"  - Problèmes détectés: {AUDIT_REPORT['summary']['issues_found']}")
print(f"\n🏥 État de santé: {AUDIT_REPORT['summary']['health_status']}")

if AUDIT_REPORT["issues"]:
    print("\n⚠️ PROBLÈMES DÉTECTÉS:")
    for issue in AUDIT_REPORT["issues"]:
        print(f"  {issue}")
else:
    print("\n✅ Aucun problème détecté!")

print("\n" + "=" * 80)

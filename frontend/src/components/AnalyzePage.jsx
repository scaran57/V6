import React, { useState } from "react";
import axios from "axios";

export default function AnalyzePage() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [disableCache, setDisableCache] = useState(false);
  const [useVisionOcr, setUseVisionOcr] = useState(true); // ✅ Activé par défaut !
  const [manualMatchName, setManualMatchName] = useState("");

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleAnalyze = async () => {
    if (!file) {
      alert("Veuillez sélectionner une image de bookmaker !");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const backendUrl = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";
      const url = `${backendUrl}/api/analyze${
        disableCache ? "?disable_cache=true" : ""
      }`;

      const res = await axios.post(url, formData);
      setResult(res.data);
    } catch (err) {
      console.error(err);
      alert("Erreur lors de l'analyse !");
    } finally {
      setLoading(false);
    }
  };

  const clearCache = async () => {
    if (!window.confirm("Voulez-vous vraiment vider le cache des analyses ?")) {
      return;
    }
    
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";
      await axios.delete(`${backendUrl}/api/admin/clear-analysis-cache`);
      alert("✅ Cache vidé avec succès !");
    } catch (err) {
      console.error(err);
      alert("Erreur lors du vidage du cache !");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">
          ⚽ Analyse de Match - Mode Test
        </h1>

        {/* Carte de Configuration */}
        <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
          <h2 className="text-xl font-semibold text-gray-700 mb-4">
            📤 Upload & Configuration
          </h2>

          <div className="space-y-4">
            {/* Upload de fichier */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Image du bookmaker
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-full file:border-0
                  file:text-sm file:font-semibold
                  file:bg-indigo-50 file:text-indigo-700
                  hover:file:bg-indigo-100
                  cursor-pointer"
              />
            </div>

            {/* Champ de saisie manuelle du nom du match */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                Nom du match (optionnel - si l'OCR échoue)
              </label>
              <input
                type="text"
                value={manualMatchName}
                onChange={(e) => setManualMatchName(e.target.value)}
                placeholder="Ex: PSG - Marseille"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500">
                ℹ️ Saisissez le nom si l'extraction automatique est incorrecte
              </p>
            </div>

            {/* Switch pour désactiver le cache */}
            <div className="flex items-center space-x-3 p-3 bg-yellow-50 rounded-lg border border-yellow-200">
              <input
                type="checkbox"
                id="disableCache"
                checked={disableCache}
                onChange={(e) => setDisableCache(e.target.checked)}
                className="w-4 h-4 text-indigo-600 bg-gray-100 border-gray-300 rounded focus:ring-indigo-500"
              />
              <label htmlFor="disableCache" className="text-sm text-gray-700 flex items-center">
                <span className="mr-2">🔄</span>
                <span>
                  <strong>Mode Test :</strong> Recalculer entièrement (désactiver le cache)
                </span>
              </label>
            </div>

            {disableCache && (
              <div className="bg-blue-50 border-l-4 border-blue-400 p-4 text-sm text-blue-700">
                <p className="font-semibold">ℹ️ Cache désactivé</p>
                <p>Chaque analyse déclenchera un nouveau calcul complet (OCR + prédiction)</p>
              </div>
            )}

            {/* Boutons d'action */}
            <div className="flex space-x-3">
              <button
                onClick={handleAnalyze}
                disabled={loading || !file}
                className={`flex-1 py-3 px-6 rounded-lg font-semibold text-white transition-all
                  ${loading || !file
                    ? "bg-gray-300 cursor-not-allowed"
                    : "bg-indigo-600 hover:bg-indigo-700 shadow-md hover:shadow-lg"
                  }`}
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin h-5 w-5 mr-3 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Analyse en cours...
                  </span>
                ) : (
                  "🎯 Analyser"
                )}
              </button>

              <button
                onClick={clearCache}
                className="py-3 px-6 rounded-lg font-semibold text-gray-700 bg-white border-2 border-gray-300 hover:bg-gray-50 hover:border-gray-400 transition-all"
              >
                🧹 Vider le cache
              </button>
            </div>
          </div>
        </div>

        {/* Résultats */}
        {result && (
          <div className="bg-white rounded-lg shadow-md p-6 space-y-4 animate-fadeIn">
            <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
              <span className="mr-2">📊</span>
              Résultat de l'analyse
            </h2>

            {/* Badge source + Message de debug */}
            <div className="mb-4 space-y-3">
              <div className="flex flex-wrap gap-2">
                {result.fromMemory === true && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                    <span className="mr-1">🧠</span>
                    Récupéré depuis le cache
                  </span>
                )}
                {result.fromMemory === false && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                    <span className="mr-1">🔁</span>
                    Nouveau calcul complet (OCR + Prédiction)
                  </span>
                )}
                {result.cacheDisabled && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800">
                    <span className="mr-1">⚠️</span>
                    Cache désactivé
                  </span>
                )}
              </div>
              
              {/* Message explicatif détaillé */}
              {result.debug && (
                <div className="bg-gray-50 border-l-4 border-gray-400 p-3 text-sm text-gray-700">
                  <p className="flex items-start">
                    <span className="mr-2 mt-0.5">ℹ️</span>
                    <span><strong>Info:</strong> {result.debug}</span>
                  </p>
                </div>
              )}
            </div>

            {/* Informations du match */}
            {(manualMatchName || 
             (result.matchName && 
              result.matchName !== "Match non détecté" && 
              !result.matchName.startsWith("League -") &&
              !result.matchName.includes("CANAI"))) && (
              <div className="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-lg p-4 border border-indigo-200">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-lg">⚽</span>
                  <span className="text-sm font-semibold text-gray-700">Match:</span>
                  <span className="text-sm font-bold text-indigo-700">
                    {manualMatchName || result.matchName}
                  </span>
                  {manualMatchName && (
                    <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">✓ Saisi manuellement</span>
                  )}
                </div>
                {result.bookmaker && result.bookmaker !== "Bookmaker inconnu" && (
                  <div className="flex items-center space-x-2">
                    <span className="text-lg">🎰</span>
                    <span className="text-sm font-semibold text-gray-700">Bookmaker:</span>
                    <span className="text-sm text-gray-600">{result.bookmaker}</span>
                  </div>
                )}
              </div>
            )}

            {/* Score prédit */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
                <div className="text-sm text-gray-600 mb-1">Score le plus probable</div>
                <div className="text-3xl font-bold text-green-700">
                  {result.mostProbableScore || "N/A"}
                </div>
              </div>

              <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
                <div className="text-sm text-gray-600 mb-1">Niveau de confiance</div>
                <div className="text-3xl font-bold text-purple-700">
                  {result.confidence ? (result.confidence * 100).toFixed(1) + "%" : "N/A"}
                </div>
              </div>
            </div>

            {/* Top 3 */}
            {result.top3 && result.top3.length > 0 && (
              <div>
                <h3 className="font-semibold text-gray-800 mb-3 flex items-center">
                  <span className="mr-2">🏆</span>
                  Top 3 des Scores
                </h3>
                <div className="space-y-2">
                  {result.top3.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                      <div className="flex items-center space-x-3">
                        <span className="text-2xl">
                          {idx === 0 ? "🥇" : idx === 1 ? "🥈" : "🥉"}
                        </span>
                        <span className="font-semibold text-gray-800">
                          {item.score}
                        </span>
                      </div>
                      <span className="text-lg font-bold text-indigo-600">
                        {typeof item.probability === 'number' 
                          ? item.probability.toFixed(2) 
                          : item.probability}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Métadonnées techniques */}
            {result.matchId && (
              <details className="text-xs text-gray-500 mt-4">
                <summary className="cursor-pointer hover:text-gray-700">
                  🔧 Informations techniques
                </summary>
                <div className="mt-2 p-3 bg-gray-50 rounded">
                  <p><strong>Match ID:</strong> {result.matchId}</p>
                  {result.analyzedAt && (
                    <p><strong>Analysé le:</strong> {new Date(result.analyzedAt).toLocaleString('fr-FR')}</p>
                  )}
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}

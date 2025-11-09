// /app/frontend/src/components/UFAUnifiedAnalyzer.jsx
import React, { useState } from "react";

export default function UFAUnifiedAnalyzer() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleUpload = async () => {
    if (!file) {
      alert("Sélectionnez d'abord une image FDJ ou bookmaker !");
      return;
    }
    
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("persist_cache", "true");

    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/unified/analyze`, {
        method: "POST",
        body: formData,
      });
      
      const data = await res.json();
      
      if (data.success) {
        setResult(data);
      } else {
        setError(data.error || "Erreur inconnue");
      }
    } catch (err) {
      setError("Erreur pendant l'analyse : " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            🎯 Analyser & Sauvegarder (UFA)
          </h1>
          <p className="text-gray-600">
            Analysez vos paris sportifs avec les coefficients de ligue
          </p>
          <div className="mt-4 inline-flex items-center px-4 py-2 bg-green-100 text-green-800 rounded-full text-sm font-medium">
            ✅ Sauvegarde automatique | ⚽ Coefficients toujours appliqués
          </div>
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-2xl shadow-xl p-8 mb-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                📸 Choisissez une image
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files[0])}
                className="block w-full text-sm text-gray-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-full file:border-0
                  file:text-sm file:font-semibold
                  file:bg-blue-50 file:text-blue-700
                  hover:file:bg-blue-100
                  cursor-pointer"
              />
              {file && (
                <p className="mt-2 text-sm text-green-600">
                  ✅ {file.name} ({(file.size / 1024).toFixed(1)} KB)
                </p>
              )}
            </div>

            <button
              onClick={handleUpload}
              disabled={loading || !file}
              className={`w-full py-3 px-6 rounded-xl font-semibold text-white transition-all shadow-lg
                ${loading || !file
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 transform hover:scale-105'
                }`}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Analyse en cours...
                </span>
              ) : (
                '🔍 Lancer l\'analyse'
              )}
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-lg mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Erreur d'analyse</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Results Display */}
        {result && result.success && (
          <div className="space-y-4">
            {/* Match Info Card */}
            <div className="bg-white rounded-2xl shadow-xl p-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                ⚽ Informations du Match
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Match</p>
                  <p className="text-lg font-semibold text-gray-900">{result.matchName}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Ligue</p>
                  <p className="text-lg font-semibold text-gray-900">{result.league}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Coefficients appliqués</p>
                  <p className="text-lg font-semibold">
                    {result.leagueCoeffsApplied ? (
                      <span className="text-green-600">✅ Oui</span>
                    ) : (
                      <span className="text-red-600">❌ Non</span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Sauvegardé</p>
                  <p className="text-lg font-semibold">
                    {result.savedToCache ? (
                      <span className="text-green-600">✅ Oui</span>
                    ) : (
                      <span className="text-gray-600">❌ Non</span>
                    )}
                  </p>
                </div>
              </div>
            </div>

            {/* Most Probable Score */}
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-2xl shadow-xl p-6 border-2 border-green-200">
              <h3 className="text-xl font-bold text-gray-900 mb-2">
                🏆 Score le plus probable
              </h3>
              <div className="flex items-center justify-center">
                <div className="text-6xl font-bold text-green-700">
                  {result.mostProbableScore}
                </div>
              </div>
              {result.confidence !== undefined && (
                <p className="text-center mt-3 text-gray-700">
                  Confiance : <span className="font-semibold">{(result.confidence * 100).toFixed(1)}%</span>
                </p>
              )}
            </div>

            {/* Top 3 Scores */}
            {result.top3 && result.top3.length > 0 && (
              <div className="bg-white rounded-2xl shadow-xl p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">
                  📊 Top 3 des scores probables
                </h3>
                <div className="space-y-3">
                  {result.top3.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition"
                    >
                      <div className="flex items-center space-x-4">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-white
                          ${idx === 0 ? 'bg-yellow-500' : idx === 1 ? 'bg-gray-400' : 'bg-orange-400'}`}>
                          {idx + 1}
                        </div>
                        <span className="text-2xl font-bold text-gray-900">
                          {item.score}
                        </span>
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-bold text-blue-600">
                          {item.probability.toFixed(2)}%
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="bg-gray-50 rounded-xl p-4 text-sm text-gray-600">
              <p>
                🕐 Analysé le : {new Date(result.timestamp).toLocaleString('fr-FR')}
              </p>
              {result.info && (
                <div className="mt-2 space-y-1">
                  <p>🏠 Équipe domicile : {result.info.home_team}</p>
                  <p>✈️ Équipe extérieur : {result.info.away_team}</p>
                  <p>🏆 Ligue : {result.info.league}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

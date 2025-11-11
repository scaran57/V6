import React, { useState } from "react";
import UFAUnifiedAnalyzer from "./components/UFAUnifiedAnalyzer";
import TestMode from "./TestMode";
import MatchAnalyzer from "./components/MatchAnalyzer";
import UfaDashboard from "./components/UfaDashboard";

function AppRouter() {
  const [mode, setMode] = useState("unified"); // "unified", "test", ou "analyzer"

  return (
    <div>
      {/* Barre de navigation pour basculer entre les modes */}
      <nav className="bg-gray-800 text-white p-4 shadow-lg">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold">⚽ Prédicteur de Match UFA</h1>
          <div className="flex space-x-2">
            <button
              onClick={() => setMode("unified")}
              className={`px-6 py-3 rounded-xl font-bold transition-all shadow-lg ${
                mode === "unified"
                  ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white transform scale-105"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              🎯 Analyser & Sauvegarder (UFA)
            </button>
            <button
              onClick={() => setMode("test")}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                mode === "test"
                  ? "bg-yellow-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              🧪 Mode Test (Ancien)
            </button>
            <button
              onClick={() => setMode("analyzer")}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                mode === "analyzer"
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              🏆 Analyzer (Ancien)
            </button>
            <button
              onClick={() => setMode("dashboard")}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                mode === "dashboard"
                  ? "bg-green-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              📊 Dashboard UFAv3
            </button>
          </div>
        </div>
      </nav>

      {/* Message informatif */}
      {(mode === "test" || mode === "analyzer") && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 m-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-yellow-700">
                ⚠️ Mode ancien conservé pour compatibilité. 
                Utilisez <strong>"Analyser & Sauvegarder (UFA)"</strong> pour bénéficier de toutes les fonctionnalités :
                coefficients automatiques, sauvegarde, pipeline UFA complet.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Contenu selon le mode */}
      <div>
        {mode === "unified" ? (
          <UFAUnifiedAnalyzer />
        ) : mode === "test" ? (
          <TestMode />
        ) : mode === "analyzer" ? (
          <MatchAnalyzer />
        ) : mode === "dashboard" ? (
          <UfaDashboard />
        ) : null}
      </div>
    </div>
  );
}

export default AppRouter;

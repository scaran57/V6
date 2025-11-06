import React, { useState } from "react";
import App from "./App";
import TestMode from "./TestMode";

function AppRouter() {
  const [mode, setMode] = useState("production"); // "production" ou "test"

  return (
    <div>
      {/* Barre de navigation pour basculer entre les modes */}
      <nav className="bg-gray-800 text-white p-4 shadow-lg">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold">⚽ Prédicteur de Match</h1>
          <div className="flex space-x-2">
            <button
              onClick={() => setMode("production")}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                mode === "production"
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              🎯 Mode Production
            </button>
            <button
              onClick={() => setMode("test")}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                mode === "test"
                  ? "bg-yellow-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              🧪 Mode Test
            </button>
          </div>
        </div>
      </nav>

      {/* Contenu selon le mode */}
      <div>
        {mode === "production" ? <App /> : <TestMode />}
      </div>
    </div>
  );
}

export default AppRouter;

import React from "react";
import AnalyzePage from "./components/AnalyzePage";

function TestMode() {
  return (
    <div>
      <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4 mb-4">
        <p className="font-bold">🧪 Mode Test Activé</p>
        <p className="text-sm">
          Cette page permet de tester l'analyse avec contrôle du cache. 
          Utilisez le switch pour désactiver le cache et forcer un nouveau calcul à chaque fois.
        </p>
      </div>
      <AnalyzePage />
    </div>
  );
}

export default TestMode;

import { useState } from "react";
import "@/App.css";
import axios from "axios";
import { Upload, Brain, TrendingUp, BarChart3 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  
  // Pour l'apprentissage
  const [showLearning, setShowLearning] = useState(false);
  const [predictedScore, setPredictedScore] = useState("");
  const [realScore, setRealScore] = useState("");
  
  // Pour la saisie manuelle du nom du match
  const [manualMatchName, setManualMatchName] = useState("");

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
      setError(null);
      setResult(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
      setError(null);
      setResult(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const analyzeImage = async () => {
    if (!selectedFile) {
      setError("Veuillez sélectionner une image");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post(`${API}/analyze`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // 60 secondes timeout
      });

      setResult(response.data);
      setPredictedScore(response.data.mostProbableScore);
    } catch (err) {
      if (err.code === 'ECONNABORTED') {
        setError("L'analyse prend trop de temps. Veuillez réessayer avec une image plus claire.");
      } else {
        setError(err.response?.data?.error || "Erreur lors de l'analyse de l'image");
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const submitLearning = async () => {
    if (!predictedScore || !realScore) {
      alert("Veuillez remplir les deux scores");
      return;
    }

    // Validation du format
    const scorePattern = /^\d{1,2}-\d{1,2}$/;
    if (!scorePattern.test(predictedScore) && predictedScore.toLowerCase() !== "autre") {
      alert("Format du score prédit invalide. Utilisez le format X-Y (ex: 2-1)");
      return;
    }
    if (!scorePattern.test(realScore)) {
      alert("Format du score réel invalide. Utilisez le format X-Y (ex: 2-1)");
      return;
    }

    const formData = new FormData();
    formData.append('predicted', predictedScore);
    formData.append('real', realScore);

    try {
      const response = await axios.post(`${API}/learn`, formData);
      if (response.data.success) {
        if (response.data.skipped) {
          alert(`⚠️ ${response.data.message}`);
        } else {
          alert(`✅ ${response.data.message}\nNouvelle différence attendue: ${response.data.newDiffExpected || 'N/A'}`);
        }
        setShowLearning(false);
        setRealScore("");
      } else {
        alert("❌ Erreur lors de l'apprentissage");
      }
    } catch (err) {
      alert("❌ Erreur lors de l'apprentissage: " + (err.response?.data?.error || err.message));
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Brain className="w-10 h-10 text-indigo-600" />
              <h1 className="text-3xl font-bold text-gray-900">Prédicteur de Score</h1>
            </div>
            <button
              onClick={() => setShowLearning(!showLearning)}
              className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              data-testid="toggle-learning-btn"
            >
              <TrendingUp className="w-5 h-5" />
              <span>Apprentissage</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid md:grid-cols-2 gap-8">
          {/* Zone d'upload */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
              <Upload className="w-6 h-6 mr-2 text-indigo-600" />
              Upload Image Bookmaker
            </h2>
            
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              className="border-2 border-dashed border-indigo-300 rounded-lg p-8 text-center hover:border-indigo-500 transition-colors cursor-pointer"
              data-testid="upload-zone"
            >
              {preview ? (
                <div>
                  <img src={preview} alt="Preview" className="max-h-64 mx-auto rounded-lg shadow-md" />
                  <p className="mt-4 text-sm text-gray-600">{selectedFile?.name}</p>
                </div>
              ) : (
                <div>
                  <Upload className="w-16 h-16 mx-auto text-indigo-400 mb-4" />
                  <p className="text-gray-600 mb-2">Glissez votre image ici</p>
                  <p className="text-sm text-gray-500">ou cliquez pour sélectionner</p>
                </div>
              )}
              <input
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
                id="file-input"
              />
            </div>

            <label htmlFor="file-input" className="block mt-4">
              <div className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors text-center cursor-pointer">
                Choisir une image
              </div>
            </label>

            {/* Champ de saisie manuelle du nom du match */}
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Nom du match (optionnel - si l'OCR échoue)
              </label>
              <input
                type="text"
                value={manualMatchName}
                onChange={(e) => setManualMatchName(e.target.value)}
                placeholder="Ex: PSG - Marseille"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">
                ℹ️ Saisissez le nom si l'extraction automatique est incorrecte
              </p>
            </div>

            <button
              onClick={analyzeImage}
              disabled={!selectedFile || loading}
              className="w-full mt-4 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-semibold"
              data-testid="analyze-btn"
            >
              {loading ? "Analyse en cours..." : "Analyser & Prédire"}
            </button>

            {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg" data-testid="error-message">
                <p className="text-red-600 text-sm">{error}</p>
              </div>
            )}
          </div>

          {/* Résultats */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
              <BarChart3 className="w-6 h-6 mr-2 text-green-600" />
              Résultats de Prédiction
            </h2>

            {result ? (
              <div className="space-y-6">
                {/* Score Principal avec Confiance */}
                <div className="bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-lg p-6 shadow-lg" data-testid="prediction-result">
                  <p className="text-sm font-medium mb-2">Score le Plus Probable</p>
                  <p className="text-5xl font-bold mb-3" data-testid="most-probable-score">{result.mostProbableScore}</p>
                  {result.probabilities[result.mostProbableScore] && (
                    <p className="text-lg opacity-90">
                      Probabilité: {result.probabilities[result.mostProbableScore]}%
                    </p>
                  )}
                  
                  {/* Jauge de Confiance */}
                  {result.confidence !== undefined && (
                    <div className="mt-4 pt-4 border-t border-white/30">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Niveau de Confiance</span>
                        <span className="text-lg font-bold">{(result.confidence * 100).toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-white/30 rounded-full h-3">
                        <div
                          className={`h-3 rounded-full transition-all duration-700 ${
                            result.confidence >= 0.7 ? 'bg-green-300' :
                            result.confidence >= 0.4 ? 'bg-yellow-300' : 'bg-red-300'
                          }`}
                          style={{ width: `${result.confidence * 100}%` }}
                        ></div>
                      </div>
                      <div className="mt-2 flex items-center space-x-2">
                        {result.confidence >= 0.7 ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            🟢 Confiance Élevée
                          </span>
                        ) : result.confidence >= 0.4 ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                            🟠 Confiance Moyenne
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                            🔴 Confiance Faible
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Interprétation et Recommandations */}
                {result.confidence !== undefined && (
                  <div className={`p-4 rounded-lg border-l-4 ${
                    result.confidence >= 0.7 ? 'bg-green-50 border-green-500' :
                    result.confidence >= 0.4 ? 'bg-yellow-50 border-yellow-500' : 'bg-red-50 border-red-500'
                  }`}>
                    <h4 className="font-semibold text-gray-800 mb-2">
                      {result.confidence >= 0.7 ? '✅ Interprétation' :
                       result.confidence >= 0.4 ? '⚠️ Interprétation' : '❌ Interprétation'}
                    </h4>
                    <p className="text-sm text-gray-700 mb-3">
                      {result.confidence >= 0.7 ? 
                        'Prédiction très fiable. Un score domine clairement, ce qui indique une forte probabilité pour ce résultat.' :
                       result.confidence >= 0.4 ?
                        'Prédiction modérée. Plusieurs scores possibles, mais avec quelques favoris qui se dégagent.' :
                        'Prédiction incertaine. Match très ouvert avec de nombreuses possibilités. Aucun favori clair ne se dégage.'}
                    </p>
                    <div className="bg-white/50 p-3 rounded text-sm">
                      <strong className="text-gray-800">💡 Recommandation:</strong>
                      <p className="text-gray-700 mt-1">
                        {result.confidence >= 0.7 ?
                          'Vous pouvez vous fier à cette prédiction avec confiance. Le score indiqué a une forte probabilité de se réaliser.' :
                         result.confidence >= 0.4 ?
                          'Restez prudent. Considérez les autres scores du Top 3 et envisagez des paris combinés.' :
                          'Prudence maximale recommandée. Évitez les paris importants sur un seul score. Match très imprévisible.'}
                      </p>
                    </div>
                  </div>
                )}

                {/* Informations du Match et Bookmaker */}
                {(result.matchName || result.bookmaker || manualMatchName) && (
                  <div className="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-lg p-4 border border-indigo-200">
                    {/* Afficher le nom manuel en priorité, sinon le nom détecté si valide */}
                    {(manualMatchName || 
                     (result.matchName && 
                      result.matchName !== "Match non détecté" && 
                      !result.matchName.startsWith("League -") &&
                      !result.matchName.includes("CANAI"))) && (
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
                    )}
                    {result.bookmaker && result.bookmaker !== "Bookmaker inconnu" && (
                      <div className="flex items-center space-x-2">
                        <span className="text-lg">🎰</span>
                        <span className="text-sm font-semibold text-gray-700">Bookmaker:</span>
                        <span className="text-sm text-gray-600">{result.bookmaker}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Top 3 des Scores */}
                {result.top3 && result.top3.length > 0 && (
                  <div>
                    <h3 className="font-semibold text-gray-800 mb-3 flex items-center">
                      🏆 Top 3 des Scores
                    </h3>
                    <div className="space-y-2">
                      {result.top3.map((item, idx) => (
                        <div
                          key={idx}
                          className={`flex items-center justify-between p-4 rounded-lg border-2 ${
                            idx === 0 ? 'bg-yellow-50 border-yellow-400' :
                            idx === 1 ? 'bg-gray-50 border-gray-300' :
                            'bg-orange-50 border-orange-300'
                          }`}
                        >
                          <div className="flex items-center space-x-3">
                            <span className="text-2xl font-bold">
                              {idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉'}
                            </span>
                            <span className="text-xl font-bold text-gray-800">{item.score}</span>
                          </div>
                          <div className="text-right">
                            <div className="text-2xl font-bold text-indigo-600">
                              {item.probability}%
                            </div>
                            <div className="text-xs text-gray-500">probabilité</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Toutes les Probabilités (repliable) */}
                <details className="mt-4">
                  <summary className="cursor-pointer font-semibold text-gray-700 hover:text-indigo-600 transition-colors">
                    📊 Voir toutes les probabilités ({Object.keys(result.probabilities).length} scores)
                  </summary>
                  <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                    {Object.entries(result.probabilities)
                      .sort((a, b) => b[1] - a[1])
                      .map(([score, prob]) => (
                        <div key={score} className="flex items-center justify-between p-2 bg-gray-50 rounded" data-testid={`probability-${score}`}>
                          <span className="font-medium text-gray-800 text-sm">{score}</span>
                          <div className="flex items-center space-x-3">
                            <div className="w-24 bg-gray-200 rounded-full h-1.5">
                              <div
                                className="bg-indigo-600 h-1.5 rounded-full transition-all duration-500"
                                style={{ width: `${prob}%` }}
                              ></div>
                            </div>
                            <span className="text-xs font-semibold text-gray-600 w-12 text-right">
                              {prob}%
                            </span>
                          </div>
                        </div>
                      ))}
                  </div>
                </details>

                {/* Cotes Extraites (repliable) */}
                {result.extractedScores && result.extractedScores.length > 0 && (
                  <details>
                    <summary className="cursor-pointer font-semibold text-gray-700 hover:text-indigo-600 transition-colors">
                      🎯 Cotes extraites ({result.extractedScores.length} scores)
                    </summary>
                    <div className="mt-3 p-4 bg-blue-50 rounded-lg max-h-48 overflow-y-auto">
                      <div className="text-xs text-gray-600 space-y-1">
                        {result.extractedScores.map((item, idx) => (
                          <div key={idx} className="flex justify-between">
                            <span className="font-medium">{item.score}</span>
                            <span>Cote: {item.odds}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </details>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <BarChart3 className="w-20 h-20 mx-auto mb-4 opacity-50" />
                <p>Les résultats apparaîtront ici après l'analyse</p>
              </div>
            )}
          </div>
        </div>

        {/* Module d'apprentissage */}
        {showLearning && (
          <div className="mt-8 bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
              <TrendingUp className="w-6 h-6 mr-2 text-purple-600" />
              Module d'Apprentissage
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Ajustez le modèle en fournissant le score prédit et le score réel du match.
            </p>
            
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Score Prédit (ex: 2-1)
                </label>
                <input
                  type="text"
                  value={predictedScore}
                  onChange={(e) => setPredictedScore(e.target.value)}
                  placeholder="2-1"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  data-testid="predicted-score-input"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Score Réel (ex: 3-1)
                </label>
                <input
                  type="text"
                  value={realScore}
                  onChange={(e) => setRealScore(e.target.value)}
                  placeholder="3-1"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  data-testid="real-score-input"
                />
              </div>
            </div>

            <button
              onClick={submitLearning}
              className="mt-4 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-semibold"
              data-testid="submit-learning-btn"
            >
              Soumettre l'Apprentissage
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-12 py-6 text-center text-gray-600 text-sm">
        <p>Prédicteur de Score avec Intelligence Artificielle 🧠⚽</p>
      </footer>
    </div>
  );
}

export default App;
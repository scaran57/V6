import React, { useEffect, useState } from "react";
import axios from "axios";

/*
  MatchAnalyzer.jsx
  - Page complète d'analyse intégrée avec le backend Emergent.
  - Endpoints attendus:
      GET  /api/admin/league/list
      GET  /api/admin/league/standings?league=LaLiga
      GET  /api/league/team-coeff?team=Real%20Madrid&league=LaLiga
      POST /api/analyze[?disable_cache=true&use_league_coeff=true&league=X]  (form-data file=@)
      POST /api/admin/league/update?league=LaLiga&force=true
*/

const API_BASE = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";

export default function MatchAnalyzer() {
  const [leagues, setLeagues] = useState([]);
  const [league, setLeague] = useState("");
  const [standings, setStandings] = useState([]);
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  const [file, setFile] = useState(null);

  const [useLeagueCoeff, setUseLeagueCoeff] = useState(true);
  const [disableCache, setDisableCache] = useState(false);

  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [debug, setDebug] = useState(null);
  const [homeCoeff, setHomeCoeff] = useState(1.0);
  const [awayCoeff, setAwayCoeff] = useState(1.0);
  const [homeSource, setHomeSource] = useState("");
  const [awaySource, setAwaySource] = useState("");

  const [message, setMessage] = useState("");
  
  // États pour la validation prédictive
  const [validationReport, setValidationReport] = useState(null);
  const [validationStatus, setValidationStatus] = useState("");

  useEffect(() => {
    fetchLeagues();
    fetchValidationReport();
  }, []);
  
  async function fetchValidationReport() {
    try {
      const res = await axios.get(`${API_BASE}/api/validation/status`);
      if (res.data.success && res.data.status !== "no_report") {
        setValidationReport(res.data);
        setValidationStatus("Dernier rapport chargé");
      }
    } catch (err) {
      console.error("fetchValidationReport", err);
    }
  }

  useEffect(() => {
    if (league) fetchStandings(league);
  }, [league]);

  useEffect(() => {
    // when home/away change, fetch coeffs
    if (home && league && useLeagueCoeff) fetchCoefficients();
    else {
      setHomeCoeff(1.0);
      setAwayCoeff(1.0);
      setHomeSource("");
      setAwaySource("");
    }
  }, [home, away, league, useLeagueCoeff]);

  async function fetchLeagues() {
    try {
      const res = await axios.get(`${API_BASE}/api/admin/league/list`);
      const data = res.data;
      const arr = Array.isArray(data) ? data : data.leagues || data.list || [];
      setLeagues(arr);
      if (arr.length > 0 && !league) {
        setLeague(arr[0]);
      }
    } catch (err) {
      console.error("fetchLeagues", err);
      setMessage("❌ Impossible de récupérer la liste des ligues.");
    }
  }

  async function fetchStandings(lg) {
    try {
      const res = await axios.get(`${API_BASE}/api/admin/league/standings`, {
        params: { league: lg },
      });
      const data = res.data;
      const teams = data.teams || data.standings || [];
      setStandings(teams);
      if (teams && teams.length === 0 && data.items) setStandings(data.items);
    } catch (err) {
      console.error("fetchStandings", err);
      setStandings([]);
    }
  }

  async function fetchCoefficients() {
    try {
      if (!home || !away || !league) return;
      const [hRes, aRes] = await Promise.all([
        axios.get(`${API_BASE}/api/league/team-coeff`, { params: { team: home, league } }),
        axios.get(`${API_BASE}/api/league/team-coeff`, { params: { team: away, league } }),
      ]);
      
      const hData = hRes.data;
      const aData = aRes.data;
      
      const h = hData.coefficient ?? hData.coef ?? hData.coeficient ?? 1.0;
      const a = aData.coefficient ?? aData.coef ?? aData.coeficient ?? 1.0;
      
      setHomeCoeff(Number(h));
      setAwayCoeff(Number(a));
      setHomeSource(hData.source || "");
      setAwaySource(aData.source || "");
    } catch (err) {
      console.error("fetchCoefficients", err);
      setHomeCoeff(1.0);
      setAwayCoeff(1.0);
      setHomeSource("");
      setAwaySource("");
    }
  }

  function onFileChange(e) {
    setFile(e.target.files?.[0] ?? null);
  }

  async function handleAnalyze() {
    if (!file && !(home && away)) {
      alert("Sélectionne une image ou choisis manuellement les équipes.");
      return;
    }
    setAnalyzing(true);
    setResult(null);
    setDebug(null);
    setMessage("Analyse en cours...");

    try {
      const fd = new FormData();
      if (file) fd.append("file", file);

      const params = new URLSearchParams();
      if (disableCache) params.append("disable_cache", "true");
      if (!useLeagueCoeff) params.append("disable_league_coeff", "true");
      if (league) params.append("league", league);

      const url = `${API_BASE}/api/analyze?${params.toString()}`;

      const res = await axios.post(url, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });

      const data = res.data;
      setResult(data);
      
      // Debug info
      setDebug({
        from_memory: data.fromMemory ?? data.from_memory ?? false,
        cache_disabled: data.cacheDisabled ?? disableCache,
        league: data.league || league,
        league_coeffs_applied: data.leagueCoeffsApplied ?? false,
        match_name: data.matchName || "Non détecté",
        bookmaker: data.bookmaker || "Non détecté",
      });
      
      setMessage("✅ Analyse terminée");
    } catch (err) {
      console.error("analyze error", err);
      setMessage("❌ Erreur durant l'analyse. Voir console pour détails.");
      setResult({ error: err.response?.data?.error || err.message });
    } finally {
      setAnalyzing(false);
    }
  }

  async function forceUpdateLeague(lg) {
    if (!lg) return;
    setMessage(`🔄 Mise à jour ${lg} en cours...`);
    try {
      await axios.post(`${API_BASE}/api/admin/league/update`, null, { 
        params: { league: lg, force: true },
        timeout: 60000
      });
      setMessage(`✅ Mise à jour ${lg} terminée.`);
      fetchStandings(lg);
    } catch (err) {
      console.error("forceUpdateLeague", err);
      setMessage("❌ Erreur lors de la mise à jour.");
    }
  }

  async function updateAllNow() {
    setMessage("🔄 Mise à jour de toutes les ligues...");
    try {
      await axios.post(`${API_BASE}/api/admin/league/update-all`, null, { 
        params: { force: true },
        timeout: 120000
      });
      setMessage("✅ Mise à jour de toutes les ligues terminée.");
      if (league) fetchStandings(league);
    } catch (err) {
      console.error("updateAllNow", err);
      setMessage("❌ Erreur lors de la mise à jour générale.");
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 py-8">
      <div className="max-w-6xl mx-auto px-4">
        <h1 className="text-4xl font-bold mb-6 text-white text-center">
          ⚽ Match Analyzer <span className="text-purple-400">(Coefficients UEFA)</span>
        </h1>

        {/* Configuration Panel */}
        <div className="bg-slate-800/90 backdrop-blur text-white p-6 rounded-xl shadow-2xl space-y-6 mb-6">
          {/* League & Team Selection */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* League Selection */}
            <div>
              <label className="block text-sm font-semibold text-gray-300 mb-2">
                🏆 Ligue / Compétition
              </label>
              <select
                value={league}
                onChange={(e) => setLeague(e.target.value)}
                className="w-full bg-slate-700 text-white p-3 rounded-lg border border-slate-600 focus:ring-2 focus:ring-purple-500 focus:outline-none"
              >
                {leagues.length === 0 && <option>Chargement...</option>}
                {leagues.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-400 mt-1">
                {standings.length} équipes chargées
              </p>
            </div>

            {/* File Upload */}
            <div>
              <label className="block text-sm font-semibold text-gray-300 mb-2">
                📸 Image bookmaker
              </label>
              <div className="relative">
                <input
                  type="file"
                  accept="image/*"
                  onChange={onFileChange}
                  className="w-full text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-purple-600 file:text-white hover:file:bg-purple-500 cursor-pointer"
                />
              </div>
              {file && (
                <p className="text-xs text-green-400 mt-1">
                  ✓ {file.name}
                </p>
              )}
            </div>
          </div>

          {/* Team Selection */}
          <div>
            <label className="block text-sm font-semibold text-gray-300 mb-2">
              👥 Sélection manuelle des équipes (optionnel)
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Équipe Domicile</label>
                <select
                  value={home}
                  onChange={(e) => setHome(e.target.value)}
                  className="w-full bg-slate-700 text-white p-3 rounded-lg border border-slate-600 focus:ring-2 focus:ring-green-500 focus:outline-none"
                >
                  <option value="">-- Sélectionner --</option>
                  {standings.map((t) => (
                    <option key={t.team ?? t.name} value={t.team ?? t.name}>
                      {t.position ? `${t.position}. ` : ""}{t.team ?? t.name}
                    </option>
                  ))}
                </select>
                {home && useLeagueCoeff && (
                  <div className="mt-2 text-xs bg-green-900/30 p-2 rounded border border-green-700">
                    <div className="font-semibold text-green-300">Coefficient: {homeCoeff.toFixed(3)}</div>
                    {homeSource && (
                      <div className="text-gray-400">Source: {homeSource}</div>
                    )}
                  </div>
                )}
              </div>

              <div>
                <label className="text-xs text-gray-400 mb-1 block">Équipe Extérieur</label>
                <select
                  value={away}
                  onChange={(e) => setAway(e.target.value)}
                  className="w-full bg-slate-700 text-white p-3 rounded-lg border border-slate-600 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="">-- Sélectionner --</option>
                  {standings.map((t) => (
                    <option key={t.team ?? t.name + "_a"} value={t.team ?? t.name}>
                      {t.position ? `${t.position}. ` : ""}{t.team ?? t.name}
                    </option>
                  ))}
                </select>
                {away && useLeagueCoeff && (
                  <div className="mt-2 text-xs bg-blue-900/30 p-2 rounded border border-blue-700">
                    <div className="font-semibold text-blue-300">Coefficient: {awayCoeff.toFixed(3)}</div>
                    {awaySource && (
                      <div className="text-gray-400">Source: {awaySource}</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Options */}
          <div className="border-t border-slate-700 pt-4">
            <div className="flex flex-wrap items-center gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useLeagueCoeff}
                  onChange={(e) => setUseLeagueCoeff(e.target.checked)}
                  className="w-4 h-4 text-purple-600 bg-gray-700 border-gray-600 rounded focus:ring-purple-500"
                />
                <span className="text-sm font-medium">🏆 Activer coefficients de ligue</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={disableCache}
                  onChange={(e) => setDisableCache(e.target.checked)}
                  className="w-4 h-4 text-purple-600 bg-gray-700 border-gray-600 rounded focus:ring-purple-500"
                />
                <span className="text-sm font-medium">🔄 Forcer nouveau calcul</span>
              </label>

              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="ml-auto bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 disabled:from-gray-600 disabled:to-gray-500 text-white font-bold px-6 py-3 rounded-lg shadow-lg transform hover:scale-105 transition-all disabled:transform-none"
              >
                {analyzing ? "🔄 Analyse..." : "🚀 Analyser"}
              </button>
            </div>
          </div>

          {/* Admin Actions */}
          <div className="border-t border-slate-700 pt-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs text-gray-400 font-semibold">ADMIN:</span>
              <button
                onClick={() => forceUpdateLeague(league)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white text-sm font-medium transition-colors"
              >
                🔁 Update {league}
              </button>
              <button
                onClick={updateAllNow}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-sm font-medium transition-colors"
              >
                🔄 Update toutes ligues
              </button>
              {message && (
                <div className="ml-auto text-sm text-gray-300 bg-slate-700/50 px-3 py-2 rounded">
                  {message}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Results Panel */}
        {result && !result.error && (
          <div className="bg-white/95 backdrop-blur p-6 rounded-xl shadow-2xl">
            <h2 className="text-2xl font-bold text-gray-800 mb-4 border-b pb-2">
              📊 Résultats de l'analyse
            </h2>

            {/* Match Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Match</div>
                <div className="font-bold text-lg text-gray-800">
                  {debug?.match_name || "Non détecté"}
                </div>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Bookmaker</div>
                <div className="font-bold text-lg text-gray-800">
                  {debug?.bookmaker || "Non détecté"}
                </div>
              </div>
            </div>

            {/* Top Prediction */}
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-6 rounded-xl mb-6 border-l-4 border-green-500">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-gray-600 mb-1">Score le plus probable</div>
                  <div className="text-4xl font-bold text-gray-800">
                    {result.mostProbableScore || result.top_prediction || "N/A"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-600 mb-1">Confiance</div>
                  <div className="text-3xl font-bold text-green-600">
                    {result.confidence ? `${(Number(result.confidence) * 100).toFixed(1)}%` : "N/A"}
                  </div>
                </div>
              </div>
            </div>

            {/* Debug Info */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">Provenance</div>
                <div className="font-semibold text-gray-800">
                  {debug?.from_memory ? "🧠 Cache" : "🔁 Nouveau calcul"}
                </div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">Ligue</div>
                <div className="font-semibold text-gray-800">
                  {debug?.league || "N/A"}
                </div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">Coefficients appliqués</div>
                <div className="font-semibold text-gray-800">
                  {debug?.league_coeffs_applied ? "✅ Oui" : "❌ Non"}
                </div>
              </div>
            </div>

            {/* Top 10 Probabilities */}
            <div>
              <h3 className="text-lg font-bold text-gray-800 mb-3">Top 10 des scores</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {result.probabilities &&
                  Object.entries(result.probabilities)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 10)
                    .map(([score, p], idx) => (
                      <div
                        key={score}
                        className={`p-3 rounded-lg text-center ${
                          idx === 0
                            ? "bg-gradient-to-br from-green-500 to-emerald-500 text-white"
                            : idx === 1
                            ? "bg-gradient-to-br from-blue-500 to-indigo-500 text-white"
                            : idx === 2
                            ? "bg-gradient-to-br from-purple-500 to-pink-500 text-white"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        <div className="font-bold text-lg">{score}</div>
                        <div className="text-sm opacity-90">
                          {(Number(p) * 100).toFixed(1)}%
                        </div>
                      </div>
                    ))}
              </div>
            </div>

            {/* Top 3 */}
            {result.top3 && result.top3.length > 0 && (
              <div className="mt-6">
                <h3 className="text-lg font-bold text-gray-800 mb-3">Top 3 détaillé</h3>
                <div className="space-y-2">
                  {result.top3.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between bg-gray-50 p-3 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                            idx === 0
                              ? "bg-yellow-400 text-yellow-900"
                              : idx === 1
                              ? "bg-gray-300 text-gray-700"
                              : "bg-orange-300 text-orange-900"
                          }`}
                        >
                          {idx + 1}
                        </div>
                        <div className="font-bold text-xl text-gray-800">
                          {item.score}
                        </div>
                      </div>
                      <div className="text-lg font-semibold text-gray-700">
                        {(Number(item.probability) * 100).toFixed(2)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {result && result.error && (
          <div className="bg-red-100 border-l-4 border-red-500 p-4 rounded-lg">
            <div className="font-bold text-red-800 mb-2">Erreur</div>
            <div className="text-red-700">{result.error}</div>
          </div>
        )}

        {!result && (
          <div className="text-center text-gray-400 py-12">
            <div className="text-6xl mb-4">📊</div>
            <div className="text-xl">Sélectionnez une image et cliquez sur Analyser</div>
            <div className="text-sm mt-2">Les résultats s'afficheront ici</div>
          </div>
        )}
      </div>
    </div>
  );
}

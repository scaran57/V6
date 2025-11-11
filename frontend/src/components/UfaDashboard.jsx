// /frontend/src/components/UfaDashboard.jsx
import React, { useEffect, useState } from "react";
import { RefreshCcw, Activity, Globe2, Brain, FileText, LineChart } from "lucide-react";
import { LineChart as ReLineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function UfaDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/ufa/v3/dashboard-status`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (e) {
      console.error("Erreur dashboard:", e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000); // toutes les 15s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="p-6 text-gray-400 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCcw className="animate-spin mx-auto mb-4" size={40} />
          <p>Chargement du dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-red-400 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-xl mb-2">❌ Erreur de connexion</p>
          <p className="text-sm">{error}</p>
          <button 
            onClick={fetchStatus}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="p-6 text-gray-400">Aucune donnée disponible</div>;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">🤖 Dashboard UFAv3</h1>
          <p className="text-gray-400">
            Dernière mise à jour : {new Date(data.timestamp).toLocaleString('fr-FR')}
          </p>
        </div>

        {/* Grid principal */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          
          {/* Statuts des processus */}
          <div className="bg-gray-800 rounded-2xl p-6 shadow-xl border border-gray-700 hover:border-gray-600 transition-all">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-4">
              <Activity className="text-green-400" size={24} /> Processus
            </h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Backend</span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  data.backend === "running" 
                    ? "bg-green-500/20 text-green-400" 
                    : "bg-red-500/20 text-red-400"
                }`}>
                  {data.backend === "running" ? "🟢 Actif" : "🔴 Inactif"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Scheduler</span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  data.scheduler === "running" 
                    ? "bg-green-500/20 text-green-400" 
                    : "bg-red-500/20 text-red-400"
                }`}>
                  {data.scheduler === "running" ? "🟢 Actif" : "🔴 Inactif"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Keep-Alive</span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  data.keep_alive === "running" 
                    ? "bg-green-500/20 text-green-400" 
                    : "bg-red-500/20 text-red-400"
                }`}>
                  {data.keep_alive === "running" ? "🟢 Actif" : "🔴 Inactif"}
                </span>
              </div>
            </div>
          </div>

          {/* Coefficients */}
          <div className="bg-gray-800 rounded-2xl p-6 shadow-xl border border-gray-700 hover:border-gray-600 transition-all">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-4">
              <Globe2 className="text-blue-400" size={24} /> Coefficients
            </h2>
            <div className="space-y-4">
              <div>
                <p className="text-gray-400 text-sm">Équipes FIFA</p>
                <p className="text-3xl font-bold text-blue-400">{data.coeffs.fifa_teams}</p>
              </div>
              <div>
                <p className="text-gray-400 text-sm">Ligues UEFA</p>
                <p className="text-3xl font-bold text-blue-400">{data.coeffs.uefa_leagues}</p>
              </div>
            </div>
          </div>

          {/* Modèle */}
          <div className="bg-gray-800 rounded-2xl p-6 shadow-xl border border-gray-700 hover:border-gray-600 transition-all">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-4">
              <Brain className="text-purple-400" size={24} /> Modèle UFAv3
            </h2>
            <div className="space-y-4">
              <div>
                <p className="text-gray-400 text-sm">État</p>
                <p className={`text-2xl font-bold ${
                  data.model.exists ? "text-green-400" : "text-red-400"
                }`}>
                  {data.model.exists ? "✅ Chargé" : "❌ Absent"}
                </p>
              </div>
              {data.model.exists && (
                <div>
                  <p className="text-gray-400 text-sm">Taille</p>
                  <p className="text-2xl font-bold text-purple-400">
                    {data.model.size_kb} Ko
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Performance */}
          <div className="bg-gray-800 rounded-2xl p-6 shadow-xl border border-gray-700 hover:border-gray-600 transition-all lg:col-span-2">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-4">
              <RefreshCcw className="text-yellow-400" size={24} /> Performance
            </h2>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-gray-400 text-sm mb-2">Précision actuelle</p>
                <p className="text-4xl font-bold text-yellow-400">
                  {data.performance.accuracy !== null 
                    ? `${data.performance.accuracy}%` 
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-gray-400 text-sm mb-2">Matchs analysés</p>
                <p className="text-4xl font-bold text-yellow-400">
                  {data.performance.matches}
                </p>
              </div>
            </div>
          </div>

          {/* Courbe d'évolution */}
          <div className="bg-gray-800 rounded-2xl p-6 shadow-xl border border-gray-700 hover:border-gray-600 transition-all lg:col-span-3">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-6">
              <LineChart className="text-green-400" size={24} /> Évolution du modèle
            </h2>
            {data.history && data.history.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <ReLineChart data={data.history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis 
                    dataKey="date" 
                    stroke="#9CA3AF" 
                    tick={{ fill: '#9CA3AF' }}
                    angle={-45}
                    textAnchor="end"
                    height={80}
                  />
                  <YAxis 
                    stroke="#9CA3AF" 
                    domain={[0, 100]} 
                    tick={{ fill: '#9CA3AF' }}
                    label={{ value: 'Précision (%)', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1F2937', 
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#F3F4F6'
                    }} 
                  />
                  <Line 
                    type="monotone" 
                    dataKey="accuracy" 
                    stroke="#10B981" 
                    strokeWidth={3}
                    dot={{ fill: '#10B981', r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </ReLineChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center py-12">
                <LineChart className="mx-auto text-gray-600 mb-4" size={48} />
                <p className="text-gray-500">Aucune donnée historique disponible</p>
                <p className="text-gray-600 text-sm mt-2">
                  Les données apparaîtront après le premier réentraînement
                </p>
              </div>
            )}
          </div>

          {/* Logs récents */}
          <div className="bg-gray-800 rounded-2xl p-6 shadow-xl border border-gray-700 hover:border-gray-600 transition-all lg:col-span-3">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-4">
              <FileText className="text-orange-400" size={24} /> Logs récents
            </h2>
            <div className="bg-gray-900 rounded-lg p-4 overflow-y-auto max-h-48 font-mono text-sm">
              {data.logs.length > 0 ? (
                <pre className="text-gray-300 whitespace-pre-wrap">
                  {data.logs.join('\n')}
                </pre>
              ) : (
                <p className="text-gray-500">Aucun log disponible</p>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

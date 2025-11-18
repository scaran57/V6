import React from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function SystemPage() {
  const [status, setStatus] = React.useState(null);
  const [diagnostic, setDiagnostic] = React.useState(null);
  const [running, setRunning] = React.useState(false);
  const [learningStats, setLearningStats] = React.useState(null);

  React.useEffect(() => { fetchStatus(); fetchLearningStats(); }, []);

  async function fetchStatus() {
    try {
      const r = await fetch(`${BACKEND_URL}/api/admin/league/scheduler-status`);
      const j = await r.json();
      setStatus(j);
    } catch (e) {
      console.error(e);
    }
  }

  async function fetchLearningStats() {
    try {
      const r = await fetch(`${BACKEND_URL}/api/learning-stats?days=30`);
      const j = await r.json();
      setLearningStats(j.stats);
    } catch (e) {
      console.error(e);
    }
  }

  async function forceUpdate() {
    if (!confirm('Lancer la mise à jour manuelle?')) return;
    setRunning(true);
    try {
      await fetch(`${BACKEND_URL}/api/admin/league/trigger-update`, { method: 'POST' });
      await fetchStatus();
      alert('Mise à jour déclenchée!');
    } catch (e) {
      alert('Erreur: ' + e.message);
    }
    setRunning(false);
  }

  async function runDiagnostic() {
    setRunning(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/diagnostic`);
      const j = await r.json();
      setDiagnostic(j);
    } catch (e) {
      alert('Erreur: ' + e.message);
    }
    setRunning(false);
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Scheduler Status */}
      <section className="bg-white p-6 rounded-lg shadow-lg">
        <h2 className="text-2xl font-bold mb-4 text-slate-800">⚙️ Scheduler & Système</h2>
        <div className="grid md:grid-cols-3 gap-4 mb-4">
          <div className="bg-blue-50 p-4 rounded">
            <div className="text-sm text-slate-600">Statut Scheduler</div>
            <div className="text-xl font-bold">{status?.scheduler?.is_running ? '✅ Actif' : '❌ Inactif'}</div>
          </div>
          <div className="bg-green-50 p-4 rounded">
            <div className="text-sm text-slate-600">Prochaine exécution</div>
            <div className="text-xl font-bold">{status?.scheduler?.next_update || '-'}</div>
          </div>
          <div className="bg-purple-50 p-4 rounded">
            <div className="text-sm text-slate-600">Dernière mise à jour</div>
            <div className="text-xl font-bold">{status?.scheduler?.last_update || 'Jamais'}</div>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={forceUpdate} disabled={running} className="bg-orange-600 text-white px-4 py-2 rounded hover:bg-orange-700 disabled:opacity-50">
            {running ? '⏳' : '🔄'} Forcer mise à jour
          </button>
          <button onClick={runDiagnostic} disabled={running} className="bg-slate-600 text-white px-4 py-2 rounded hover:bg-slate-700 disabled:opacity-50">
            {running ? '⏳' : '🔍'} Diagnostic
          </button>
        </div>
      </section>

      {/* Learning Stats */}
      {learningStats && (
        <section className="bg-white p-6 rounded-lg shadow-lg">
          <h3 className="text-xl font-bold mb-4">🎓 Statistiques d'apprentissage (30 jours)</h3>
          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-indigo-50 p-4 rounded">
              <div className="text-sm text-slate-600">Événements</div>
              <div className="text-2xl font-bold">{learningStats.count || 0}</div>
            </div>
            <div className="bg-teal-50 p-4 rounded">
              <div className="text-sm text-slate-600">Ajustement moyen</div>
              <div className="text-2xl font-bold">{learningStats.avg_adjustment?.toFixed(4) || 0}</div>
            </div>
            <div className="bg-amber-50 p-4 rounded">
              <div className="text-sm text-slate-600">Ajustement total</div>
              <div className="text-2xl font-bold">{learningStats.total_adjustment?.toFixed(4) || 0}</div>
            </div>
          </div>
        </section>
      )}

      {/* Diagnostic Results */}
      {diagnostic && (
        <section className="bg-white p-6 rounded-lg shadow-lg">
          <h3 className="text-xl font-bold mb-4">🔍 Résultats du diagnostic</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-green-50 p-4 rounded text-center">
              <div className="text-sm text-slate-600">Tests réussis</div>
              <div className="text-3xl font-bold text-green-600">{diagnostic.summary?.passed || 0}</div>
            </div>
            <div className="bg-red-50 p-4 rounded text-center">
              <div className="text-sm text-slate-600">Tests échoués</div>
              <div className="text-3xl font-bold text-red-600">{diagnostic.summary?.failed || 0}</div>
            </div>
            <div className="bg-blue-50 p-4 rounded text-center">
              <div className="text-sm text-slate-600">Total tests</div>
              <div className="text-3xl font-bold text-blue-600">{diagnostic.summary?.total_tests || 0}</div>
            </div>
            <div className="bg-purple-50 p-4 rounded text-center">
              <div className="text-sm text-slate-600">Taux de réussite</div>
              <div className="text-3xl font-bold text-purple-600">{diagnostic.summary?.success_rate || '0%'}</div>
            </div>
          </div>
          <details className="bg-slate-50 rounded p-4">
            <summary className="cursor-pointer font-medium">Détails complets</summary>
            <pre className="text-xs mt-2 overflow-auto max-h-96 bg-slate-800 text-green-400 p-3 rounded">
              {JSON.stringify(diagnostic, null, 2)}
            </pre>
          </details>
        </section>
      )}
    </div>
  );
}

import React from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function HistoryPage() {
  const [uploads, setUploads] = React.useState([]);
  const [analyses, setAnalyses] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [view, setView] = React.useState('uploads');

  React.useEffect(() => { fetchData(); }, [view]);

  async function fetchData() {
    setLoading(true);
    try {
      const endpoint = view === 'uploads' ? '/api/last-uploads?limit=50' : '/api/last-analyses?limit=50';
      const r = await fetch(`${BACKEND_URL}${endpoint}`);
      const j = await r.json();
      if (view === 'uploads') setUploads(j.uploads || []);
      else setAnalyses(j.analyses || []);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  return (
    <div className="max-w-7xl mx-auto">
      <section className="bg-white p-6 rounded-lg shadow-lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-slate-800">📋 Historique</h2>
          <div className="flex gap-2">
            <button onClick={() => setView('uploads')} className={`px-4 py-2 rounded ${view === 'uploads' ? 'bg-blue-600 text-white' : 'bg-slate-100'}`}>
              Images
            </button>
            <button onClick={() => setView('analyses')} className={`px-4 py-2 rounded ${view === 'analyses' ? 'bg-blue-600 text-white' : 'bg-slate-100'}`}>
              Analyses
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8">Chargement...</div>
        ) : view === 'uploads' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-100">
                <tr>
                  <th className="p-3 text-left">ID</th>
                  <th className="p-3 text-left">Image</th>
                  <th className="p-3 text-left">Match</th>
                  <th className="p-3 text-left">Ligue</th>
                  <th className="p-3 text-left">Date</th>
                  <th className="p-3 text-left">Statut</th>
                </tr>
              </thead>
              <tbody>
                {uploads.map(item => (
                  <tr key={item.id} className="border-t hover:bg-slate-50">
                    <td className="p-3">#{item.id}</td>
                    <td className="p-3">{item.original_filename || 'N/A'}</td>
                    <td className="p-3">{item.home_team && item.away_team ? `${item.home_team} vs ${item.away_team}` : '-'}</td>
                    <td className="p-3">{item.league || '-'}</td>
                    <td className="p-3">{item.upload_time ? new Date(item.upload_time).toLocaleString('fr-FR') : '-'}</td>
                    <td className="p-3">{item.processed ? '✅ Traité' : '⏳ En attente'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-100">
                <tr>
                  <th className="p-3 text-left">ID</th>
                  <th className="p-3 text-left">Score prédit</th>
                  <th className="p-3 text-left">Score réel</th>
                  <th className="p-3 text-left">Ligue</th>
                  <th className="p-3 text-left">OCR</th>
                  <th className="p-3 text-left">Confiance</th>
                  <th className="p-3 text-left">Date</th>
                </tr>
              </thead>
              <tbody>
                {analyses.map(item => (
                  <tr key={item.id} className="border-t hover:bg-slate-50">
                    <td className="p-3">#{item.id}</td>
                    <td className="p-3 font-medium">{item.most_probable_score || '-'}</td>
                    <td className="p-3">{item.real_score || '-'}</td>
                    <td className="p-3">{item.league_used || '-'}</td>
                    <td className="p-3">{item.ocr_engine || '-'}</td>
                    <td className="p-3">{item.confidence ? `${(item.confidence * 100).toFixed(1)}%` : '-'}</td>
                    <td className="p-3">{item.created_at ? new Date(item.created_at).toLocaleString('fr-FR') : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

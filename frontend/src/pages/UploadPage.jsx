// Page d'upload et analyse d'images bookmaker
import React from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function UploadPage() {
  const [file, setFile] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState(null);
  const [preferGpt, setPreferGpt] = React.useState(true);
  const [league, setLeague] = React.useState('');
  const [homeTeam, setHomeTeam] = React.useState('');
  const [awayTeam, setAwayTeam] = React.useState('');
  const [bookmaker, setBookmaker] = React.useState('');
  const [preview, setPreview] = React.useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    
    // Preview
    if (selectedFile) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result);
      };
      reader.readAsDataURL(selectedFile);
    } else {
      setPreview(null);
    }
  };

  const upload = async () => {
    if (!file) return alert('Choisis une image');
    
    setLoading(true);
    setResult(null);
    
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('league', league);
      fd.append('home_team', homeTeam);
      fd.append('away_team', awayTeam);
      fd.append('bookmaker', bookmaker);
      fd.append('prefer_gpt_vision', preferGpt);
      
      const r = await fetch(`${BACKEND_URL}/api/upload-image-advanced`, {
        method: 'POST',
        body: fd
      });
      
      const j = await r.json();
      setResult(j);
    } catch (error) {
      setResult({ error: error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <section className="bg-white p-6 rounded-lg shadow-lg">
        <h2 className="text-2xl font-bold mb-2 text-slate-800">📸 Analyser un ticket bookmaker</h2>
        <p className="text-sm text-slate-600 mb-6">
          Glisse ou choisis la photo du coupon. Le système analyse automatiquement avec GPT-4 Vision et sauvegarde l'analyse.
        </p>
        
        <div className="grid md:grid-cols-2 gap-6">
          {/* Left column - Upload */}
          <div>
            <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center hover:border-blue-500 transition">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
              />
              <label htmlFor="file-upload" className="cursor-pointer">
                {preview ? (
                  <img src={preview} alt="Preview" className="max-h-64 mx-auto rounded" />
                ) : (
                  <div>
                    <svg className="mx-auto h-12 w-12 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="mt-2 text-sm text-slate-600">Clique ou glisse une image</p>
                  </div>
                )}
              </label>
            </div>
            
            {file && (
              <div className="mt-2 text-sm text-slate-600">
                📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </div>
            )}
          </div>
          
          {/* Right column - Options */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Ligue</label>
              <select
                value={league}
                onChange={(e) => setLeague(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Détecter automatiquement</option>
                <option value="LaLiga">LaLiga (Espagne)</option>
                <option value="PremierLeague">Premier League (Angleterre)</option>
                <option value="SerieA">Serie A (Italie)</option>
                <option value="Bundesliga">Bundesliga (Allemagne)</option>
                <option value="Ligue1">Ligue 1 (France)</option>
                <option value="Ligue2">Ligue 2 (France)</option>
                <option value="ChampionsLeague">Champions League</option>
                <option value="EuropaLeague">Europa League</option>
              </select>
            </div>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Équipe domicile</label>
                <input
                  type="text"
                  value={homeTeam}
                  onChange={(e) => setHomeTeam(e.target.value)}
                  placeholder="Ex: PSG"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Équipe extérieur</label>
                <input
                  type="text"
                  value={awayTeam}
                  onChange={(e) => setAwayTeam(e.target.value)}
                  placeholder="Ex: Marseille"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Bookmaker</label>
              <select
                value={bookmaker}
                onChange={(e) => setBookmaker(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Sélectionner</option>
                <option value="Winamax">Winamax</option>
                <option value="Unibet">Unibet</option>
                <option value="BetClic">BetClic</option>
                <option value="ParionsSport">ParionsSport (FDJ)</option>
                <option value="PMU">PMU Sport</option>
              </select>
            </div>
            
            <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-md">
              <input
                type="checkbox"
                checked={preferGpt}
                onChange={(e) => setPreferGpt(e.target.checked)}
                id="gpt-vision"
                className="w-4 h-4"
              />
              <label htmlFor="gpt-vision" className="text-sm text-slate-700">
                🤖 GPT-4 Vision prioritaire (plus précis)
              </label>
            </div>
            
            <button
              onClick={upload}
              disabled={loading || !file}
              className="w-full bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-3 rounded-lg font-medium hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-md"
            >
              {loading ? '🔄 Analyse en cours...' : '🚀 Lancer l\'analyse'}
            </button>
          </div>
        </div>
        
        {/* Results */}
        {result && (
          <div className="mt-6 border-t pt-6">
            <h3 className="text-lg font-semibold mb-3 text-slate-800">
              {result.error ? '❌ Erreur' : '✅ Résultat de l\'analyse'}
            </h3>
            {result.error ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                {result.error}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-slate-50 p-3 rounded">
                    <div className="text-xs text-slate-500">Moteur OCR</div>
                    <div className="text-lg font-semibold">{result.ocr_engine || 'N/A'}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded">
                    <div className="text-xs text-slate-500">Scores extraits</div>
                    <div className="text-lg font-semibold">{result.scores_count || 0}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded">
                    <div className="text-xs text-slate-500">Upload ID</div>
                    <div className="text-lg font-semibold">#{result.uploaded_id}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded">
                    <div className="text-xs text-slate-500">Analyse ID</div>
                    <div className="text-lg font-semibold">#{result.analysis_id}</div>
                  </div>
                </div>
                
                {result.parsed_scores && result.parsed_scores.length > 0 && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <h4 className="font-medium text-green-800 mb-2">Scores extraits:</h4>
                    <div className="space-y-1 text-sm">
                      {result.parsed_scores.map((score, idx) => (
                        <div key={idx} className="flex justify-between">
                          <span>{score.home}-{score.away}</span>
                          <span className="font-medium">Cote: {score.cote}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                <details className="bg-slate-50 rounded-lg p-4">
                  <summary className="cursor-pointer font-medium text-slate-700">Détails complets (JSON)</summary>
                  <pre className="text-xs mt-2 overflow-auto max-h-64 bg-slate-800 text-green-400 p-3 rounded">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

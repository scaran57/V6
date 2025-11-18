// Dashboard principal avec navigation
import React from 'react';
import UploadPage from './UploadPage';
import HistoryPage from './HistoryPage';
import SystemPage from './SystemPage';

export default function DashboardPage() {
  const [route, setRoute] = React.useState('upload');

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-white shadow p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-blue-600">⚽ Football AI</h1>
          <span className="text-sm text-slate-500">Système de prédiction</span>
        </div>
        <nav className="space-x-2">
          <button
            onClick={() => setRoute('upload')}
            className={`px-4 py-2 rounded-lg transition ${
              route === 'upload' ? 'bg-blue-600 text-white shadow-md' : 'bg-slate-100 hover:bg-slate-200'
            }`}
          >
            📸 Analyser
          </button>
          <button
            onClick={() => setRoute('history')}
            className={`px-4 py-2 rounded-lg transition ${
              route === 'history' ? 'bg-blue-600 text-white shadow-md' : 'bg-slate-100 hover:bg-slate-200'
            }`}
          >
            📋 Historique
          </button>
          <button
            onClick={() => setRoute('system')}
            className={`px-4 py-2 rounded-lg transition ${
              route === 'system' ? 'bg-blue-600 text-white shadow-md' : 'bg-slate-100 hover:bg-slate-200'
            }`}
          >
            ⚙️ Système
          </button>
        </nav>
      </header>
      <main className="p-6">
        {route === 'upload' && <UploadPage />}
        {route === 'history' && <HistoryPage />}
        {route === 'system' && <SystemPage />}
      </main>
      <footer className="bg-white border-t p-4 text-center text-sm text-slate-500">
        Football AI Prediction System - Powered by GPT-4 Vision & Machine Learning
      </footer>
    </div>
  );
}

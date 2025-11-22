import React from "react";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import HistoryPage from "./pages/HistoryPage";
import SystemPage from "./pages/SystemPage";

export default function AppRouter() {
  const [route, setRoute] = React.useState("dashboard");

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white shadow p-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">⚽ Football AI</h1>

        <nav className="flex space-x-4">
          <button onClick={() => setRoute("dashboard")}>🏠 Dashboard</button>
          <button onClick={() => setRoute("upload")}>📸 Analyse</button>
          <button onClick={() => setRoute("history")}>📋 Historique</button>
          <button onClick={() => setRoute("system")}>⚙️ Système</button>
        </nav>
      </header>

      <main className="p-4">
        {route === "dashboard" && <DashboardPage />}
        {route === "upload" && <UploadPage />}
        {route === "history" && <HistoryPage />}
        {route === "system" && <SystemPage />}
      </main>
    </div>
  );
}

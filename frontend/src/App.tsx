import { useState, useEffect } from 'react';
import { StatusPanel } from './StatusPanel';
import { ModelPanel } from './ModelPanel';
import { GISMap } from './Map';
import './index.css';

interface DemStatus {
  source?: string;
  provider?: string;
  data_status?: string;
  resolution_m?: number;
  crs?: string;
}

function App() {
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [demStatus, setDemStatus] = useState<DemStatus | null>(null);

  useEffect(() => {
    fetch('/api/v1/elevation/status')
      .then(res => res.json())
      .then(data => setDemStatus(data))
      .catch(err => console.error("Failed to load elevation status", err));
  }, []);

  return (
    <div className="flex flex-col h-screen bg-gray-900 w-full font-sans text-white overflow-hidden">
      {/* TOP: Header */}
      <header className="flex-none bg-gray-950 px-6 py-3.5 border-b border-gray-800 flex justify-between items-center shadow-md">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight flex items-center">
            FloodGuard AI 
            <span className="text-blue-500 text-sm font-medium tracking-normal ml-3 bg-blue-950/80 px-2.5 py-0.5 rounded border border-blue-800/60">
              Urban Flood Nowcasting System
            </span>
          </h1>
        </div>
        <div className="flex items-center space-x-6 text-xs">
          <div className="flex items-center bg-gray-900 px-3 py-1 rounded-full border border-gray-800">
            <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
            System Online
          </div>
          <div className="text-gray-400 font-mono">
            {new Date().toLocaleString()}
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="flex-1 flex overflow-hidden">
        
        {/* LEFT: Sidebar Dashboard */}
        <aside className="w-1/3 min-w-[420px] max-w-[500px] bg-gray-900 border-r border-gray-800 p-5 overflow-y-auto flex flex-col gap-5">
          
          {/* Milestone 4: Flood Modeling Control & Statistics */}
          <ModelPanel onRunSelected={(id) => setSelectedRunId(id)} activeRunId={selectedRunId} />
          
          {/* Milestone 2 Data Status */}
          <StatusPanel />

          {/* DEM/Elevation Status */}
          <section className="bg-gray-800 p-4 rounded-lg shadow border border-gray-700">
            <h2 className="text-sm font-bold mb-2 text-blue-400 uppercase tracking-wide">Elevation Data Status</h2>
            <div className="flex flex-col text-xs text-gray-300 bg-gray-900 p-3 rounded space-y-1">
              <div>Source: <strong className="text-white">{demStatus?.source || 'Copernicus DEM GLO-30'}</strong></div>
              <div>Resolution: <strong className="text-white">{demStatus?.resolution_m ? `${demStatus.resolution_m}m Grid (Resampled)` : '30m Grid'}</strong></div>
              <div>Status: {
                demStatus?.data_status === 'OBSERVED' ? (
                  <span className="text-green-400 font-semibold">REAL DATA — OBSERVED (Copernicus GLO-30)</span>
                ) : (
                  <span className="text-yellow-400 font-semibold">DEVELOPMENT DATA — SYNTHETIC DEM</span>
                )
              }</div>
              {demStatus?.crs && <div>CRS: <strong className="text-gray-300">{demStatus.crs}</strong></div>}
            </div>
          </section>

          {/* Scientific Safety Notice */}
          <section className="bg-gray-800 p-4 rounded-lg shadow border border-yellow-700/50">
             <h2 className="text-sm font-bold mb-2 text-yellow-500 flex items-center">
                <span className="mr-2">⚠️</span> Scientific Safety Notice
             </h2>
             <p className="text-xs text-gray-300 leading-relaxed">
               This system acts as a decision-support platform. 
               <br/><br/>
               Currently displaying <strong>Development Data — Simulated Rainfall & Baseline Flood Model</strong>. 
               Flood predictions shown by this development system are baseline model outputs and have not been validated for operational emergency use.
             </p>
          </section>

        </aside>

        {/* CENTER: GIS Map */}
        <section className="flex-1 relative bg-black">
          <GISMap selectedRunId={selectedRunId} />
        </section>

      </main>
    </div>
  );
}

export default App;

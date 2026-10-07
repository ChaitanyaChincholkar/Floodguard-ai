import { useState, useEffect } from 'react';

interface ModelMetrics {
  rainfall_mm: number;
  affected_cells: number;
  affected_area_sqkm: number;
  max_depth_m: number;
  mean_depth_m: number;
  risk_counts: {
    low: number;
    moderate: number;
    high: number;
    severe: number;
  };
}

interface ModelRun {
  id: number;
  model_name: string;
  model_version: string;
  status: string;
  execution_time_ms?: number;
  dem_source: string;
  data_status: string;
  parameters?: { rainfall_mm?: number };
  metrics?: ModelMetrics;
}

interface ModelPanelProps {
  onRunSelected?: (runId: number) => void;
  activeRunId?: number | null;
}

export function ModelPanel({ onRunSelected, activeRunId }: ModelPanelProps) {
  const [latestRun, setLatestRun] = useState<ModelRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [rainfallInput, setRainfallInput] = useState<number>(65.0);

  const fetchLatestRun = async () => {
    try {
      const res = await fetch('/api/v1/model/runs/latest');
      if (res.ok) {
        const data = await res.json();
        setLatestRun(data);
        if (onRunSelected && data.id && activeRunId !== data.id) {
          onRunSelected(data.id);
        }
      }
    } catch (err) {
      console.error("Failed to load model run", err);
    }
  };

  useEffect(() => {
    fetchLatestRun();
    const interval = setInterval(fetchLatestRun, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleRunModel = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/model/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rainfall_mm: rainfallInput })
      });
      if (res.ok) {
        const data = await res.json();
        setLatestRun(data);
        if (onRunSelected) onRunSelected(data.id);
      }
    } catch (err) {
      console.error("Failed to launch model run", err);
    } finally {
      setLoading(false);
      setTimeout(fetchLatestRun, 1500);
    }
  };

  const metrics = latestRun?.metrics;

  return (
    <div className="bg-gray-800 p-5 rounded-lg shadow-lg border border-gray-700 space-y-4">
      <div className="flex justify-between items-center border-b border-gray-700 pb-3">
        <h2 className="text-lg font-bold text-blue-400 flex items-center">
          <span className="mr-2">🌊</span> Baseline Urban Flood Model
        </h2>
        <span className={`text-xs px-2.5 py-1 rounded-full font-bold uppercase ${
          latestRun?.status === 'COMPLETED' ? 'bg-green-900 text-green-300 border border-green-700' :
          latestRun?.status === 'RUNNING' ? 'bg-yellow-900 text-yellow-300 border border-yellow-700 animate-pulse' :
          'bg-gray-700 text-gray-300'
        }`}>
          {latestRun?.status || 'IDLE'}
        </span>
      </div>

      {/* Model Simulation Controller */}
      <div className="bg-gray-900 p-3 rounded-md space-y-3">
        <div className="flex justify-between items-center text-xs text-gray-300">
          <label htmlFor="rainfall-forcing" className="font-semibold">Simulated Storm Rainfall Forcing:</label>
          <span className="font-bold text-blue-400 text-sm">{rainfallInput} mm</span>
        </div>
        <input
          id="rainfall-forcing"
          type="range"
          min="20"
          max="120"
          step="5"
          value={rainfallInput}
          onChange={(e) => setRainfallInput(Number(e.target.value))}
          className="w-full h-1.5 bg-gray-700 rounded cursor-pointer accent-blue-500"
        />
        <button
          onClick={handleRunModel}
          disabled={loading || latestRun?.status === 'RUNNING'}
          className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white font-bold text-xs uppercase tracking-wider rounded transition-colors shadow"
        >
          {loading || latestRun?.status === 'RUNNING' ? 'Executing Physics Engine...' : 'Run Flood Simulation'}
        </button>
      </div>

      {/* Real Calculated Model Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-gray-900 p-2.5 rounded border border-gray-800">
            <span className="text-gray-400 block mb-1">Inundated Area</span>
            <span className="text-base font-extrabold text-white">{metrics.affected_area_sqkm} km²</span>
          </div>
          <div className="bg-gray-900 p-2.5 rounded border border-gray-800">
            <span className="text-gray-400 block mb-1">Max Water Depth</span>
            <span className="text-base font-extrabold text-red-400">{metrics.max_depth_m} m</span>
          </div>
          <div className="bg-gray-900 p-2.5 rounded border border-gray-800">
            <span className="text-gray-400 block mb-1">Mean Water Depth</span>
            <span className="text-base font-extrabold text-yellow-400">{metrics.mean_depth_m} m</span>
          </div>
          <div className="bg-gray-900 p-2.5 rounded border border-gray-800">
            <span className="text-gray-400 block mb-1">Inundated Grid Cells</span>
            <span className="text-base font-extrabold text-blue-300">{metrics.affected_cells} cells</span>
          </div>
        </div>
      )}

      {/* Risk Category Distribution */}
      {metrics?.risk_counts && (
        <div className="space-y-1 text-xs">
          <span className="text-gray-400 block font-semibold mb-1">Risk Classification Breakdown:</span>
          <div className="flex justify-between items-center bg-gray-900 px-3 py-1.5 rounded">
            <span className="text-cyan-400 flex items-center">
              <span className="w-2 h-2 bg-cyan-400 rounded-full inline-block mr-1.5"></span> Low (&lt; 0.15m)
            </span>
            <span className="font-bold">{metrics.risk_counts.low}</span>
          </div>
          <div className="flex justify-between items-center bg-gray-900 px-3 py-1.5 rounded">
            <span className="text-yellow-400 flex items-center">
              <span className="w-2 h-2 bg-yellow-400 rounded-full inline-block mr-1.5"></span> Moderate (0.15-0.35m)
            </span>
            <span className="font-bold">{metrics.risk_counts.moderate}</span>
          </div>
          <div className="flex justify-between items-center bg-gray-900 px-3 py-1.5 rounded">
            <span className="text-orange-400 flex items-center">
              <span className="w-2 h-2 bg-orange-400 rounded-full inline-block mr-1.5"></span> High (0.35-0.60m)
            </span>
            <span className="font-bold">{metrics.risk_counts.high}</span>
          </div>
          <div className="flex justify-between items-center bg-gray-900 px-3 py-1.5 rounded">
            <span className="text-red-400 flex items-center">
              <span className="w-2 h-2 bg-red-500 rounded-full inline-block mr-1.5"></span> Severe (&ge; 0.60m)
            </span>
            <span className="font-bold">{metrics.risk_counts.severe}</span>
          </div>
        </div>
      )}

      {/* Explicit Data Provenance & Safety Disclaimer */}
      <div className="bg-gray-900/90 p-3 rounded text-[11px] border border-yellow-600/40 text-gray-300 space-y-1">
        <div className="text-yellow-400 font-bold flex items-center">
          <span>⚠️ DEVELOPMENT MODEL — NOT FOR OPERATIONAL USE</span>
        </div>
        <div>Rainfall Source: <strong className="text-white">DevelopmentRainfallProvider (SIMULATED)</strong></div>
        <div>DEM Source: <strong className="text-white">{latestRun?.dem_source || 'Synthetic DEM - DEVELOPMENT DATA'}</strong></div>
        <div>Model Version: <strong className="text-white">{latestRun?.model_name || 'Baseline Urban Flood Model'} v{latestRun?.model_version || '0.1.0'}</strong></div>
      </div>
    </div>
  );
}

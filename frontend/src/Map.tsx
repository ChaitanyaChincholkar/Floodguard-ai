import { useState, useEffect, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, GeoJsonLayer } from '@deck.gl/layers';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

const INITIAL_VIEW_STATE = {
  longitude: 77.5946,
  latitude: 12.9716, // Bangalore coordinates
  zoom: 11,
  pitch: 45,
  bearing: 0
};

interface GISMapProps {
  selectedRunId?: number | null;
}

export function GISMap({ selectedRunId }: GISMapProps) {
  const [rainfallData, setRainfallData] = useState<any>(null);
  const [floodData, setFloodData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showRainfall, setShowRainfall] = useState(true);
  const [showFloodExtent, setShowFloodExtent] = useState(true);
  const [timeIndex, setTimeIndex] = useState(100);

  // Fetch Rainfall Point Observation GeoJSON
  useEffect(() => {
    fetch('/api/v1/geospatial/rainfall')
      .then(res => res.json())
      .then(geoJson => {
        setRainfallData(geoJson);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load rainfall map data", err);
        setLoading(false);
      });
  }, []);

  // Fetch Flood Model Prediction GeoJSON
  useEffect(() => {
    const fetchFloodGeoJson = async () => {
      try {
        let runIdToFetch = selectedRunId;
        if (!runIdToFetch) {
          const runRes = await fetch('/api/v1/model/runs/latest');
          if (runRes.ok) {
            const runInfo = await runRes.json();
            runIdToFetch = runInfo.id;
          }
        }
        if (runIdToFetch) {
          const res = await fetch(`/api/v1/model/runs/${runIdToFetch}/geojson`);
          if (res.ok) {
            const geoJson = await res.json();
            setFloodData(geoJson);
          }
        }
      } catch (err) {
        console.error("Failed to load flood prediction geojson", err);
      }
    };

    fetchFloodGeoJson();
    const interval = setInterval(fetchFloodGeoJson, 5000);
    return () => clearInterval(interval);
  }, [selectedRunId]);

  // Filter rainfall data based on time slider
  const filteredRainfallData = useMemo(() => {
    if (!rainfallData || !rainfallData.features) return [];
    
    const sorted = [...rainfallData.features].sort((a: any, b: any) => 
        new Date(a.properties.timestamp).getTime() - new Date(b.properties.timestamp).getTime()
    );
    
    const cutoff = Math.floor((timeIndex / 100) * sorted.length);
    return sorted.slice(0, cutoff === 0 ? 1 : cutoff);
  }, [rainfallData, timeIndex]);

  const latestTimestamp = filteredRainfallData.length > 0 
    ? new Date(filteredRainfallData[filteredRainfallData.length - 1].properties.timestamp).toLocaleString()
    : 'No data';

  const layers = [
    // 1. Flood Inundation Prediction Polygon Layer
    showFloodExtent && floodData && new GeoJsonLayer({
      id: 'flood-extent-layer',
      data: floodData,
      filled: true,
      stroked: true,
      extruded: true,
      wireframe: false,
      getPolygon: (d: any) => d.geometry.coordinates,
      getElevation: (d: any) => (d.properties.predicted_depth_m || 0.1) * 80,
      getFillColor: (d: any) => {
        const risk = d.properties.risk_level;
        if (risk === 'severe' || risk === 'very_high') return [220, 0, 80, 210]; // Red/Purple
        if (risk === 'high') return [255, 120, 0, 190]; // Orange
        if (risk === 'moderate') return [255, 210, 0, 170]; // Yellow
        return [0, 200, 255, 140]; // Cyan / Low
      },
      getLineColor: [255, 255, 255, 80],
      getLineWidth: 1,
      lineWidthUnits: 'pixels',
      pickable: true,
      autoHighlight: true,
      updateTriggers: {
        data: [floodData]
      }
    }),

    // 2. Rainfall Point Observations Layer
    showRainfall && new ScatterplotLayer({
      id: 'rainfall-layer',
      data: filteredRainfallData,
      getPosition: (d: any) => d.geometry.coordinates,
      getFillColor: (d: any) => {
        const mm = d.properties.rainfall_mm;
        if (mm > 40) return [255, 0, 0, 230];
        if (mm > 15) return [255, 165, 0, 230];
        return [0, 255, 0, 230];
      },
      getRadius: (d: any) => d.properties.rainfall_mm * 10 + 60,
      radiusUnits: 'meters',
      pickable: true,
      autoHighlight: true,
      updateTriggers: {
        data: [filteredRainfallData]
      }
    })
  ].filter(Boolean);

  const renderTooltip = ({ object }: any) => {
    if (!object) return null;
    const props = object.properties;

    // Check if hovered element is a Flood Prediction polygon
    if (props.predicted_depth_m !== undefined) {
      return {
        html: `
          <div style="font-family: system-ui, sans-serif; padding: 6px; font-size: 12px; line-height: 1.4;">
            <div style="font-weight: bold; color: #60a5fa; border-bottom: 1px solid #374151; padding-bottom: 4px; margin-bottom: 4px;">
              🌊 INUNDATION PREDICTION ZONE
            </div>
            <div><strong>Risk Level:</strong> <span style="text-transform: uppercase; color: ${
              props.risk_level === 'severe' || props.risk_level === 'very_high' ? '#f87171' :
              props.risk_level === 'high' ? '#fb923c' :
              props.risk_level === 'moderate' ? '#facc15' : '#38bdf8'
            }">${props.risk_level}</span></div>
            <div><strong>Predicted Water Depth:</strong> <span style="color: #60a5fa; font-weight: bold;">${props.predicted_depth_m.toFixed(2)} m</span></div>
            <div><strong>Storm Rainfall Input:</strong> ${props.rainfall_mm} mm</div>
            <div><strong>Terrain Elevation:</strong> ${props.elevation_m} m</div>
            <div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid #374151; color: #fbbf24; font-size: 10px;">
              ⚠️ Status: <strong>SIMULATED (Development Model)</strong>
            </div>
          </div>
        `
      };
    }

    // Rainfall observation point
    return {
      html: `
        <div style="font-family: system-ui, sans-serif; padding: 6px; font-size: 12px;">
          <div><strong>Rainfall Observation:</strong> ${props.rainfall_mm.toFixed(2)} mm</div>
          <div><strong>Status:</strong> ${props.data_status.toUpperCase()}</div>
          <div><strong>Timestamp:</strong> ${new Date(props.timestamp).toLocaleString()}</div>
        </div>
      `
    };
  };

  return (
    <div className="relative w-full h-full min-h-[600px] overflow-hidden flex flex-col">
      <div className="flex-1 relative">
        <DeckGL
          initialViewState={INITIAL_VIEW_STATE}
          controller={true}
          layers={layers}
          getTooltip={renderTooltip}
        >
          <Map
            mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          />
        </DeckGL>

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900 bg-opacity-75 text-white z-10 font-medium">
            Loading geospatial & flood prediction layers...
          </div>
        )}

        {/* Map Controls & Legends Overlay */}
        <div className="absolute top-4 right-4 bg-gray-800/95 p-4 rounded-lg shadow-2xl text-white text-xs border border-gray-700 z-10 pointer-events-auto space-y-3 max-w-[240px]">
          <div>
            <h4 className="font-bold text-gray-200 border-b border-gray-700 pb-1 mb-2">Map Layers</h4>
            <label className="flex items-center mb-1.5 cursor-pointer">
              <input type="checkbox" checked={showFloodExtent} onChange={e => setShowFloodExtent(e.target.checked)} className="mr-2 rounded accent-blue-500" />
              <span>Show Flood Extent Layer</span>
            </label>
            <label className="flex items-center cursor-pointer">
              <input type="checkbox" checked={showRainfall} onChange={e => setShowRainfall(e.target.checked)} className="mr-2 rounded accent-blue-500" />
              <span>Show Rainfall Observations</span>
            </label>
          </div>
          
          {/* Flood Risk Legend */}
          <div>
            <h4 className="font-bold text-blue-400 border-b border-gray-700 pb-1 mb-2">Flood Water Depth (m)</h4>
            <div className="flex items-center mb-1"><span className="w-3 h-3 bg-cyan-400 rounded-sm inline-block mr-2 shadow"></span> 0.05 - 0.15 m (Low)</div>
            <div className="flex items-center mb-1"><span className="w-3 h-3 bg-yellow-400 rounded-sm inline-block mr-2 shadow"></span> 0.15 - 0.35 m (Moderate)</div>
            <div className="flex items-center mb-1"><span className="w-3 h-3 bg-orange-500 rounded-sm inline-block mr-2 shadow"></span> 0.35 - 0.60 m (High)</div>
            <div className="flex items-center mb-1"><span className="w-3 h-3 bg-red-600 rounded-sm inline-block mr-2 shadow"></span> &ge; 0.60 m (Severe)</div>
          </div>
          
          <div className="border-t border-gray-700 pt-2 text-[10px]">
            <span className="font-bold text-yellow-500 block">⚠️ DEVELOPMENT DATA</span>
            <span className="text-gray-300">Status: <strong className="text-white">SIMULATED MODEL</strong></span>
          </div>
        </div>
      </div>

      {/* Time Slider Controls */}
      <div className="h-20 bg-gray-950 border-t border-gray-800 px-6 py-3 flex flex-col justify-center">
        <div className="flex justify-between text-xs text-gray-400 mb-1.5">
          <span>Historical Rainfall Window</span>
          <span className="font-bold text-white">Current View: {latestTimestamp}</span>
          <span>Latest Available</span>
        </div>
        <input 
          type="range" 
          min="0" max="100" 
          value={timeIndex} 
          onChange={(e) => setTimeIndex(Number(e.target.value))}
          className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
        />
      </div>
    </div>
  );
}

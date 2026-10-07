import { useState, useEffect } from 'react';

type DataSource = {
  id: number;
  name: string;
  provider_type: string;
  data_type: string | null;
  health_status: string;
  last_synced: string | null;
};

export function StatusPanel() {
  const [providers, setProviders] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/data/status')
      .then((res) => res.json())
      .then((data) => {
        setProviders(data.providers || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch data status", err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="bg-gray-800 p-6 rounded-lg shadow-lg text-white">
      <h2 className="text-xl font-bold mb-4 text-blue-400">Data Sources & Status</h2>
      {loading ? (
        <p>Loading...</p>
      ) : providers.length === 0 ? (
        <p className="text-gray-400">No data sources configured yet.</p>
      ) : (
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="pb-2">Provider</th>
              <th className="pb-2">Type</th>
              <th className="pb-2">Status</th>
              <th className="pb-2">Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => (
              <tr key={p.id} className="border-b border-gray-700 last:border-0">
                <td className="py-2">{p.name} <span className="text-xs bg-yellow-600 px-2 py-1 rounded ml-2">{p.provider_type === 'development' ? 'SIMULATED' : 'LIVE'}</span></td>
                <td className="py-2 capitalize">{p.data_type || 'Unknown'}</td>
                <td className="py-2">
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${p.health_status === 'healthy' ? 'bg-green-600' : 'bg-red-600'}`}>
                    {p.health_status.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 text-gray-400">
                  {p.last_synced ? new Date(p.last_synced).toLocaleString() : 'Never'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

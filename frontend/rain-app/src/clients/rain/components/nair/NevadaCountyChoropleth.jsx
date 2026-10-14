import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

const RAIN_NAVY = '#003366';
const NV_PATH = 'M14 10 L150 10 L150 196 L86 250 L14 92 Z';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

// Stylized region shapes stay local -- decorative illustration geometry,
// not data. Keyed by county name so they can be paired with whichever
// risk level the backend reports for that county.
const REGION_PATHS = {
  Humboldt: 'M40 28 L96 28 L98 70 L44 74 Z',
  Pershing: 'M44 74 L98 70 L100 104 L48 108 Z',
  Lander: 'M100 60 L128 58 L130 110 L102 112 Z',
};

const fill = { critical: '#DC2626', high: '#D97706', warning: '#CA8A04' };

export default function NevadaCountyChoropleth() {
  const [summary, setSummary] = useState({ population_served: '', avoidable_ed_rate_per_1000: null, regions: [], legend: [] });

  useEffect(() => {
    fetch(`${API_BASE}/ultra/rain/countyRisk`)
      .then((r) => r.json())
      .then(setSummary)
      .catch(() => {});
  }, []);

  const { population_served, avoidable_ed_rate_per_1000, regions, legend } = summary;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">County Access-Risk Heat — Frontier Nevada</p>
        <span className="text-[10px] font-semibold text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">{population_served} served</span>
      </div>
      <div className="flex gap-4">
        <svg viewBox="0 0 164 262" className="w-[140px] flex-shrink-0">
          <path d={NV_PATH} fill="#EEF2F7" stroke="#CBD5E1" strokeWidth="1.5" strokeLinejoin="round" />
          {regions.map((r) => (
            <path key={r.name} d={REGION_PATHS[r.name]} fill={fill[r.risk]} fillOpacity="0.5" stroke={fill[r.risk]} strokeWidth="1" />
          ))}
          {/* closure marker */}
          <g>
            <rect x="64" y="46" width="9" height="9" rx="1.5" fill="#fff" stroke="#DC2626" strokeWidth="1.5" />
            <line x1="66" y1="48" x2="71" y2="53" stroke="#DC2626" strokeWidth="1.4" />
            <line x1="71" y1="48" x2="66" y2="53" stroke="#DC2626" strokeWidth="1.4" />
          </g>
        </svg>

        <div className="flex-1 space-y-2">
          {regions.map((r) => (
            <div key={r.name} className="bg-white rounded-lg border border-gray-100 px-2.5 py-1.5 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: fill[r.risk] }} />
              <span className="text-[11px] font-semibold text-gray-700 flex-1">{r.name}</span>
              <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded" style={{ color: fill[r.risk], backgroundColor: `${fill[r.risk]}1a` }}>{r.risk}</span>
            </div>
          ))}
          <div className="bg-white rounded-lg border border-gray-100 p-2 mt-1">
            <p className="text-[9px] uppercase tracking-wider text-gray-400 font-semibold">Avoidable ED rate (per 1,000)</p>
            <p className="text-[13px] font-bold" style={{ color: RAIN_NAVY }}>{avoidable_ed_rate_per_1000} <span className="text-[10px] font-normal text-gray-400">concentrated in affected ZIPs</span></p>
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] text-gray-500 border-t border-gray-100 pt-2 mt-2">
        {legend.map((l) => (
          <span key={l.label} className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: fill[l.risk] }} /> {l.label}</span>
        ))}
      </div>
    </motion.div>
  );
}

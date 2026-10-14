import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';

// The original static card, kept as the offline fallback.
export function StaticTripTelehealthConversion() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Trip → Telehealth Conversion</p>
        <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded">13 convertible</span>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {[['13', 'Convertible trips', RAIN_NAVY], ['7', 'Home-capable (no room)', '#059669'], ['6', 'Need a room slot', '#D97706']].map(([n, l, c]) => (
          <div key={l} className="bg-white rounded-lg p-2 border border-gray-100 text-center">
            <p className="text-[16px] font-bold" style={{ color: c }}>{n}</p>
            <p className="text-[9px] text-gray-500 leading-tight mt-0.5">{l}</p>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <div className="bg-white rounded-lg p-2.5 border border-gray-100">
          <div className="flex items-center justify-between text-[10px] mb-1">
            <span className="font-semibold text-gray-700">Vehicles freed</span>
            <span className="font-bold" style={{ color: RAIN_NAVY }}>+2 for afternoon dialysis</span>
          </div>
          <div className="flex items-center justify-between text-[10px]">
            <span className="font-semibold text-gray-700">EMS response (north)</span>
            <span className="font-bold text-emerald-600">47 min → &lt; 38 min by afternoon</span>
          </div>
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mt-2">Converting 13 trips clears the 9-trip overflow and returns crews to emergency coverage.</p>
    </motion.div>
  );
}

// Live: the dataset has no field marking a transport as convertible to
// telehealth, no room-slot data, and no dialysis concept -- so none of the
// static card's 13/7/6 split, EMS projection, or vehicle-reallocation claim
// can be computed. This shows the one real, verified proxy figure instead:
// scheduled transports whose patient also has an eligible telehealth
// session booked today. See james_ops_live.py.
export default function TripTelehealthConversion() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('TripTelehealthConversion', 'james')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticTripTelehealthConversion />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Loading transport-telehealth overlap…</div>;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Trip → Telehealth Overlap</p>
        <span className="text-[10px] font-semibold text-slate-600 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded">proxy estimate</span>
      </div>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[18px] font-bold" style={{ color: RAIN_NAVY }}>{data.proxy_convertible}</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">also have an eligible telehealth session today</p>
        </div>
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[18px] font-bold text-gray-700">{data.scheduled_today}</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">transports scheduled today</p>
        </div>
      </div>
      <p className="text-[9.5px] text-gray-500 leading-snug bg-amber-50 border border-amber-100 rounded-lg p-2">{data.method}</p>
      <p className="text-[9px] text-gray-400 mt-2 leading-snug">{data.note}</p>
    </motion.div>
  );
}

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Baby, HeartPulse, Activity, Truck, WifiOff } from 'lucide-react';

const RAIN_NAVY = '#003366';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

// Branch id (from the backend) -> the real lucide-react icon. A component
// reference can't travel over JSON, so the backend sends an id and this
// maps it back -- same pattern used for KPI and data-source icons.
const BRANCH_ICON_MAP = {
  'maternal-access': Baby,
  'chronic-continuity': HeartPulse,
  'ed-utilization': Activity,
  'transport-strain': Truck,
  'telehealth-equity': WifiOff,
};

export default function CascadeDiagram() {
  const [branches, setBranches] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/ultra/rain/cascade`)
      .then((r) => r.json())
      .then(setBranches)
      .catch(() => setBranches([]));
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <p className="text-xs font-semibold text-gray-600 mb-3">One Closure → Five Interconnected Effects</p>
      <div className="flex justify-center mb-3">
        <div className="px-3 py-1.5 rounded-lg text-white text-[11px] font-bold text-center" style={{ backgroundColor: RAIN_NAVY }}>
          Battle Mountain L&amp;D Closure
          <span className="block text-[8.5px] font-medium opacity-80">March 1, 2026</span>
        </div>
      </div>
      <div className="relative pl-4 space-y-2">
        <div className="absolute left-1 top-1 bottom-2 w-px bg-gray-200" />
        {branches.map((b) => {
          const Icon = BRANCH_ICON_MAP[b.id];
          return (
            <div key={b.id} className="relative bg-white rounded-lg border border-gray-100 p-2.5 flex items-start gap-2.5">
              <span className="absolute -left-3 top-4 w-2 h-2 rounded-full" style={{ backgroundColor: RAIN_NAVY }} />
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${RAIN_NAVY}12` }}>
                {Icon ? <Icon className="w-3.5 h-3.5" style={{ color: RAIN_NAVY }} /> : null}
              </div>
              <div className="flex-1">
                <p className="text-[11px] font-semibold text-gray-800">{b.label}</p>
                <p className="text-[10px] font-bold text-gray-700">{b.metric}</p>
                <p className="text-[9px] text-gray-400 leading-tight">{b.sub}</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-gray-400 mt-2">No single system surfaces this cascade — it only appears when all seven domains are read together.</p>
    </motion.div>
  );
}

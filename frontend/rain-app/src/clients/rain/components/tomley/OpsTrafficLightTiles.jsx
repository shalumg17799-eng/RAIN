import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Truck, Video, Ambulance, Building2, BedDouble } from 'lucide-react';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const ICONS = { Truck, Video, Ambulance, Building2 };

const colors = {
  red: { bg: 'bg-red-50', br: 'border-red-200', dot: 'bg-red-500', tx: 'text-red-700' },
  yellow: { bg: 'bg-amber-50', br: 'border-amber-200', dot: 'bg-amber-500', tx: 'text-amber-700' },
  green: { bg: 'bg-emerald-50', br: 'border-emerald-200', dot: 'bg-emerald-500', tx: 'text-emerald-700' },
  // Genuinely neutral -- used where no threshold exists to judge the number against,
  // so it is never shown as a false red/yellow alarm.
  info: { bg: 'bg-slate-50', br: 'border-slate-200', dot: 'bg-slate-400', tx: 'text-slate-600' },
};

// The original static card, kept as the offline fallback.
const STATIC_TILES = [
  { icon: Truck, label: 'Transport Queue', value: '+9 over', status: 'red' },
  { icon: Video, label: 'Telehealth Capacity', value: '31 unslotted', status: 'red' },
  { icon: Ambulance, label: 'EMS Response', value: '47 min', status: 'yellow' },
  { icon: Building2, label: 'Mobile Clinic', value: '98% util', status: 'yellow' },
  { icon: BedDouble, label: 'Facility Beds', value: 'Available', status: 'green' },
];

export function StaticOpsTrafficLightTiles() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <p className="text-xs font-semibold text-gray-600 mb-3">Daily Operations Status</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {STATIC_TILES.map((t) => {
          const Icon = t.icon; const c = colors[t.status];
          return (
            <div key={t.label} className={`rounded-lg border p-2.5 ${c.bg} ${c.br}`}>
              <div className="flex items-center justify-between mb-1">
                <Icon className={`w-4 h-4 ${c.tx}`} />
                <span className={`w-2 h-2 rounded-full ${c.dot}`} />
              </div>
              <p className="text-[10px] font-semibold text-gray-700 leading-tight">{t.label}</p>
              <p className={`text-[11px] font-bold ${c.tx}`}>{t.value}</p>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

// Live: 4 real tiles computed from the backend on each load. Two of the
// static card's 5 tiles (Mobile Clinic utilization, Facility beds) had no
// backing anywhere in the dataset and are not reproduced -- see
// james_ops_live.py. A short note says so instead of silently dropping them.
export default function OpsTrafficLightTiles() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('OpsTrafficTiles', 'james')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticOpsTrafficLightTiles />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Loading operations status…</div>;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <p className="text-xs font-semibold text-gray-600 mb-3">Daily Operations Status</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {data.tiles.map((t) => {
          const Icon = ICONS[t.icon] || Truck; const c = colors[t.status] || colors.info;
          return (
            <div key={t.label} className={`rounded-lg border p-2.5 ${c.bg} ${c.br}`} title={t.detail}>
              <div className="flex items-center justify-between mb-1">
                <Icon className={`w-4 h-4 ${c.tx}`} />
                <span className={`w-2 h-2 rounded-full ${c.dot}`} />
              </div>
              <p className="text-[10px] font-semibold text-gray-700 leading-tight">{t.label}</p>
              <p className={`text-[11px] font-bold ${c.tx}`}>{t.value}</p>
            </div>
          );
        })}
      </div>
      {data.omitted && data.omitted.length > 0 && (
        <p className="text-[9px] text-gray-400 mt-2 leading-tight">
          Not shown (no data in the system for these): {data.omitted.join(', ')}.
        </p>
      )}
    </motion.div>
  );
}

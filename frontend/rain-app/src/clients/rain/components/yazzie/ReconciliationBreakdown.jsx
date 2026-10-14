import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';

// The original static card, kept as the offline fallback.
const STATIC_TYPES = [
  { label: 'Encounters', count: 620 },
  { label: 'Orders', count: 410 },
  { label: 'Pending claims', count: 210 },
];
const STATIC_TOTAL = 1240;

export function StaticReconciliationBreakdown() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Provider Reconciliation Failure</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">1,240 unresolved</span>
      </div>
      <div className="space-y-2 mb-3">
        {STATIC_TYPES.map((t) => (
          <div key={t.label}>
            <div className="flex items-center justify-between text-[11px] mb-0.5">
              <span className="font-semibold text-gray-700">{t.label}</span>
              <span className="text-gray-500">{t.count.toLocaleString()}</span>
            </div>
            <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(t.count / STATIC_TOTAL) * 100}%`, backgroundColor: RAIN_NAVY }} />
            </div>
          </div>
        ))}
      </div>
      <div className="bg-white rounded-lg border border-gray-100 p-2.5 mb-2">
        <p className="text-[9px] uppercase tracking-wider text-gray-400 font-semibold mb-1.5">Provider lifecycle</p>
        <div className="flex items-center gap-1.5 text-[9px]">
          <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold">Active (pre-Mar 1)</span>
          <span className="text-gray-300">→</span>
          <span className="px-1.5 py-0.5 rounded bg-red-50 text-red-700 font-semibold">Deactivated Mar 1</span>
          <span className="text-gray-300">→</span>
          <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-semibold">1,240 records orphaned</span>
        </div>
      </div>
      <div className="flex items-center justify-between bg-white rounded-lg border border-gray-100 px-2.5 py-2">
        <span className="text-[10px] font-semibold text-gray-700">Crosswalk mismatches</span>
        <span className="text-[12px] font-bold text-amber-600">180</span>
      </div>
      <p className="text-[10px] text-gray-400 mt-2">Fixable with a claims-only active flag on the deactivated NPIs plus a panel crosswalk update.</p>
    </motion.div>
  );
}

function monthDay(iso) {
  if (!iso) return '';
  const [, m, d] = iso.split('-');
  return `${['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][parseInt(m, 10)]} ${parseInt(d, 10)}`;
}

// Live: the type breakdown, total, crosswalk count, and deactivation date all
// come from the backend, computed fresh from rain.db (see david_data_health.py).
export default function ReconciliationBreakdown() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('ReconciliationBreakdown', 'david')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticReconciliationBreakdown />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Loading reconciliation detail…</div>;
  }

  const closure = monthDay(data.deactivation_date);
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Provider Reconciliation Failure</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">{data.total.toLocaleString()} unresolved</span>
      </div>
      <div className="space-y-2 mb-3">
        {data.types.map((t) => (
          <div key={t.label}>
            <div className="flex items-center justify-between text-[11px] mb-0.5">
              <span className="font-semibold text-gray-700">{t.label}</span>
              <span className="text-gray-500">{t.count.toLocaleString()}</span>
            </div>
            <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(t.count / data.total) * 100}%`, backgroundColor: RAIN_NAVY }} />
            </div>
          </div>
        ))}
      </div>
      <div className="bg-white rounded-lg border border-gray-100 p-2.5 mb-2">
        <p className="text-[9px] uppercase tracking-wider text-gray-400 font-semibold mb-1.5">Provider lifecycle</p>
        <div className="flex items-center gap-1.5 text-[9px]">
          <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold">Active (pre-{closure})</span>
          <span className="text-gray-300">→</span>
          <span className="px-1.5 py-0.5 rounded bg-red-50 text-red-700 font-semibold">Deactivated {closure}</span>
          <span className="text-gray-300">→</span>
          <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-semibold">{data.total.toLocaleString()} records orphaned</span>
        </div>
      </div>
      <div className="flex items-center justify-between bg-white rounded-lg border border-gray-100 px-2.5 py-2">
        <span className="text-[10px] font-semibold text-gray-700">Crosswalk mismatches</span>
        <span className="text-[12px] font-bold text-amber-600">{data.crosswalk_mismatches}</span>
      </div>
      <p className="text-[10px] text-gray-400 mt-2">{data.note}</p>
    </motion.div>
  );
}

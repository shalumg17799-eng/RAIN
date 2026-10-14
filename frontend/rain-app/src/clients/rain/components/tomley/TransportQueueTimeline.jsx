import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';

// The original static card, kept as the offline fallback.
const STATIC_HOURS = [
  { h: '7a', prenatal: 2, chronic: 2, cap: 6 }, { h: '8a', prenatal: 5, chronic: 5, cap: 6 },
  { h: '9a', prenatal: 6, chronic: 5, cap: 6 }, { h: '10a', prenatal: 4, chronic: 4, cap: 6 },
  { h: '11a', prenatal: 3, chronic: 3, cap: 6 }, { h: '12p', prenatal: 2, chronic: 2, cap: 6 },
  { h: '1p', prenatal: 1, chronic: 3, cap: 6 }, { h: '2p', prenatal: 1, chronic: 2, cap: 6 },
];
const STATIC_MAX_V = 12;

export function StaticTransportQueueTimeline() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Transport Queue by Hour — Corridor Collision</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">8–11a peak</span>
      </div>
      <div className="flex items-end justify-between gap-1.5 h-28 mb-2">
        {STATIC_HOURS.map((d) => {
          const total = d.prenatal + d.chronic; const over = total > d.cap;
          return (
            <div key={d.h} className="flex-1 flex flex-col items-center justify-end h-full">
              <div className="w-full flex flex-col justify-end items-stretch h-full relative">
                <div className="absolute left-0 right-0 border-t border-dashed border-gray-400" style={{ bottom: `${(d.cap / STATIC_MAX_V) * 100}%` }} />
                <div className="rounded-t-sm" style={{ height: `${(d.prenatal / STATIC_MAX_V) * 100}%`, backgroundColor: over ? '#DC2626' : RAIN_NAVY }} />
                <div style={{ height: `${(d.chronic / STATIC_MAX_V) * 100}%`, backgroundColor: over ? '#F87171' : '#7C9CC4' }} />
              </div>
              <span className="text-[8px] text-gray-400 mt-1">{d.h}</span>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] text-gray-500 border-t border-gray-100 pt-2">
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: RAIN_NAVY }} /> Prenatal (115mi corridor)</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: '#7C9CC4' }} /> Dialysis / oncology</span>
        <span className="flex items-center gap-1"><span className="w-3 border-t border-dashed border-gray-400" /> Vehicle capacity (6)</span>
      </div>
      <p className="text-[10px] text-gray-400 mt-2">14 trips requested 8–11a against 6 vehicles · 3 patients double-booked across EMS/NEMT.</p>
    </motion.div>
  );
}

const TYPE_COLOR = { EMS: '#DC2626', NEMT: RAIN_NAVY };

// Live: the static card's hourly chart, "dialysis/oncology" category, and
// vehicle capacity of 6 have no basis anywhere in the dataset -- no
// hour-of-day field, no vehicle/fleet table. Shown instead: today's real
// request-type and schedule-status split -- see james_ops_live.py.
export default function TransportQueueTimeline() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('TransportQueueBreakdown', 'james')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticTransportQueueTimeline />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Loading today's transport queue…</div>;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Transport Queue — Today</p>
        <span className="text-[10px] font-semibold text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">{data.total} requests</span>
      </div>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[18px] font-bold text-emerald-600">{data.scheduled}</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Scheduled</p>
        </div>
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[18px] font-bold text-red-600">{data.unscheduled}</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Unscheduled</p>
        </div>
      </div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1.5">By request type</p>
      <div className="space-y-2 mb-2">
        {data.by_type.map((t) => (
          <div key={t.label}>
            <div className="flex items-center justify-between text-[11px] mb-0.5">
              <span className="font-semibold text-gray-700">{t.label}</span>
              <span className="text-gray-500">{t.count}</span>
            </div>
            <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(t.count / data.total) * 100}%`, backgroundColor: TYPE_COLOR[t.label] || RAIN_NAVY }} />
            </div>
          </div>
        ))}
      </div>
      <p className="text-[9.5px] text-gray-400 leading-snug">{data.note}</p>
    </motion.div>
  );
}

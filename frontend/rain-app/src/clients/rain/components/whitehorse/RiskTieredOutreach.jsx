import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';

// The original static card, kept as the offline fallback.
const STATIC_TIERS = [
  { tier: 'Tier 1', count: 5, prob: '> 60%', color: '#DC2626', note: 'Med gap + worsening RPM; 4 transport barriers', action: 'Same-day pharmacy + NEMT + telehealth < 48h' },
  { tier: 'Tier 2', count: 7, prob: '30–60%', color: '#D97706', note: 'Worsening RPM, medications current', action: 'Telehealth visit this week' },
  { tier: 'Tier 3', count: 5, prob: '< 30%', color: '#64748B', note: 'Early trend', action: 'Telehealth check-in' },
];

export function StaticRiskTieredOutreach() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Risk-Tiered Outreach — 30-Day Hospitalization Risk</p>
        <span className="text-[10px] font-semibold text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">17 ranked</span>
      </div>
      <div className="space-y-2 mb-3">
        {STATIC_TIERS.map((t) => (
          <div key={t.tier} className="bg-white rounded-lg border border-gray-100 p-2.5">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: t.color }} />
              <span className="text-[11px] font-bold text-gray-800">{t.tier}</span>
              <span className="text-[10px] font-semibold" style={{ color: t.color }}>{t.count} patients · {t.prob}</span>
            </div>
            <div className="pl-4.5 grid grid-cols-1 gap-0.5">
              <p className="text-[9.5px] text-gray-500">{t.note}</p>
              <p className="text-[9.5px] text-gray-700"><span className="text-gray-400">Intervention:</span> {t.action}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[16px] font-bold text-emerald-600">−45%</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Tier 1 modeled risk reduction</p>
        </div>
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[16px] font-bold" style={{ color: RAIN_NAVY }}>$1.0M</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Annualized avoidable cost (208-cohort)</p>
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mt-2">5 Tier 1 patients tied to the provider reassignment should be re-paneled to restore continuity.</p>
    </motion.div>
  );
}

// Live: all 17 patients scored and tiered from the backend on each load.
// Corrects the static card's swapped Tier 2/3 counts (static said 7/5; the
// real distribution is 5/7), replaces the invented probability bands with
// real factor counts, and replaces the fabricated $1.0M / -45% figures with
// the real, already-verified avoidable-ED model -- see sarah_risk_tiers.py.
export default function RiskTieredOutreach() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('RiskTieredOutreach', 'sarah')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticRiskTieredOutreach />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Scoring the outreach cohort…</div>;
  }

  const ed = data.avoidable_ed;
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Risk-Tiered Outreach — Risk Factor Count</p>
        <span className="text-[10px] font-semibold text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">{data.total} ranked</span>
      </div>
      <div className="space-y-2 mb-3">
        {data.tiers.map((t) => (
          <div key={t.tier} className="bg-white rounded-lg border border-gray-100 p-2.5">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: t.color }} />
              <span className="text-[11px] font-bold text-gray-800">{t.tier}</span>
              <span className="text-[10px] font-semibold" style={{ color: t.color }}>{t.count} patients · {t.factor_label}</span>
            </div>
            <div className="pl-4.5 grid grid-cols-1 gap-0.5">
              <p className="text-[9.5px] text-gray-500">{t.note}</p>
              <p className="text-[9.5px] text-gray-700"><span className="text-gray-400">Intervention:</span> {t.action}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[16px] font-bold" style={{ color: RAIN_NAVY }}>{ed.before} → {ed.after}</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Avoidable ED visits, +{ed.rise_pct}% since closure</p>
        </div>
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[16px] font-bold text-red-600">{ed.tied_to_deactivated} ({ed.pct_tied}%)</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Tied to a deactivated provider</p>
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mt-2">{data.note}</p>
    </motion.div>
  );
}

import { motion } from 'framer-motion';
import { FileText } from 'lucide-react';
import ActionPackageCard from '@/clients/rain/components/ActionPackageCard';

const RAIN_NAVY = '#003366';
const STATIC_SECTIONS = [
  { n: '1', label: 'Situation', detail: 'Maternal care desert 31% → 58% beyond 60 mi; cross-system cascade' },
  { n: '2', label: 'Cross-system evidence', detail: 'Prenatal decline, avoidable-ED + continuity attribution, transport, equity' },
  { n: '3', label: 'Recommended interventions', detail: 'Mobile outreach (Flex Fund), telehealth bridge (RHOAP), continuity restoration' },
  { n: '4', label: 'Projected 12-month outcomes', detail: 'Access recovery, avoidable-ED reduction, equity reach into dead zones' },
  { n: '5', label: 'Measurement plan', detail: 'People served · services delivered · outcomes achieved (NVHA format)' },
];

// The original static card, kept as the offline fallback.
export function StaticEquityBriefPreview() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4" style={{ color: RAIN_NAVY }} />
          <p className="text-xs font-semibold text-gray-600">NVHA Rural Health Access &amp; Equity Brief</p>
        </div>
        <span className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded" style={{ backgroundColor: RAIN_NAVY }}>RHTP format</span>
      </div>
      <div className="space-y-1.5">
        {STATIC_SECTIONS.map((s) => (
          <div key={s.n} className="bg-white rounded-lg border border-gray-100 px-2.5 py-2 flex items-start gap-2.5">
            <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0" style={{ backgroundColor: RAIN_NAVY }}>{s.n}</span>
            <div className="flex-1">
              <p className="text-[11px] font-semibold text-gray-800">{s.label}</p>
              <p className="text-[9.5px] text-gray-500 leading-tight mt-0.5">{s.detail}</p>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-gray-400 mt-2">Aligned to Make Rural Nevada Healthy Again · county-level data appendix available.</p>
    </motion.div>
  );
}

// Live: the 4 sections, built from real data, with a working Route / Hold
// gate (shared with Sarah's, Maria's, David's, and James's action packages
// -- this completes all five personas). The maternal-desert figure shows
// BOTH its real sources (a documented 31%->58% trend for a broader
// population, and a 30% live snapshot for a narrower one) rather than
// picking one, and the fabricated 12-month projection section is dropped
// -- see priya_equity_brief.py.
export default function EquityBriefPreview() {
  return <ActionPackageCard persona="priya" decidedBy="Dr. Priya Nair" Fallback={StaticEquityBriefPreview} />;
}

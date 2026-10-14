import ActionPackageCard from '@/clients/rain/components/ActionPackageCard';
import { motion } from 'framer-motion';

const RAIN_NAVY = '#003366';
const STATIC_FIXES = [
  { id: '1', name: 'Provider reconciliation', effort: '1 ingestion cycle', risk: 'Low', recovery: '1,240 records resolve', recommended: true },
  { id: '2', name: 'RPM store-and-forward buffering', effort: 'Next window', risk: 'Low', recovery: '78% → ~95%', recommended: false },
  { id: '3', name: 'FHIR mapping rules', effort: 'Next window', risk: 'Low', recovery: 'Clears null-location + bad codes', recommended: false },
];

// The original static card, kept as the offline fallback.
export function StaticRemediationPlanPreview() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Data Remediation Plan</p>
        <span className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded" style={{ backgroundColor: RAIN_NAVY }}>3 fixes staged</span>
      </div>
      <div className="space-y-2 mb-3">
        {STATIC_FIXES.map((f) => (
          <div key={f.id} className={`rounded-lg border p-2.5 ${f.recommended ? 'bg-white' : 'bg-white/60 border-gray-100'}`}
            style={f.recommended ? { borderColor: RAIN_NAVY } : {}}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="w-5 h-5 rounded flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0" style={{ backgroundColor: f.recommended ? RAIN_NAVY : '#94a3b8' }}>{f.id}</span>
              <p className="text-[11px] font-semibold text-gray-800 flex-1">{f.name}</p>
              {f.recommended && <span className="text-[8px] font-bold text-white px-1.5 py-0.5 rounded uppercase" style={{ backgroundColor: RAIN_NAVY }}>Execute first</span>}
            </div>
            <div className="grid grid-cols-3 gap-1.5 pl-7">
              <div><p className="text-[8px] uppercase text-gray-400 font-semibold">Effort</p><p className="text-[9px] font-semibold text-gray-700">{f.effort}</p></div>
              <div><p className="text-[8px] uppercase text-gray-400 font-semibold">Risk</p><p className="text-[9px] font-semibold text-emerald-600">{f.risk}</p></div>
              <div><p className="text-[8px] uppercase text-gray-400 font-semibold">Recovery</p><p className="text-[9px] font-semibold text-gray-700 leading-tight">{f.recovery}</p></div>
            </div>
          </div>
        ))}
      </div>
      <div className="bg-white rounded-lg border border-gray-100 px-2.5 py-2 text-[10px] text-gray-600">
        <span className="font-semibold">+ Downstream re-run</span> refreshes maternal, chronic, and population health cohorts and notifies each clinical owner. <span className="font-semibold">+ Data-quality watch</span> alerts on feed degradation after future facility events.
      </div>
    </motion.div>
  );
}

// Live: the 3 fixes, built from real data, with a working Route / Hold gate
// (shared with Sarah's and Maria's action packages). Corrects the static
// card's wrong RPM figure (78% -> real 61%) and the unverifiable "clears
// null-location + bad codes" claim (replaced with the real weakest FHIR
// feed) -- see david_remediation_plan.py.
export default function RemediationPlanPreview() {
  return <ActionPackageCard persona="david" decidedBy="David Yazzie" Fallback={StaticRemediationPlanPreview} />;
}

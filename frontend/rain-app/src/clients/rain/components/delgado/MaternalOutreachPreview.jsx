import { motion } from 'framer-motion';
import { FileText, Video, Bus, Users } from 'lucide-react';
import ActionPackageCard from '@/clients/rain/components/ActionPackageCard';

const RAIN_NAVY = '#003366';

const items = [
  { icon: FileText, label: 'Ranked patient list', detail: '14 third-trimester, each with EHR history, registry dx, last RPM, distance' },
  { icon: Video, label: 'Telehealth referrals', detail: '8 Project ECHO Nevada prenatal referral drafts' },
  { icon: Bus, label: 'NEMT transport requests', detail: '3 hybrid + 22 with no scheduled transport' },
  { icon: Users, label: 'Cross-team handoff', detail: '3 compounding-risk cases shared with chronic disease team' },
];

// The original static card. Shown when the backend can't be reached, so the app keeps
// working offline exactly as before.
export function StaticMaternalOutreachPreview() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Priority Maternal Outreach Package</p>
        <span className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded" style={{ backgroundColor: RAIN_NAVY }}>Draft · ready to route</span>
      </div>
      <div className="space-y-2">
        {items.map((it) => {
          const Icon = it.icon;
          return (
            <div key={it.label} className="bg-white rounded-lg border border-gray-100 p-2.5 flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${RAIN_NAVY}14` }}>
                <Icon className="w-3.5 h-3.5" style={{ color: RAIN_NAVY }} />
              </div>
              <div className="flex-1">
                <p className="text-[11px] font-semibold text-gray-800">{it.label}</p>
                <p className="text-[9.5px] text-gray-500 leading-tight mt-0.5">{it.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-3 gap-2 mt-3">
        {[['8', 'Telehealth'], ['3', 'Hybrid + NEMT'], ['3', 'In-person']].map(([n, l]) => (
          <div key={l} className="bg-white rounded-lg p-2 border border-gray-100 text-center">
            <p className="text-[15px] font-bold" style={{ color: RAIN_NAVY }}>{n}</p>
            <p className="text-[9px] text-gray-500 leading-tight mt-0.5">{l}</p>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-gray-400 mt-2">Every figure links to its source record across the EHR, registry, RPM feed, and NEMT logs.</p>
    </motion.div>
  );
}

// Live: the package (ranked list, referral and NEMT drafts, chronic-team handoff) is built
// from the database by the backend. Draft only -- routing records the approval, nothing is sent.
export default function MaternalOutreachPreview() {
  return <ActionPackageCard persona="maria" decidedBy="Dr. Maria Delgado-Reyes" Fallback={StaticMaternalOutreachPreview} />;
}

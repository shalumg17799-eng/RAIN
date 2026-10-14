import { motion } from 'framer-motion';
import { Route, Video, Ambulance, HeartPulse } from 'lucide-react';
import ActionPackageCard from '@/clients/rain/components/ActionPackageCard';
import OfflineCacheIndicator from '@/components/chat/OfflineCacheIndicator';

const RAIN_NAVY = '#003366';
const STATIC_ITEMS = [
  { icon: Route, label: 'Consolidated transport schedule', detail: 'Merges prenatal + chronic corridors, resolves 3 double-bookings, shifts 5 to afternoon' },
  { icon: Video, label: '13 trips converted to telehealth', detail: '7 home visits with join link, 6 scheduled into freed afternoon rooms' },
  { icon: Ambulance, label: 'EMS crew reassignment', detail: 'Restores a unit to the northern ZIP codes with no current coverage' },
  { icon: HeartPulse, label: 'Daily risk panel', detail: '16 elevated-risk patients awaiting transport, ranked for field teams' },
];

// The original static card, kept as the offline fallback.
export function StaticOperationsPlanPreview() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Today's Operations Plan</p>
        <span className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded" style={{ backgroundColor: RAIN_NAVY }}>Field-ready</span>
      </div>
      <div className="space-y-2 mb-3">
        {STATIC_ITEMS.map((it) => {
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
      <OfflineCacheIndicator />
    </motion.div>
  );
}

// Live: the 4 items, built from real data, with a working Route / Hold gate
// (shared with Sarah's, Maria's, and David's action packages). Corrects the
// static card's unsupported double-booking claim, its wrong 13-trip
// telehealth figure (real proxy is 3), and its fabricated "16 elevated-risk
// patients" risk panel (real finding: 9 unscheduled, 0 elevated-risk) --
// see james_operations_plan.py.
export default function OperationsPlanPreview() {
  return <ActionPackageCard persona="james" decidedBy="James Tomley" Fallback={StaticOperationsPlanPreview} />;
}

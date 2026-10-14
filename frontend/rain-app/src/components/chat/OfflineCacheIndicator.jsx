import { WifiOff } from 'lucide-react';

/**
 * Offline-cache indicator for the operations mobile app (James Tomley persona).
 * Signals that a plan/response is available offline in the field, for the
 * frontier service area's connectivity dead zones.
 */
export default function OfflineCacheIndicator({ label = 'Cached offline · available in the field' }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200">
      <WifiOff className="w-3.5 h-3.5 text-amber-600" />
      <span className="text-[10px] font-semibold text-amber-700">{label}</span>
    </div>
  );
}

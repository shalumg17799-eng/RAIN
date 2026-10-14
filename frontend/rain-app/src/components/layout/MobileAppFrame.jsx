import { Wifi, Battery, Signal, WifiOff } from 'lucide-react';

/**
 * Phone-frame wrapper used to present a persona's experience as a mobile app
 * (James Tomley's rural operations app). Renders the device chrome — status bar,
 * an app header with an offline-cache indicator, and a home indicator — around a
 * phone-width column that hosts the same responsive React UI used on desktop.
 *
 * The column caps at a phone width (≤390px) and fills the screen below it, so at
 * a mobile viewport it renders as a full-bleed app (and the inner UI uses its
 * mobile layout); on a wide screen it presents as a centered phone for demos.
 */
export default function MobileAppFrame({ children, offline = true, appLabel = 'RAIN Operations' }) {
  return (
    <div className="w-full h-full flex justify-center bg-gray-100">
      <div className="w-full max-w-[390px] h-full flex flex-col bg-gray-50 border-x border-gray-300 shadow-xl">
        {/* Status bar */}
        <div className="flex-shrink-0 h-8 bg-gray-900 text-white flex items-center justify-between px-5 text-[11px] font-medium">
          <span>9:41</span>
          <div className="flex items-center gap-1.5">
            {offline ? <WifiOff className="w-3.5 h-3.5 text-amber-400" /> : <Wifi className="w-3.5 h-3.5" />}
            <Signal className="w-3.5 h-3.5" />
            <Battery className="w-4 h-4" />
          </div>
        </div>

        {/* App header */}
        <div className="flex-shrink-0 bg-[#003366] text-white px-4 py-2.5 flex items-center justify-between">
          <span className="text-[13px] font-bold tracking-tight">{appLabel}</span>
          {offline && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-400/20 border border-amber-300/40">
              <WifiOff className="w-3 h-3 text-amber-300" />
              <span className="text-[9px] font-semibold text-amber-200">Offline · cached</span>
            </span>
          )}
        </div>

        {/* Screen — hosts the responsive app UI, which scrolls internally */}
        <div className="flex-1 min-h-0 flex flex-col">
          {children}
        </div>

        {/* Home indicator */}
        <div className="flex-shrink-0 bg-white h-5 flex items-center justify-center border-t border-gray-100">
          <div className="w-32 h-1 rounded-full bg-gray-300" />
        </div>
      </div>
    </div>
  );
}

import { Wifi, Battery, Signal } from 'lucide-react';

/**
 * Generic phone-frame wrapper for screenshot-ready mobile views (the patient-facing
 * RAIN app). Renders a status bar and a home indicator around a phone-width column
 * that fills the screen below ~390px and centers as a device on wider screens.
 * The app header/content is supplied as children.
 */
export default function MobilePhoneFrame({ children }) {
  return (
    <div className="w-full min-h-screen flex justify-center bg-gray-100">
      <div className="w-full max-w-[390px] min-h-screen flex flex-col bg-white border-x border-gray-200 shadow-xl">
        {/* Status bar */}
        <div className="flex-shrink-0 h-8 bg-white text-gray-800 flex items-center justify-between px-5 text-[11px] font-semibold">
          <span>9:41</span>
          <div className="flex items-center gap-1.5">
            <Signal className="w-3.5 h-3.5" />
            <Wifi className="w-3.5 h-3.5" />
            <Battery className="w-4 h-4" />
          </div>
        </div>

        {/* App content */}
        <div className="flex-1 min-h-0 flex flex-col">
          {children}
        </div>

        {/* Home indicator */}
        <div className="flex-shrink-0 h-5 flex items-center justify-center">
          <div className="w-32 h-1 rounded-full bg-gray-300" />
        </div>
      </div>
    </div>
  );
}

import { motion } from 'framer-motion';

const RAIN_NAVY = '#003366';
// Simplified Nevada silhouette (stylized — not survey-accurate).
const NV_PATH = 'M14 10 L150 10 L150 196 L150 196 L86 250 L14 92 Z';

// Patient ZIP clusters around the closed Battle Mountain unit (north-central).
const clusters = [
  { x: 78, y: 70, n: 9 },
  { x: 92, y: 62, n: 7 },
  { x: 66, y: 84, n: 6 },
];

export default function NevadaAccessMap() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Maternal Access — Distance to Delivery</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">115 mi to nearest OB</span>
      </div>

      <div className="flex gap-4">
        <svg viewBox="0 0 164 262" className="w-[150px] flex-shrink-0">
          <path d={NV_PATH} fill="#EEF2F7" stroke="#CBD5E1" strokeWidth="1.5" strokeLinejoin="round" />
          {/* Humboldt + Pershing highlight (north-central) */}
          <path d="M52 40 L120 40 L122 96 L58 100 Z" fill={RAIN_NAVY} fillOpacity="0.10" stroke={RAIN_NAVY} strokeOpacity="0.4" strokeWidth="1" strokeDasharray="3 2" />
          <text x="86" y="34" textAnchor="middle" className="fill-gray-400" style={{ fontSize: 7, fontWeight: 700 }}>HUMBOLDT · PERSHING</text>

          {/* Distance corridor: closed unit → nearest delivering hospital */}
          <line x1="80" y1="58" x2="28" y2="120" stroke="#DC2626" strokeWidth="1.6" strokeDasharray="4 3" />

          {/* Patient ZIP clusters */}
          {clusters.map((c, i) => (
            <g key={i}>
              <circle cx={c.x} cy={c.y} r={6 + c.n * 0.5} fill={RAIN_NAVY} fillOpacity="0.16" />
              <circle cx={c.x} cy={c.y} r="3" fill={RAIN_NAVY} />
              <text x={c.x} y={c.y - 9} textAnchor="middle" className="fill-gray-500" style={{ fontSize: 7, fontWeight: 700 }}>{c.n}</text>
            </g>
          ))}

          {/* Closed Battle Mountain unit */}
          <g>
            <rect x="76" y="54" width="9" height="9" rx="1.5" fill="#fff" stroke="#DC2626" strokeWidth="1.5" />
            <line x1="78" y1="56" x2="83" y2="61" stroke="#DC2626" strokeWidth="1.4" />
            <line x1="83" y1="56" x2="78" y2="61" stroke="#DC2626" strokeWidth="1.4" />
          </g>
          {/* Nearest delivering hospital */}
          <g>
            <rect x="23" y="115" width="10" height="10" rx="1.5" fill="#059669" />
            <line x1="28" y1="117.5" x2="28" y2="122.5" stroke="#fff" strokeWidth="1.4" />
            <line x1="25.5" y1="120" x2="30.5" y2="120" stroke="#fff" strokeWidth="1.4" />
          </g>
        </svg>

        <div className="flex-1 space-y-2 text-[11px]">
          <div className="flex items-start gap-2">
            <span className="w-3 h-3 mt-0.5 rounded-sm border border-red-500 flex items-center justify-center flex-shrink-0"><span className="text-[8px] text-red-500 font-bold leading-none">✕</span></span>
            <p className="text-gray-600"><span className="font-semibold text-gray-800">Battle Mountain CAH</span> — labor & delivery suspended March 1, 2026.</p>
          </div>
          <div className="flex items-start gap-2">
            <span className="w-3 h-3 mt-0.5 rounded-sm bg-emerald-600 flex-shrink-0" />
            <p className="text-gray-600"><span className="font-semibold text-gray-800">Nearest delivering hospital</span> — now 115 miles away.</p>
          </div>
          <div className="flex items-start gap-2">
            <span className="w-3 h-3 mt-0.5 rounded-full flex-shrink-0" style={{ backgroundColor: RAIN_NAVY }} />
            <p className="text-gray-600"><span className="font-semibold text-gray-800">22 patient ZIP clusters</span> beyond 100 mi; 3 in broadband-dead zones.</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-100 p-2 mt-1">
            <p className="text-[9px] uppercase tracking-wider text-gray-400 font-semibold">Childbearing-age women &gt;60 mi from OB</p>
            <p className="text-[13px] font-bold" style={{ color: RAIN_NAVY }}>58% <span className="text-[10px] font-normal text-gray-400">was 31% before closure</span></p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

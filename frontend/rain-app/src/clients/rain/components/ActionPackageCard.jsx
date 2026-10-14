import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ClipboardList, FileText, Pill, Bus, Video, Home, Users, Route, Ambulance, HeartPulse, ChevronDown, ChevronUp } from 'lucide-react';

const RAIN_NAVY = '#003366';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

// The backend sends an icon id; a component reference can't travel over JSON.
const ICONS = {
  list: ClipboardList, file: FileText, pill: Pill, bus: Bus, video: Video, home: Home,
  users: Users, route: Route, ambulance: Ambulance, heart: HeartPulse,
};

const STATE_BADGE = {
  routed: 'Routed (simulated)',
  partially_routed: 'Partly routed (simulated)',
  held: 'Held for review',
};

async function post(url, body) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'That request was not valid.');
  return data;
}

/**
 * A live "action package" card. The package (what to do, for whom, with the
 * evidence) comes from the backend, built from the real data. DRAFT ONLY:
 * "Route" records the approval and an audit entry; nothing is sent anywhere.
 *
 * props:
 *   persona     backend persona id, e.g. 'maria'
 *   decidedBy   who is approving (recorded in the audit log)
 *   Fallback    component shown when the backend can't be reached (the original static card)
 */
export default function ActionPackageCard({ persona, decidedBy, Fallback = null, initialPackage = null }) {
  const url = `${API_BASE}/ultra/rain/${persona}/actionPackage`;
  const [pkg, setPkg] = useState(initialPackage);
  const [phase, setPhase] = useState(initialPackage ? 'live' : 'loading'); // loading | live | offline
  const [showPatients, setShowPatients] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (initialPackage) return;
    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('unavailable'))))
      .then((p) => { setPkg(p); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, [url, initialPackage]);

  if (phase === 'offline') return Fallback ? <Fallback /> : null;
  if (phase === 'loading' || !pkg) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Preparing the package from the data…</div>;
  }

  const { display, summary: s } = pkg;
  const readyCount = pkg.actions.filter((a) => a.status === 'ready').length;
  const allRouted = pkg.state === 'routed';
  const waiting = pkg.needs_input || [];
  const badge = STATE_BADGE[pkg.state] || `Draft · ${s.ready_total} of ${s.actions_total} ready`;
  const flagsFor = (pid) => pkg.actions.filter((a) => a.patient_id === pid && a.flags && a.flags.length).flatMap((a) => a.flags);

  const decide = async (decision) => {
    setBusy(true); setError(null);
    try {
      const out = await post(`${url}/decision`, { decision, decided_by: decidedBy, inputs: {} });
      setResult(out); setPkg(out.package);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">{display.title}</p>
        <span className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded" style={{ backgroundColor: RAIN_NAVY }}>{badge}</span>
      </div>

      <div className="space-y-2">
        {display.rows.map((r) => {
          const Icon = ICONS[r.icon] || ClipboardList;
          return (
            <div key={r.label} className="bg-white rounded-lg border border-gray-100 p-2.5 flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${RAIN_NAVY}14` }}>
                <Icon className="w-3.5 h-3.5" style={{ color: RAIN_NAVY }} />
              </div>
              <div className="flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-[11px] font-semibold text-gray-800">{r.label}</p>
                  <span className="text-[9px] text-gray-500 whitespace-nowrap">{r.status}</span>
                </div>
                <p className="text-[9.5px] text-gray-500 leading-tight mt-0.5">{r.detail}</p>
              </div>
            </div>
          );
        })}
      </div>

      {display.tiles && display.tiles.length > 0 && (
        <div className="grid grid-cols-3 gap-2 mt-3">
          {display.tiles.map((t) => (
            <div key={t.label} className="bg-white rounded-lg p-2 border border-gray-100 text-center">
              <p className="text-[15px] font-bold" style={{ color: RAIN_NAVY }}>{t.n}</p>
              <p className="text-[9px] text-gray-500 leading-tight mt-0.5">{t.label}</p>
            </div>
          ))}
        </div>
      )}

      {pkg.patients && pkg.patients.length > 0 && (
      <button type="button" onClick={() => setShowPatients((v) => !v)}
        className="mt-2 flex items-center gap-1 text-[10px] font-semibold" style={{ color: RAIN_NAVY }}>
        {showPatients ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {showPatients ? 'Hide' : 'Show'} each patient's summary and evidence
      </button>
      )}
      {showPatients && pkg.patients && pkg.patients.length > 0 && (
        <div className="mt-1.5 space-y-2">
          {pkg.patients.map((p) => (
            <div key={p.patient_id} className="bg-white rounded-lg border border-gray-100 p-2.5">
              <p className="text-[10.5px] font-semibold text-gray-800">
                #{p.rank} {p.patient_id} · {p.risk_score} of {p.risk_factors_total} risk factors · {p.recommended_intervention}
              </p>
              <p className="text-[9.5px] text-gray-600 leading-snug mt-0.5">{p.care_summary}</p>
              {flagsFor(p.patient_id).map((f) => (
                <p key={f.code + p.patient_id} className="text-[9.5px] text-amber-800 bg-amber-50 border border-amber-100 rounded px-1.5 py-1 mt-1 leading-snug">{f.message}</p>
              ))}
              <ul className="mt-1 space-y-0.5">
                {p.evidence.map((e) => (
                  <li key={`${p.patient_id}-${e.table}`} className="text-[9px] text-gray-500 leading-tight">
                    <span className="font-semibold text-gray-600">{e.system}</span> — {e.fact}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {pkg.notes.length > 0 && (
        <>
          <button type="button" onClick={() => setShowNotes((v) => !v)}
            className="mt-2 flex items-center gap-1 text-[10px] font-semibold text-amber-700">
            {showNotes ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            What the data shows before you route ({pkg.notes.length})
          </button>
          {showNotes && (
            <ul className="mt-1 bg-amber-50 border border-amber-100 rounded-lg p-2 space-y-1">
              {pkg.notes.map((n) => <li key={n} className="text-[9.5px] text-amber-900 leading-snug">{n}</li>)}
            </ul>
          )}
        </>
      )}

      {waiting.length > 0 && !allRouted && (
        <p className="mt-2 text-[9.5px] text-gray-500">
          Waiting on input, and held if you route: {waiting.map((w) => `${w.label} (${w.count})`).join(', ')}.
        </p>
      )}

      {error && <p role="alert" className="mt-2 text-[10px] text-red-600">{error}</p>}

      {!allRouted && (
        <div className="mt-3 flex gap-2">
          <button type="button" onClick={() => decide('route')} disabled={busy || readyCount === 0}
            className="flex-1 text-[11px] font-semibold text-white px-2.5 py-1.5 rounded-lg disabled:opacity-40" style={{ backgroundColor: RAIN_NAVY }}>
            Route ready actions ({readyCount})
          </button>
          <button type="button" onClick={() => decide('hold')} disabled={busy}
            className="flex-1 text-[11px] font-semibold px-2.5 py-1.5 rounded-lg border border-gray-300 text-gray-700 bg-white disabled:opacity-50">
            Hold for review
          </button>
        </div>
      )}

      {result && (
        <div role="status" className="mt-2 bg-white rounded-lg border border-gray-100 p-2.5">
          <p className="text-[10.5px] font-semibold text-gray-800">{result.decision === 'route' ? 'Recorded' : 'Held'}</p>
          <p className="text-[9.5px] text-gray-600 leading-snug mt-0.5">{result.message}</p>
        </div>
      )}

      <p className="text-[10px] text-gray-400 mt-2">{display.footer}</p>
    </motion.div>
  );
}

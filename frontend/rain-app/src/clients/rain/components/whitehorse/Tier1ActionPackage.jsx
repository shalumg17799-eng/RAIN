import { useEffect, useState } from 'react';
import { logBackend, logFallback } from '../../../../utils/dataLog';
import { motion } from 'framer-motion';
import { ClipboardList, Pill, Bus, Video, Home, ChevronDown, ChevronUp } from 'lucide-react';

const RAIN_NAVY = '#003366';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const PACKAGE_URL = `${API_BASE}/ultra/rain/sarah/actionPackage`;
const COORDINATOR = 'Sarah Whitehorse, RN';

// The original static card. Shown when the backend can't be reached, so the
// app keeps working offline exactly as before (same pattern as every other
// wired component).
const STATIC_ACTIONS = [
  { icon: ClipboardList, label: 'Pre-populated care summary', detail: 'RPM trend, medication gap, last contact, SDOH barriers — per patient' },
  { icon: Pill, label: 'Pharmacy outreach (5)', detail: 'Lapsed-medication refill routed to pharmacy of record' },
  { icon: Bus, label: 'NEMT transport request (4)', detail: 'For the 4 Tier 1 patients with a transportation barrier' },
  { icon: Video, label: 'Telehealth + re-panel (5)', detail: 'Visit < 48h with an available provider; continuity restored' },
  { icon: Home, label: 'CHW home visit (1)', detail: 'Silent patient — no contact in 24 days' },
];

export function StaticTier1Card() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Tier 1 Action Package — 5 Highest-Risk Patients</p>
        <span className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded" style={{ backgroundColor: RAIN_NAVY }}>Draft · ready to route</span>
      </div>
      <div className="space-y-2">
        {STATIC_ACTIONS.map((a) => {
          const Icon = a.icon;
          return (
            <div key={a.label} className="bg-white rounded-lg border border-gray-100 p-2.5 flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${RAIN_NAVY}14` }}>
                <Icon className="w-3.5 h-3.5" style={{ color: RAIN_NAVY }} />
              </div>
              <div className="flex-1">
                <p className="text-[11px] font-semibold text-gray-800">{a.label}</p>
                <p className="text-[9.5px] text-gray-500 leading-tight mt-0.5">{a.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-gray-400 mt-2">Each action carries its cross-system evidence chain so the coordinator never toggles between systems.</p>
    </motion.div>
  );
}

const emptyInputs = { pharmacy_of_record: {}, repanel_to: {}, chw_patient_id: '' };

// Only send what the coordinator actually filled in.
function cleanInputs(i) {
  const filled = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => String(v).trim() !== ''));
  const out = {};
  const ph = filled(i.pharmacy_of_record);
  const rp = filled(i.repanel_to);
  if (Object.keys(ph).length) out.pharmacy_of_record = ph;
  if (Object.keys(rp).length) out.repanel_to = rp;
  if (i.chw_patient_id.trim()) out.chw_patient_id = i.chw_patient_id.trim();
  return out;
}

async function post(path, body) {
  const res = await fetch(`${PACKAGE_URL}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'That request was not valid.');
  return data;
}

const STATE_BADGE = {
  routed: 'Routed (simulated)',
  partially_routed: 'Partly routed (simulated)',
  held: 'Held for review',
};

const FIELD_LABEL = { pharmacy_of_record: 'a pharmacy of record', repanel_to: 'a provider choice', chw_patient_id: 'a patient to visit' };

export default function Tier1ActionPackage({ initialPackage = null }) {
  const [pkg, setPkg] = useState(initialPackage);           // what the numbers and badge show (inputs applied)
  const [formPkg, setFormPkg] = useState(initialPackage);   // what the data is still missing (decides the form's fields)
  const [phase, setPhase] = useState(initialPackage ? 'live' : 'loading'); // loading | live | offline
  const [inputs, setInputs] = useState(emptyInputs);
  const [showPatients, setShowPatients] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (initialPackage) return;
    fetch(PACKAGE_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('unavailable'))))
      .then((p) => { logBackend('Sarah Tier 1 action package from GET /ultra/rain/sarah/actionPackage'); setPkg(p); setFormPkg(p); setPhase('live'); })
      .catch((e) => { logFallback('Sarah Tier 1 action package', 'STATIC_ACTIONS in Tier1ActionPackage.jsx', e.message); setPhase('offline'); });
  }, [initialPackage]);

  if (phase === 'offline') return <StaticTier1Card />;
  if (phase === 'loading' || !pkg) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Preparing the Tier 1 package from the data…</div>;
  }

  const s = pkg.summary;
  const readyCount = pkg.actions.filter((a) => a.status === 'ready').length;
  const allRouted = pkg.state === 'routed';
  const entered = Object.keys(cleanInputs(inputs)).length > 0;
  const needFor = (type, field) => formPkg.actions.filter((a) => a.type === type && a.needs.some((n) => n.field === field));
  const pharmacyNeeds = needFor('pharmacy_outreach', 'pharmacy_of_record');
  const repanelNeeds = needFor('visit_and_repanel', 'repanel_to');
  const chwNeeds = needFor('chw_home_visit', 'chw_patient_id');
  const chwAction = pkg.actions.find((a) => a.type === 'chw_home_visit');
  const showForm = !allRouted && (pharmacyNeeds.length || repanelNeeds.length || chwNeeds.length);

  const setPharmacy = (pid, v) => setInputs((i) => ({ ...i, pharmacy_of_record: { ...i.pharmacy_of_record, [pid]: v } }));
  const setRepanel = (pid, v) => setInputs((i) => ({ ...i, repanel_to: { ...i.repanel_to, [pid]: v } }));

  const run = async (fn) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const apply = () => run(async () => { setPkg(await post('/preview', { inputs: cleanInputs(inputs) })); setResult(null); });
  const decide = (decision) => run(async () => {
    const sent = cleanInputs(inputs);
    const out = await post('/decision', { decision, decided_by: COORDINATOR, inputs: sent });
    setResult(out);
    setFormPkg(out.package);
    if (decision === 'hold' && Object.keys(sent).length) {
      // Nothing was executed, so keep what the coordinator typed and keep showing it applied.
      setPkg(await post('/preview', { inputs: sent }));
    } else {
      setPkg(out.package);
      if (decision === 'route') setInputs(emptyInputs);
    }
  });

  const typeStatus = (t) => {
    const x = s[t];
    if (x.total && x.routed === x.total) return 'routed';
    return `${x.ready} of ${x.total} ready`;
  };
  const rows = [
    { icon: ClipboardList, label: 'Pre-populated care summary',
      detail: `${s.patients} patients — RPM trend, medication gap, last contact, SDOH barriers`, status: 'prepared' },
    { icon: Pill, label: `Pharmacy outreach (${s.pharmacy_outreach.total})`,
      detail: s.pharmacy_outreach.needs_input ? `Lapsed-medication refill — ${s.pharmacy_outreach.needs_input} waiting on a pharmacy of record (not in the data)` : 'Lapsed-medication refill to the pharmacy of record',
      status: typeStatus('pharmacy_outreach') },
    { icon: Bus, label: `NEMT transport request (${s.nemt_request.total})`,
      detail: `For the ${s.nemt_request.total} patients with a transportation barrier`, status: typeStatus('nemt_request') },
    { icon: Video, label: `Visit + re-panel (${s.visit_and_repanel.total})`,
      detail: `${s.visit_and_repanel.telehealth} by telehealth · ${s.visit_and_repanel.in_person_via_nemt} in person via NEMT (no broadband) · due within 48 h`,
      status: typeStatus('visit_and_repanel') },
    { icon: Home, label: `CHW home visit (${s.chw_home_visit.total})`,
      detail: chwAction && chwAction.patient_id ? `Patient ${chwAction.patient_id}` : 'The silent patient is not identified in the data — choose a patient to dispatch',
      status: typeStatus('chw_home_visit') },
  ];

  const badge = STATE_BADGE[pkg.state] || `Draft · ${s.ready_total} of ${s.actions_total} ready`;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Tier 1 Action Package — {s.patients} Highest-Risk Patients</p>
        <span className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded" style={{ backgroundColor: RAIN_NAVY }}>{badge}</span>
      </div>

      <div className="space-y-2">
        {rows.map((a) => {
          const Icon = a.icon;
          return (
            <div key={a.label} className="bg-white rounded-lg border border-gray-100 p-2.5 flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${RAIN_NAVY}14` }}>
                <Icon className="w-3.5 h-3.5" style={{ color: RAIN_NAVY }} />
              </div>
              <div className="flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-[11px] font-semibold text-gray-800">{a.label}</p>
                  <span className="text-[9px] text-gray-500 whitespace-nowrap">{a.status}</span>
                </div>
                <p className="text-[9.5px] text-gray-500 leading-tight mt-0.5">{a.detail}</p>
              </div>
            </div>
          );
        })}
      </div>

      <button type="button" onClick={() => setShowPatients((v) => !v)}
        className="mt-2 flex items-center gap-1 text-[10px] font-semibold" style={{ color: RAIN_NAVY }}>
        {showPatients ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {showPatients ? 'Hide' : 'Show'} each patient's summary and evidence
      </button>
      {showPatients && (
        <div className="mt-1.5 space-y-2">
          {pkg.patients.map((p) => (
            <div key={p.patient_id} className="bg-white rounded-lg border border-gray-100 p-2.5">
              <p className="text-[10.5px] font-semibold text-gray-800">{p.patient_id} · {p.condition} · {p.risk_score} of {p.risk_factors_total} risk factors</p>
              <p className="text-[9.5px] text-gray-600 leading-snug mt-0.5">{p.care_summary}</p>
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

      {showForm ? (
        <div className="mt-3 bg-white rounded-lg border border-gray-100 p-2.5">
          <p className="text-[10.5px] font-semibold text-gray-800">Needs your input</p>
          <p className="text-[9.5px] text-gray-500 mt-0.5">Only what the data cannot supply. Routing sends the ready actions and holds the rest.</p>

          {pharmacyNeeds.length > 0 && (
            <div className="mt-2">
              <p className="text-[9.5px] font-semibold text-gray-600">Pharmacy of record</p>
              <div className="grid grid-cols-1 gap-1 mt-1">
                {pharmacyNeeds.map((a) => (
                  <label key={a.patient_id} className="flex items-center gap-2 text-[9.5px] text-gray-600">
                    <span className="w-16 flex-shrink-0">{a.patient_id}</span>
                    <input aria-label={`Pharmacy of record for ${a.patient_id}`} type="text" maxLength={100} placeholder="Pharmacy name"
                      value={inputs.pharmacy_of_record[a.patient_id] || ''} onChange={(e) => setPharmacy(a.patient_id, e.target.value)}
                      className="flex-1 text-[10px] border border-gray-200 rounded px-1.5 py-1" />
                  </label>
                ))}
              </div>
            </div>
          )}

          {repanelNeeds.length > 0 && (
            <div className="mt-2">
              <p className="text-[9.5px] font-semibold text-gray-600">Provider for re-panel</p>
              <div className="grid grid-cols-1 gap-1 mt-1">
                {repanelNeeds.map((a) => {
                  const need = a.needs.find((n) => n.field === 'repanel_to');
                  return (
                    <label key={a.patient_id} className="text-[9.5px] text-gray-600">
                      <span className="flex items-center gap-2">
                        <span className="w-16 flex-shrink-0">{a.patient_id}</span>
                        <select aria-label={`Provider for ${a.patient_id}`} value={inputs.repanel_to[a.patient_id] || ''} onChange={(e) => setRepanel(a.patient_id, e.target.value)}
                          className="flex-1 text-[10px] border border-gray-200 rounded px-1.5 py-1 bg-white">
                          <option value="">Choose a provider…</option>
                          {need.options.map((o) => <option key={o.provider_id} value={o.provider_id}>{o.label}</option>)}
                        </select>
                      </span>
                      <span className="block text-[9px] text-gray-400 ml-[4.5rem]">{need.why}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {chwNeeds.length > 0 && (
            <div className="mt-2">
              <p className="text-[9.5px] font-semibold text-gray-600">CHW home visit</p>
              <label className="flex items-center gap-2 text-[9.5px] text-gray-600 mt-1">
                <span className="w-16 flex-shrink-0">Patient</span>
                <input aria-label="Patient to visit" type="text" maxLength={8} placeholder="PT-00000" value={inputs.chw_patient_id}
                  onChange={(e) => setInputs((i) => ({ ...i, chw_patient_id: e.target.value }))}
                  className="flex-1 text-[10px] border border-gray-200 rounded px-1.5 py-1" />
              </label>
              <p className="text-[9px] text-gray-400 mt-0.5">{chwNeeds[0].needs[0].why}</p>
            </div>
          )}

          {entered && (
            <button type="button" onClick={apply} disabled={busy}
              className="mt-2 text-[10px] font-semibold px-2 py-1 rounded border border-gray-300 text-gray-700 disabled:opacity-50">
              Apply inputs
            </button>
          )}
        </div>
      ) : null}

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
          {result.held.length > 0 && result.decision === 'route' && (
            <ul className="mt-1 space-y-0.5">
              {Object.entries(result.held.reduce((acc, h) => {
                const k = h.needs[0]; acc[k] = (acc[k] || 0) + 1; return acc;
              }, {})).map(([field, n]) => (
                <li key={field} className="text-[9px] text-gray-500">{n} waiting on {FIELD_LABEL[field] || field}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="text-[10px] text-gray-400 mt-2">
        Draft only — routing records your approval; nothing is sent to any pharmacy, dispatcher, clinic or community health worker.
        Each action carries its cross-system evidence chain so the coordinator never toggles between systems.
      </p>
    </motion.div>
  );
}

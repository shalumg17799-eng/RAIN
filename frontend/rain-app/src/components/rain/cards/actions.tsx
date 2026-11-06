/**
 * Automated Action visuals: the launch card that opens a workbench, the
 * hand-off cards with Approve, the brief and packet previews, banners,
 * sign-off and export. Nothing sends, books or publishes without a click.
 */
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle2, Download, ExternalLink, FileText, PanelRight, PenLine, Printer, Send, ShieldCheck } from 'lucide-react';
import { HANDOFFS, LAUNCHES } from '@/data/rain/contracts';
import { WORKBENCHES, launchHref } from '@/data/rain/_shared/contract';
import { BP, CODING, COHORT, CONTRACT, COUNTIES, FRESHNESS, GAP, MODEL, OPTIONS, ORG, STATE, num, suppress, usdM } from '@/data/rain/_shared/constants';
import { Button, Pill, RainCard } from '../shell/rainKit';
import { approve, editBrief, isReleased, sendNote, sign, useRainState } from '../shell/store';
import { usePanel } from '../shell/panel';
import { downloadCountyCsv } from './exportCsv';

/** "Opening Quality Gate and Campaigns, filtered to the 412 near-control members" with an Open button. */
export function LaunchCard({ step }: { step: string }) {
  const launch = LAUNCHES[step];
  const navigate = useNavigate();
  const location = useLocation();
  const inPane = usePanel();
  if (!launch) return null;
  const href = launchHref(launch);
  const here = location.pathname === WORKBENCHES[launch.workbench].path;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-brand/25 bg-brand/[0.05] px-4 py-3">
      <div className="flex min-w-0 items-start gap-2.5">
        <PanelRight className="mt-0.5 h-5 w-5 flex-shrink-0 text-brand" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-text">
            {here ? 'Open beside this conversation: ' : 'Opening '}
            {launch.label}, {launch.detail}
          </p>
          <p className="text-[11.5px] text-text-muted">{inPane || here ? 'Select anything on the screen and ask me about it here.' : 'Keep asking questions while you work; this conversation comes with you.'}</p>
        </div>
      </div>
      {!here && (
        <Button variant="primary" onClick={() => navigate(href)}>
          Open <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      )}
    </div>
  );
}

/** Hand-off cards with Approve (Use Case A to B, or to a colleague). */
export function HandoffCards({ ids, points }: { ids: string[]; points?: string[] }) {
  const { approved } = useRainState();
  const list = ids.map((id) => HANDOFFS[id]).filter(Boolean);
  return (
    <RainCard eyebrow="Hand-offs for your approval" title={list.length > 1 ? `${list.length} hand-offs ready` : list[0]?.title} points={points} label={null}>
      <ul className="grid gap-2 @lg:grid-cols-2">
        {list.map((h) => {
          const done = !!approved[h.id];
          return (
            <li key={h.id} className={`flex flex-col justify-between gap-2 rounded-xl border p-3 ${done ? 'border-success/30 bg-success-subtle' : 'border-border bg-surface'}`}>
              <div>
                <p className="text-[13px] font-semibold text-text">{h.title}</p>
                <p className="mt-0.5 text-[12px] text-text-muted">{h.detail}</p>
                <p className="mt-1 text-[11.5px] text-text-subtle">
                  To: {h.to} · lands in {WORKBENCHES[h.workbench].title}
                </p>
              </div>
              {done ? (
                <Pill tone="good">
                  <CheckCircle2 className="h-3 w-3" aria-hidden="true" /> Approved and sent
                </Pill>
              ) : (
                <Button variant="primary" onClick={() => approve(h.id)}>
                  <Send className="h-3.5 w-3.5" aria-hidden="true" /> Approve
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </RainCard>
  );
}

type BriefKind = 'board' | 'note' | 'packet' | 'adt' | 'cms';

const BRIEFS: Record<BriefKind, { eyebrow: string; title: string; sections: Array<{ key: string; heading: string; body: string }> }> = {
  board: {
    eyebrow: 'Board brief · one page',
    title: `Q3 contract checkpoint: ${ORG.plan}`,
    sections: [
      { key: 'checkpoint', heading: 'The checkpoint', body: `$${CONTRACT.actualPmpm} vs $${CONTRACT.expectedPmpm} PMPM (+${CONTRACT.abovePct}%, about $2.9M a year). Gate ${CONTRACT.gateMet} of ${CONTRACT.gateNeeded} needed. ${CONTRACT.daysLeft} days left.` },
      { key: 'gap', heading: 'The gap in four parts', body: GAP.map((g) => `${g.label} $${g.value % 1 ? g.value.toFixed(2) : g.value}`).join(' · ') + '. About half is documentation.' },
      { key: 'moves', heading: 'Three moves, owners and dates', body: `1. Coding recapture, ${CODING.members} members (CMO, this week). 2. BP campaign, about ${BP.needed} more controlled (CMO and care team, by December 31). 3. Top ${COHORT.topRanked} outreach (care team, now).` },
      { key: 'position', heading: '2027 renegotiation position', body: `Gap about ${CODING.gapAfterPct}%, gate ${CONTRACT.gateNeeded} of ${CONTRACT.gateMeasures}, about ${usdM(COHORT.avoidedCost12m)} avoided over 12 months.` },
    ],
  },
  note: {
    eyebrow: 'Draft · provider feedback note',
    title: 'Low back pain imaging at Winnemucca',
    sections: [
      { key: 'what', heading: 'What we see', body: 'Since April, low back pain imaging at Winnemucca is 27% of eligible visits vs 9% network-wide, with no red flags coded.' },
      { key: 'why', heading: 'Why it matters', body: 'Choosing Wisely advises against imaging in the first six weeks without red flags.' },
      { key: 'ask', heading: 'What we suggest', body: 'Add the network order set and red-flag checklist at Winnemucca, and include it in locum onboarding.' },
    ],
  },
  packet: {
    eyebrow: 'Governance packet',
    title: `${MODEL.name} ${MODEL.candidate}: access-adjusted`,
    sections: [
      { key: 'card', heading: 'Updated model card', body: `Ranks rising-risk members for outreach. Release threshold: subgroup gap under ${MODEL.releaseThresholdPct}%. Accuracy holds.` },
      { key: 'subgroup', heading: 'Subgroup results', body: `Frontier gap ${MODEL.frontierGapPct}% to ${MODEL.frontierGapAfterPct}%. ${MODEL.missingFromTop} in, ${MODEL.missingFromTop} out of the top 300; ${MODEL.inBpDenominator} in the BP denominator.` },
      { key: 'changes', heading: 'Feature change log', body: 'Added drive time, broadband availability, missed appointments and shortage-area status. No feature removed.' },
      { key: 'signoff', heading: 'Sign-off', body: 'CIO and CMO. Until both sign, the care team sees a pending-fix banner.' },
    ],
  },
  adt: {
    eyebrow: 'Draft · data request',
    title: 'Route HIE ADT events into the ED signal',
    sections: [
      { key: 'need', heading: 'Need', body: `Claims arrive ${CONTRACT.claimsLagDays} days after service, so new ED visits are invisible for six weeks.` },
      { key: 'ask', heading: 'Request', body: `Subscribe RAIN to HIE ADT events for attributed members; the feed is ${MODEL.adtLag.toLowerCase()} behind.` },
      { key: 'use', heading: 'Use', body: 'Same-day ED alerts on the Worklist; claims still reconcile cost when they arrive.' },
    ],
  },
  cms: {
    eyebrow: 'RHTP progress summary · Outcomes Accelerator',
    title: 'People served, services delivered and outcomes by county',
    sections: [
      { key: 'served', heading: 'People served', body: COUNTIES.map((c) => `${c.name} ${num(c.members)}`).join(' · ') + `. Total ${num(STATE.members)}, de-identified.` },
      { key: 'outcomes', heading: 'Outcome measures', body: COUNTIES.map((c) => `${c.name}: BP control ${c.bpControlPct}%, avoidable ED ${c.edPer1000} per 1,000, heart failure members ${suppress(c.heartFailure)}`).join('. ') + '.' },
      { key: 'options', heading: 'Recommended funding', body: OPTIONS.map((o) => `${o.id}: ${o.name}`).join(' · ') + '. Fund A and C; run B as a no-cost data service.' },
      { key: 'appendix', heading: 'Appendix', body: 'County charts for each measure; every figure tied to its source; cells under 11 suppressed.' },
    ],
  },
};

export function BriefPreview({ kind, editable = false, points }: { kind: BriefKind; editable?: boolean; points?: string[] }) {
  const b = BRIEFS[kind];
  const store = useRainState();
  const [editing, setEditing] = useState(editable);
  const navigate = useNavigate();
  const noteSent = !!store.sentNotes[kind];
  const text = (key: string, body: string) => store.briefEdits[`${kind}.${key}`] ?? body;
  return (
    <RainCard eyebrow={b.eyebrow} title={b.title} points={points} aside={kind === 'packet' && isReleased(store) ? <Pill tone="good">Released</Pill> : undefined}>
      <div className="rounded-xl border border-border-subtle bg-surface-2/40 p-3">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
          <FileText className="h-3.5 w-3.5" aria-hidden="true" /> {editing ? 'Editing' : 'Preview'}
        </div>
        <div className="space-y-2.5">
          {b.sections.map((s) => (
            <div key={s.key}>
              <p className="text-[12.5px] font-bold text-text">{s.heading}</p>
              {editing ? (
                <textarea
                  aria-label={s.heading}
                  value={text(s.key, s.body)}
                  onChange={(e) => editBrief(`${kind}.${s.key}`, e.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[12.5px] leading-relaxed text-text"
                />
              ) : (
                <p className="text-[12.5px] leading-relaxed text-text-muted">{text(s.key, s.body)}</p>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {(kind === 'board' || kind === 'note' || kind === 'adt') && (
          <Button onClick={() => setEditing((e) => !e)}>
            <PenLine className="h-3.5 w-3.5" aria-hidden="true" /> {editing ? 'Done editing' : 'Edit'}
          </Button>
        )}
        {kind === 'note' && (
          <Button variant="primary" disabled={noteSent} onClick={() => sendNote(kind)}>
            <Send className="h-3.5 w-3.5" aria-hidden="true" /> {noteSent ? 'Sent to Winnemucca clinicians' : 'Approve and send'}
          </Button>
        )}
        {kind === 'adt' && (
          <Button variant="primary" disabled={noteSent} onClick={() => sendNote(kind)}>
            <Send className="h-3.5 w-3.5" aria-hidden="true" /> {noteSent ? 'Request sent to the HIE' : 'Approve and send'}
          </Button>
        )}
        {kind === 'packet' && <SignoffButtons />}
        {kind === 'cms' && (
          <>
            <Button onClick={() => navigate('/rhtp-reporting?print=1')}>
              <Printer className="h-3.5 w-3.5" aria-hidden="true" /> Export PDF
            </Button>
            <Button onClick={downloadCountyCsv}>
              <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export CSV
            </Button>
          </>
        )}
      </div>
    </RainCard>
  );
}

function SignoffButtons() {
  const s = useRainState();
  return (
    <>
      <Button variant="primary" disabled={s.signed.cio} onClick={() => sign('cio')}>
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> {s.signed.cio ? 'Signed by CIO' : 'Sign off (CIO)'}
      </Button>
      <Pill tone={s.signed.cmo ? 'good' : 'neutral'}>{s.signed.cmo ? 'Co-signed by CMO' : s.cosignRequested ? 'Co-sign requested from CMO' : 'Awaiting CMO co-sign'}</Pill>
    </>
  );
}

/** The sign-off state on its own. */
export function Signoff({ points }: { points?: string[] }) {
  const s = useRainState();
  const released = isReleased(s);
  return (
    <RainCard eyebrow="Sign-off" title={released ? 'Released to the care team' : 'Release waits on both signatures'} points={points} label={null}>
      <ul className="grid gap-2 @lg:grid-cols-2">
        <li className={`rounded-xl border p-3 ${s.signed.cio ? 'border-success/30 bg-success-subtle' : 'border-border'}`}>
          <p className="text-[13px] font-semibold text-text">Raj Malhotra, CIO</p>
          <p className="text-[12px] text-text-muted">{s.signed.cio ? 'Signed' : 'Not signed'}</p>
        </li>
        <li className={`rounded-xl border p-3 ${s.signed.cmo ? 'border-success/30 bg-success-subtle' : 'border-border'}`}>
          <p className="text-[13px] font-semibold text-text">Dr. Naomi Castellanos, CMO</p>
          <p className="text-[12px] text-text-muted">{s.signed.cmo ? 'Co-signed' : s.cosignRequested ? 'Co-sign requested · in Model Governance' : 'Not yet requested'}</p>
        </li>
      </ul>
      <div className="mt-3 flex flex-wrap gap-2">
        <SignoffButtons />
      </div>
    </RainCard>
  );
}

/** How a banner will look on the care team's screen. */
export function BannerPreview({ kind }: { kind: 'pendingFix' | 'freshness' }) {
  return (
    <RainCard eyebrow="Banner preview" title={kind === 'pendingFix' ? 'As the care team will see it on the Worklist' : 'As every view now shows it'} label={null}>
      {kind === 'pendingFix' ? (
        <div className="rounded-xl border border-warning/40 bg-warning-subtle px-3 py-2 text-[12.5px] text-warning-700">
          Ranking update pending sign-off: {MODEL.missingFromTop} high-need frontier members will join the top 300. Keep working the current list.
        </div>
      ) : (
        <div className="rounded-xl border border-info/30 bg-info-subtle px-3 py-2 text-[12.5px] text-info-700">Data as of: {FRESHNESS}. ED and low-value care figures trail by about six weeks.</div>
      )}
    </RainCard>
  );
}

/** Export from the conversation (state lead). */
export function ExportCard({ format }: { format: 'pdf' | 'csv' }) {
  const navigate = useNavigate();
  return (
    <RainCard eyebrow="Export" title={format === 'pdf' ? 'RHTP progress summary (PDF)' : 'RHTP progress summary (CSV)'} label="Aggregated, de-identified">
      <p className="text-[12.5px] text-text-muted">{format === 'pdf' ? 'Opens the print view in RHTP Reporting; choose Save as PDF.' : 'One row per county; suppressed cells are left blank.'}</p>
      <div className="mt-3">
        {format === 'pdf' ? (
          <Button variant="primary" onClick={() => navigate('/rhtp-reporting?print=1')}>
            <Printer className="h-3.5 w-3.5" aria-hidden="true" /> Open print view
          </Button>
        ) : (
          <Button variant="primary" onClick={downloadCountyCsv}>
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> Download CSV
          </Button>
        )}
      </div>
    </RainCard>
  );
}

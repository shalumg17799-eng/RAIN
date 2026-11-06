/**
 * The Cockpit pane's answers about what is selected in a workbench (spec "Pane
 * follows the workbench"), as catalog components. The selection is taken when
 * the answer first renders and kept with that message, so selecting another
 * row later never rewrites an earlier answer.
 */
import type { ContractSpec } from '@core/contract/spec';
import { spec } from '@core/catalog/bespoke';
import { BP, CONTRACT, COUNTIES, GAP, LINDA, LV_MEASURES, MEASURES, SEGMENTS, SITES, isMet, num, siteById, usdK } from './constants';
import { FEATURES, getCampaignMembers, getSlots } from './records';
import { ALL_SOURCES } from './sources';

export type ContextKind = 'rank' | 'talk' | 'mode' | 'slots' | 'plan' | 'site' | 'gap' | 'segment' | 'measure' | 'lvMeasure' | 'feature' | 'source' | 'county';

const stat = (label: string, value: string, caption?: string, status?: string) => spec('stat', { label, value, ...(caption ? { caption } : {}), ...(status ? { status } : {}) });
const grid = (columns: number, children: ContractSpec[]) => spec('grid', { columns, children });

type Member = ReturnType<typeof getCampaignMembers>[number];

/** Talking points that fit the patient's visit mode and cuff. */
function talk(m: Member) {
  const video = m.mode === 'Telehealth';
  return [
    { es: 'Hola, soy Teresa de Sierra Basin. Llamo por su presión arterial.', en: 'Hi, this is Teresa from Sierra Basin. I am calling about your blood pressure.' },
    video
      ? { es: 'Podemos hacer una cita por video, sin manejar a la clínica.', en: 'We can do a video visit, with no drive to the clinic.' }
      : { es: `Podemos darle una cita en ${m.site}.`, en: `We can book you a visit at ${m.site}.` },
    ...(video && m.cuff === 'Ship first' ? [{ es: 'Le enviamos un monitor de presión a su casa antes de la cita.', en: 'We will mail you a blood pressure monitor before the visit.' }] : []),
    ...(video && m.cuff === 'On file' ? [{ es: 'Tenga a mano su monitor de presión para la cita.', en: 'Have your blood pressure monitor ready for the visit.' }] : []),
    { es: 'Le mandamos un texto para confirmar. Responda C o R.', en: 'We will text you to confirm. Reply C or R.' },
  ];
}

/** Why a telehealth or in-person visit, from this patient's own facts. */
export function modeReason(m: Member) {
  if (m.mode !== 'Telehealth') return `In person recommended: ${m.driveMin}-minute drive to ${m.site}.`;
  return m.id === 'M-40107'
    ? `Telehealth recommended: ${m.driveMin}-minute drive, broadband available, visit type eligible.`
    : `Telehealth recommended: ${m.driveMin}-minute drive and visit type eligible; a phone visit if video is not possible.`;
}

/** The extra 72-hour reminder, and why, from this patient's own facts. */
export function reminderPlan(m: Member) {
  const article = /^(8|11|18)/.test(String(m.driveMin)) ? 'an' : 'a';
  const why = [m.id === 'M-40107' ? `${LINDA.missedVisits} missed visits` : '', m.driveMin > 60 ? `${article} ${m.driveMin}-minute drive` : '', m.monthsSinceVisit >= 6 ? `no visit in ${m.monthsSinceVisit} months` : ''].filter(Boolean);
  return { early: why.length > 0, why, because: why.length > 1 ? `${why.slice(0, -1).join(', ')} and ${why[why.length - 1]}` : (why[0] ?? '') };
}

export function contextSpecs(kind: ContextKind, selectedId: string | undefined, county?: string): ContractSpec[] {
  if (kind === 'rank' || kind === 'talk' || kind === 'mode' || kind === 'slots' || kind === 'plan') {
    const all = getCampaignMembers();
    const m = all.find((x) => x.id === selectedId) ?? all[0];
    if (kind === 'rank')
      return [
        spec('callout', { title: `${m.name}: rank ${m.rank} of ${BP.nearControl}`, body: `${m.reasons.join(', ')}. Ranked by the impactability score: near control, still changeable, and held back mostly by access.`, status: 'info' }),
        grid(2, [stat('Likely to reach control', `${m.likelihood}%`, 'With one recheck'), stat('Visit mode', m.mode, `${m.driveMin}-minute drive`), stat('Cuff', m.cuff === 'Not needed' ? 'Not needed' : m.cuff, m.mode === 'Telehealth' ? 'Home reading counts for CMS165' : 'In-person reading')]),
      ];
    if (kind === 'talk')
      return [
        spec('data_table', {
          caption: `Talking points for ${m.name} (${m.language === 'Spanish' ? 'prefers Spanish' : 'Spanish version'})`,
          columns: [
            { key: 'es', label: 'Español' },
            { key: 'en', label: 'English' },
          ],
          rows: talk(m),
        }),
        spec('callout', { title: 'No clinical advice by phone script', body: 'Clinical questions go to the care team.', status: 'neutral' }),
      ];
    if (kind === 'mode')
      return [
        spec('callout', {
          title: m.mode === 'Telehealth' ? 'Telehealth recommended' : 'In person recommended',
          body: m.mode === 'Telehealth' ? `${modeReason(m)} Home cuff readings count for CMS165.` : modeReason(m),
          status: 'info',
        }),
      ];
    if (kind === 'slots') {
      const slots = getSlots()
        .map((s) => (s.mode === 'In person' ? { ...s, driveMin: m.driveMin } : s.mode === 'Mobile clinic' && m.id !== 'M-40107' ? { ...s, where: `Mobile clinic, ${m.site}` } : s))
        .sort((a, b) => a.driveMin - b.driveMin);
      return [
        spec('data_table', {
          caption: `Other slots for ${m.name}, sorted by drive time`,
          columns: [
            { key: 'mode', label: 'Mode' },
            { key: 'when', label: 'When' },
            { key: 'drive', label: 'Drive', align: 'right' },
          ],
          rows: slots.map((s) => ({ mode: s.mode, when: `${s.day}, ${s.time}`, drive: s.driveMin ? `${s.driveMin} min` : 'None' })),
        }),
      ];
    }
    const plan = reminderPlan(m);
    const video = m.mode === 'Telehealth';
    return [
      spec('data_table', {
        caption: `Reminder plan for ${m.name}: ${m.language} ${m.channel === 'Voice' ? 'voice' : 'SMS'}`,
        columns: [
          { key: 'when', label: 'When' },
          { key: 'what', label: 'What' },
        ],
        rows: [
          ...(plan.early ? [{ when: '72 hours before', what: 'Date, time and clinic only; reply C or R' }] : []),
          { when: '24 hours before', what: video ? 'Confirmation and the video link' : 'Confirmation, date, time and clinic' },
          { when: '3 hours before', what: video ? 'Link resent' : 'Short reminder' },
          { when: 'Quiet hours', what: 'No texts 8 PM to 8 AM' },
        ],
      }),
      spec('callout', {
        title: plan.early ? 'Why three reminders' : 'Two reminders',
        body: `${plan.early ? `Because of ${plan.because}. ` : ''}No reply by 24 hours before the visit creates a call task on Teresa’s worklist.`,
        status: 'info',
      }),
    ];
  }
  if (kind === 'site') {
    const s = siteById(selectedId ?? '') ?? SITES[2];
    return [grid(2, [stat(`${s.name} PMPM`, `$${s.pmpm}`, `Network $${CONTRACT.actualPmpm}`, s.pmpm > CONTRACT.actualPmpm ? 'warning' : 'good'), stat('Members', num(s.members)), stat('Low-value care', usdK(s.lowValue), 'A year'), stat('LBP imaging', `${s.imagingPct}%`, 'Network 9%', s.imagingPct > 9 ? 'critical' : 'good')]), spec('text', { text: s.locum ? 'Covered by rotating locum clinicians.' : 'Stable clinician staffing.' })];
  }
  if (kind === 'gap') {
    const g = GAP.find((x) => x.id === selectedId) ?? GAP[0];
    return [spec('callout', { title: `${g.label}: $${g.value % 1 ? g.value.toFixed(2) : g.value} of the $26 PMPM gap`, body: `${g.note}.`, status: g.id === 'coding' ? 'info' : 'warning' })];
  }
  if (kind === 'segment') {
    const s = SEGMENTS.find((x) => x.id === selectedId) ?? SEGMENTS[1];
    return [grid(2, [stat(s.label, num(s.members), `${s.sharePct}% of members`), stat('Share of spend', `${s.spendPct}%`), stat('Plan', s.action)])];
  }
  if (kind === 'measure') {
    const m = MEASURES.find((x) => x.id === selectedId) ?? MEASURES[2];
    return [grid(2, [stat(`${m.id} now`, `${m.current}%`, m.name, isMet(m) ? 'good' : 'critical'), stat('Target', m.higherIsBetter ? `${m.target}% or higher` : `${m.target}% or lower`), stat('Projected Dec 31', `${m.projected}%`)])];
  }
  if (kind === 'lvMeasure') {
    const m = LV_MEASURES.find((x) => x.id === selectedId) ?? LV_MEASURES[0];
    return [grid(2, [stat('Services', num(m.services), m.name), stat('Annual spend', usdK(m.dollars)), stat('Basis', m.basis)]), spec('text', { text: 'Counted when a service is likely wasteful or wasteful; necessary services are excluded.' })];
  }
  if (kind === 'feature') {
    const f = FEATURES.find((x) => x.id === selectedId) ?? FEATURES[0];
    return [spec('callout', { title: `${f.name} · weight ${Math.round(f.weight * 100)}% · ${f.kind}`, body: f.note, status: f.kind === 'Current' && (f.id === 'cost' || f.id === 'pcVisits') ? 'warning' : 'info' })];
  }
  if (kind === 'source') {
    const s = ALL_SOURCES.find((x) => x.id === selectedId) ?? ALL_SOURCES[19];
    return [grid(2, [stat('Label', s.kind, s.name), stat('Records', num(s.recordCount)), stat('Freshness', s.freshness)]), spec('text', { text: `${s.provides}. Used for: ${s.usedFor}.` })];
  }
  const c = COUNTIES.find((x) => x.id === county) ?? COUNTIES.find((x) => x.id === selectedId) ?? COUNTIES[2];
  return [
    grid(2, [
      stat('Primary care visits', `${c.pcVisitChangePct}%`, 'Since January', c.pcVisitChangePct <= -10 ? 'critical' : 'warning'),
      stat('Avoidable ED', `${c.edPer1000}`, 'Per 1,000', c.edPer1000 >= 330 ? 'critical' : 'neutral'),
      stat('Broadband for video', `${c.broadbandPct}%`, 'Of locations'),
      stat('Shortage area', c.hpsa, 'HRSA HPSA'),
    ]),
  ];
}

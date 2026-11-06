import { useState } from 'react';
import { LOCUMS, LOW_VALUE, LV_MEASURES, SITES, num, usdK } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { RainCard, ResponsiveTable } from '../shell/rainKit';
import { LvMeasures, SiteCompare } from '../cards/insight';
import { AnnotatedTrend } from '../cards/quality';
import { usePaneContext } from './useWorkbench';

/**
 * Low-Value Care (P2, representative): the 14-measure library, spend by
 * measure, site and ordering provider, and the trend with the April
 * annotation. Scores claims as necessary, likely wasteful or wasteful; only
 * the last two count.
 */
export default function LowValueCare({ access, filter }: { access: Access; filter: string | null }) {
  const [measure, setMeasure] = useState<string | null>(null);
  const [site, setSite] = useState<string | null>(filter === 'winnemucca' ? 'winnemucca' : null);
  const m = LV_MEASURES.find((x) => x.id === measure);
  usePaneContext(
    m
      ? { label: m.name, chips: ['Explain this low-value measure'], kind: 'lvMeasure', id: m.id }
      : site
        ? { label: `${SITES.find((s) => s.id === site)?.name}: low-value care`, chips: ['Explain this site', 'Draft a note to this provider'], kind: 'site', id: site }
        : { label: `Low-value care: ${usdK(LOW_VALUE.annual)} a year`, chips: ['Explain this low-value measure'] },
  );
  return (
    <WorkbenchLayout meta={WORKBENCHES.lowValueCare} access={access}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { label: 'Low-value services', value: num(LOW_VALUE.services) },
          { label: 'Annualized spend', value: usdK(LOW_VALUE.annual) },
          { label: 'Measures', value: String(LOW_VALUE.measures) },
          { label: 'Largest item', value: usdK(LOW_VALUE.lbpImaging) },
        ].map((t) => (
          <div key={t.label} className="rounded-xl border border-border bg-surface px-3 py-2">
            <p className="text-[11px] font-semibold text-text-muted">{t.label}</p>
            <p className="text-[18px] font-bold tabular-nums text-text">{t.value}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-4 @4xl:grid-cols-2">
        <LvMeasures selected={measure} onSelect={(id) => { setMeasure(id); }} />
        <div className="space-y-4">
          <SiteCompare metric="lowValue" selected={site} onSelect={(id) => { setSite(id); setMeasure(null); }} />
          <AnnotatedTrend />
        </div>
      </div>
      <RainCard eyebrow="Ordering providers" title="Low back pain imaging since April, Winnemucca">
        <ResponsiveTable
          caption="Ordering providers"
          rows={[...LOCUMS]}
          rowKey={(l) => l.id}
          columns={[
            { key: 'id', label: 'Clinician (de-identified)' },
            { key: 'ratePct', label: 'Imaging rate', align: 'right', render: (l) => `${l.ratePct}%` },
            { key: 'orders', label: 'Orders', align: 'right' },
            { key: 'net', label: 'Network rate', align: 'right', render: () => `${LOW_VALUE.networkRatePct}%` },
          ]}
        />
        <p className="mt-2 text-[12px] text-text-muted">From the NPPES NPI Registry. One rate across three clinicians points to a missing order set.</p>
      </RainCard>
    </WorkbenchLayout>
  );
}

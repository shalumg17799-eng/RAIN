import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { num } from '@/data/rain/_shared/constants';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import type { RainSource, SourceKind } from '@/data/rain/_shared/sources';
import { ALL_SOURCES, ENGINES, PUBLIC_SOURCES, SYNTHETIC_SOURCES } from '@/data/rain/_shared/sources';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { Pill, RainCard, ResponsiveTable, Segmented } from '../shell/rainKit';
import { usePaneContext, useWorkbench } from './useWorkbench';

/**
 * Data Sources (P2): every source with record count, freshness date and a
 * public or synthetic label. The RAIN persona's `pages.dataSources`, so it
 * replaces the shared page at /data-sources and opens in workbench mode.
 */
export default function RainDataSources() {
  const { access } = useWorkbench('dataSources');
  const [kind, setKind] = useState<'all' | SourceKind>('all');
  const [sel, setSel] = useState<string | null>(null);
  const s = ALL_SOURCES.find((x) => x.id === sel);
  usePaneContext(s ? { label: s.name, chips: ['Explain this source', 'How fresh is each data source?'], kind: 'source', id: s.id } : { label: `${PUBLIC_SOURCES.length} public, ${SYNTHETIC_SOURCES.length} synthetic, ${ENGINES.length} RAIN engines`, chips: ['How fresh is each data source?', 'What public data feeds the county view?'] });
  if (!access) return <Navigate to="/ask" replace />;
  const rows = ALL_SOURCES.filter((x) => kind === 'all' || x.kind === kind);
  return (
    <WorkbenchLayout meta={WORKBENCHES.dataSources} access={access} label="Public + synthetic">
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'Public sources', value: PUBLIC_SOURCES.length, tone: 'good' as const },
          { label: 'Synthetic datasets', value: SYNTHETIC_SOURCES.length, tone: 'warning' as const },
          { label: 'RAIN engines', value: ENGINES.length, tone: 'neutral' as const },
        ].map((t) => (
          <div key={t.label} className="rounded-xl border border-border bg-surface px-3 py-2">
            <p className="text-[11px] font-semibold text-text-muted">{t.label}</p>
            <p className="text-[18px] font-bold tabular-nums text-text">{t.value}</p>
          </div>
        ))}
      </div>
      <RainCard
        eyebrow="Data foundation"
        title="Every source, its freshness and its label"
        label="Public + synthetic"
        aside={
          <Segmented<'all' | SourceKind>
            label="Source type"
            value={kind}
            onChange={setKind}
            options={[
              { value: 'all', label: 'All' },
              { value: 'Public', label: 'Public' },
              { value: 'Synthetic', label: 'Synthetic' },
              { value: 'Engine', label: 'Engines' },
            ]}
          />
        }
      >
        <ResponsiveTable<RainSource>
          caption="Data sources"
          rows={rows}
          rowKey={(x) => x.id}
          onRowClick={(x) => setSel(x.id)}
          selectedKey={sel}
          columns={[
            { key: 'name', label: 'Source', render: (x) => <span className="font-semibold">{x.name}</span> },
            { key: 'kind', label: 'Label', render: (x) => <Pill tone={x.kind === 'Public' ? 'good' : x.kind === 'Synthetic' ? 'warning' : 'neutral'}>{x.kind}</Pill> },
            { key: 'records', label: 'Records', align: 'right', render: (x) => num(x.recordCount) },
            { key: 'freshness', label: 'Freshness' },
            { key: 'usedFor', label: 'Used for', wideOnly: true, render: (x) => <span className="text-[12px] text-text-muted">{x.usedFor}</span> },
          ]}
        />
        <p className="mt-2 text-[12px] text-text-muted">
          Record counts are illustrative. Synthetic datasets swap for partner feeds through the same data contract.
        </p>
      </RainCard>
    </WorkbenchLayout>
  );
}


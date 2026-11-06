/**
 * /catalog — the component catalog, drawn from the registry.
 *
 * The page the frontend, backend and leadership review together: every type
 * the AI can draw, rendered live from its example, with its contract (props
 * JSON Schema) and the example payload beside it. It reads the same registry
 * that `npm run catalog` exports, so what is shown here is exactly what the
 * backend builds against. Platform sign-ins only; clients never see it.
 */
import { useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { z } from 'zod';
import { Boxes, Layers3, Puzzle } from 'lucide-react';
import { useSession } from '../context/SessionContext';
import { CATALOG } from '@core/catalog/registry';
import ComponentRenderer from '@core/catalog/ComponentRenderer';
import { CatalogActionsProvider } from '@core/catalog/catalogActions';
import type { CatalogEntry, Tier } from '@core/catalog/types';

const TIER_NAME: Record<Tier, string> = { 1: 'Shell', 2: 'Catalog', 3: 'Compose', 4: 'Bespoke' };
const noop = () => {};

function EntryCard({ entry }: { entry: CatalogEntry }) {
  const schema = useMemo(() => JSON.stringify(z.toJSONSchema(entry.schema, { unrepresentable: 'any', io: 'input' }), null, 2), [entry]);
  const example = useMemo(() => JSON.stringify({ type: entry.type, version: entry.version, props: entry.example }, null, 2), [entry]);
  return (
    <article id={entry.type} className="rounded-2xl border border-border bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border-subtle px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-text">{entry.title}</h2>
          <p className="mt-0.5 font-mono text-[11.5px] text-text-muted">{entry.type} · v{entry.version}</p>
        </div>
        <span className="rounded-full border border-brand/25 bg-brand/[0.05] px-2.5 py-0.5 text-[11px] font-semibold text-brand">
          Tier {entry.tier} · {TIER_NAME[entry.tier]}
        </span>
      </header>
      <div className="px-5 py-4">
        <p className="text-[13px] leading-relaxed text-text-muted">{entry.description}</p>
        <div className="mt-4 rounded-xl border border-dashed border-border bg-surface-2 p-4">
          <ComponentRenderer components={[{ type: entry.type, version: entry.version, props: entry.example as Record<string, unknown> }]} />
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <details className="rounded-lg border border-border">
            <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-text-muted">Example payload</summary>
            <pre className="max-h-80 overflow-auto border-t border-border-subtle px-3 py-2 text-[11px] leading-relaxed text-text">{example}</pre>
          </details>
          <details className="rounded-lg border border-border">
            <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-text-muted">Props schema (JSON Schema)</summary>
            <pre className="max-h-80 overflow-auto border-t border-border-subtle px-3 py-2 text-[11px] leading-relaxed text-text">{schema}</pre>
          </details>
        </div>
      </div>
    </article>
  );
}

export default function CatalogGallery() {
  // SessionContext is untyped JSX; this is the one field the gallery reads.
  const { isPlatformScope } = useSession() as unknown as { isPlatformScope: boolean };
  const [tier, setTier] = useState<Tier | 'all'>('all');
  if (!isPlatformScope) return <Navigate to="/ask" replace />;

  const tiers = [...new Set(CATALOG.map((e) => e.tier))].sort() as Tier[];
  const shown = tier === 'all' ? CATALOG : CATALOG.filter((e) => e.tier === tier);
  const count = (t: Tier) => CATALOG.filter((e) => e.tier === t).length;

  return (
    <CatalogActionsProvider value={{ onChip: noop, onAction: noop }}>
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
          <h1 className="text-xl font-semibold text-text">Component catalog</h1>
          <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-text-muted">
            Every component the AI can draw, with its contract. The backend returns <code className="font-mono text-[12px]">{'{ type, version, props }'}</code> in
            a turn&apos;s <code className="font-mono text-[12px]">components[]</code>; the props must satisfy the schema shown. Exported for the backend as
            <code className="font-mono text-[12px]"> docs/catalog/catalog.json</code>.
          </p>

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
            {[
              { icon: Boxes, label: 'Component types', value: CATALOG.length },
              { icon: Puzzle, label: 'Tier 2 · catalog', value: count(2) },
              { icon: Layers3, label: 'Tier 3 · compose', value: count(3) },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3">
                <Icon className="h-4 w-4 text-brand" aria-hidden="true" />
                <div>
                  <p className="text-xl font-bold tabular-nums text-text">{value}</p>
                  <p className="text-[11px] text-text-muted">{label}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Filter by tier">
            {(['all', ...tiers] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTier(t)}
                aria-pressed={tier === t}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${tier === t ? 'border-brand bg-brand text-brand-fg' : 'border-border bg-surface text-text-muted hover:text-brand'}`}
              >
                {t === 'all' ? 'All' : `Tier ${t} · ${TIER_NAME[t]}`}
              </button>
            ))}
          </div>

          <div className="mt-5 space-y-5">
            {shown.map((e) => <EntryCard key={e.type} entry={e} />)}
          </div>
        </div>
      </div>
    </CatalogActionsProvider>
  );
}

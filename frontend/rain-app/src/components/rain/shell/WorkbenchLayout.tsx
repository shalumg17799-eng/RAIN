import type { ReactNode } from 'react';
import { Eye, PenLine, RefreshCw } from 'lucide-react';
import { FRESHNESS } from '@/data/rain/_shared/constants';
import type { Access, WorkbenchMeta } from '@/data/rain/_shared/contract';
import CockpitPane from './CockpitPane';
import { DataLabel, Pill } from './rainKit';
import { useRainState } from './store';

/**
 * Workbench mode (spec): the workbench takes centre stage and the Cockpit pane
 * docks on the right; the left navigation stays visible (it is the app
 * shell's). One layout for all ten workbenches.
 */
export default function WorkbenchLayout({
  meta,
  access,
  label = 'Synthetic',
  insights = true,
  actions,
  children,
}: {
  meta: WorkbenchMeta;
  access: Access;
  label?: 'Synthetic' | 'Public + synthetic' | 'Aggregated, de-identified' | 'Public';
  /** Use Case A workbenches carry the data freshness line. */
  insights?: boolean;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { freshnessBanner } = useRainState();
  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-1">
      <div className="scrollbar-sleek @container min-w-0 flex-1 overflow-y-auto px-4 pb-24 pt-5 sm:px-6 lg:px-8 lg:pb-10">
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-text">{meta.title}</h2>
              {access === 'view' && (
                <Pill tone="neutral">
                  <Eye className="h-3 w-3" aria-hidden="true" /> View only
                </Pill>
              )}
              {access === 'cosign' && (
                <Pill tone="brand">
                  <PenLine className="h-3 w-3" aria-hidden="true" /> Co-sign
                </Pill>
              )}
              <DataLabel kind={label} />
            </div>
            <p className="mt-1 max-w-3xl text-[13px] text-text-muted">{meta.subtitle}</p>
            {insights && <p className="mt-1 text-[11.5px] text-text-subtle">Data as of: {FRESHNESS}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
        {freshnessBanner && insights && (
          <div role="status" className="mb-4 flex items-start gap-2 rounded-xl border border-info/30 bg-info-subtle px-3 py-2 text-[12.5px] text-info-700">
            <RefreshCw className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            Claims run through Q3 with a 45-day lag, so ED and low-value care figures trail by about six weeks. ADT is current to today.
          </div>
        )}
        <div className="space-y-4">{children}</div>
      </div>
      <CockpitPane />
    </div>
  );
}

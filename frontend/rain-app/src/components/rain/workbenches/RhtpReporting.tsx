import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import { Download, Printer } from 'lucide-react';
import { COUNTIES, OPTIONS, STATE, num, usdK } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { Button, RainCard, ResponsiveTable } from '../shell/rainKit';
import { downloadCountyCsv } from '../cards/exportCsv';
import { OptionTable, PcTrend } from '../cards/state';
import { usePaneContext } from './useWorkbench';

/** Visits and services by county (illustrative; reconcile to the members in view). */
const SERVICES: Record<string, { visits: number; services: number }> = {
  elko: { visits: 21_400, services: 48_900 },
  humboldt: { visits: 10_900, services: 25_300 },
  lander: { visits: 5_200, services: 12_100 },
  pershing: { visits: 3_700, services: 8_800 },
  whitePine: { visits: 7_900, services: 18_200 },
  churchill: { visits: 17_600, services: 40_100 },
};

/**
 * RHTP Reporting (P2, representative): people served, services delivered and
 * outcomes by county for the Outcomes Accelerator, ready to export as PDF
 * (the print view) or CSV. Aggregated, de-identified, small cells suppressed.
 */
export default function RhtpReporting({ access }: { access: Access }) {
  const [params] = useSearchParams();
  const [printing, setPrinting] = useState(params.get('print') === '1');
  // The print view: a clean document outside the app root, printed, then removed.
  useEffect(() => {
    if (!printing) return undefined;
    const done = () => setPrinting(false);
    window.addEventListener('afterprint', done);
    const t = window.setTimeout(() => window.print(), 500);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener('afterprint', done);
    };
  }, [printing]);
  usePaneContext({ label: 'RHTP progress summary, Outcomes Accelerator', chips: ['Generate the CMS progress summary', 'Export CSV'] });
  return (
    <WorkbenchLayout
      meta={WORKBENCHES.rhtpReporting}
      access={access}
      label="Aggregated, de-identified"
      actions={
        <>
          <Button onClick={() => setPrinting(true)}>
            <Printer className="h-3.5 w-3.5" aria-hidden="true" /> Export PDF
          </Button>
          <Button onClick={downloadCountyCsv}>
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export CSV
          </Button>
        </>
      }
    >
      <RainCard eyebrow="Outcomes Accelerator" title={`People served, services delivered and outcomes · ${STATE.networks} networks, ${STATE.sites} sites`} label="Aggregated, de-identified">
        <ResponsiveTable
          caption="RHTP progress by county"
          rows={COUNTIES}
          rowKey={(c) => c.id}
          columns={[
            { key: 'name', label: 'County', render: (c) => <span className="font-semibold">{c.name}</span> },
            { key: 'served', label: 'People served', align: 'right', render: (c) => num(c.members) },
            { key: 'visits', label: 'Visits', align: 'right', render: (c) => num(SERVICES[c.id].visits) },
            { key: 'services', label: 'Services', align: 'right', render: (c) => num(SERVICES[c.id].services) },
            { key: 'bp', label: 'BP control', align: 'right', render: (c) => `${c.bpControlPct}%` },
            { key: 'ed', label: 'Avoidable ED / 1,000', align: 'right', render: (c) => c.edPer1000 },
            { key: 'lv', label: 'Low-value care', align: 'right', render: (c) => usdK(c.lowValue) },
            { key: 'hf', label: 'Heart failure members', align: 'right', render: (c) => (c.heartFailure < STATE.suppressUnder ? '–' : num(c.heartFailure)) },
          ]}
        />
        <p className="mt-2 text-[12px] text-text-muted">
          {num(STATE.members)} people served. A dash is a suppressed cell (under {STATE.suppressUnder}). Visit and service counts are illustrative.
        </p>
      </RainCard>
      <div className="grid gap-4 @4xl:grid-cols-2">
        <OptionTable />
        <PcTrend />
      </div>
      {printing && createPortal(<PrintDocument />, document.body)}
    </WorkbenchLayout>
  );
}

/** What the PDF holds: the summary as a plain document, with the app hidden while printing. */
function PrintDocument() {
  return (
    <div className="rain-print-doc hidden bg-surface p-8 text-text print:block">
      <style>{'@media print { #root { display: none !important; } }'}</style>
      <p className="text-[11px] font-bold uppercase tracking-wide text-brand">RHTP progress summary · Rural Health Outcomes Accelerator</p>
      <h1 className="mt-1 text-xl font-bold">People served, services delivered and outcomes by county</h1>
      <p className="mt-1 text-[12px]">Aggregated and de-identified synthetic data for a demo. Cells under {STATE.suppressUnder} are suppressed.</p>
      <table className="mt-4 w-full border-collapse text-[12px]">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="py-1">County</th>
            <th className="py-1 text-right">People served</th>
            <th className="py-1 text-right">Visits</th>
            <th className="py-1 text-right">Services</th>
            <th className="py-1 text-right">BP control</th>
            <th className="py-1 text-right">Avoidable ED / 1,000</th>
            <th className="py-1 text-right">Heart failure members</th>
          </tr>
        </thead>
        <tbody>
          {COUNTIES.map((c) => (
            <tr key={c.id} className="border-b border-border-subtle">
              <td className="py-1">{c.name}</td>
              <td className="py-1 text-right">{num(c.members)}</td>
              <td className="py-1 text-right">{num(SERVICES[c.id].visits)}</td>
              <td className="py-1 text-right">{num(SERVICES[c.id].services)}</td>
              <td className="py-1 text-right">{c.bpControlPct}%</td>
              <td className="py-1 text-right">{c.edPer1000}</td>
              <td className="py-1 text-right">{c.heartFailure < STATE.suppressUnder ? '–' : num(c.heartFailure)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2 className="mt-5 text-[14px] font-bold">Recommended funding</h2>
      <ul className="mt-1 list-disc pl-5 text-[12px]">
        {OPTIONS.map((o) => (
          <li key={o.id}>
            {o.id}: {o.name}. {o.outcome}.
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[12px]">Fund A and C together; run B as a no-cost data service.</p>
    </div>
  );
}

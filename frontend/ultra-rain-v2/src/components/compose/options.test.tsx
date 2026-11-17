/**
 * The optional props added to the shared blocks (Phase 2 of the component
 * plan). Each must draw something when used; the persona render nets prove
 * that, when unused, every existing card draws exactly as before.
 */
import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { DataTable } from './DataTable';
import { Callout, Text } from './Text';
import TargetBar from '@/components/kpi/TargetBar';
import TrendChart from '@/components/kpi/TrendChart';
import ActionCardList from '@core/catalog/adapters/ActionCardList';
import { stackProps, chartProps, dataTableProps, textProps } from '@core/catalog/schemas';

const html = (el: React.ReactElement) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>);

describe('shared block options', () => {
  it('data_table: highlighted row, bar column, second line and tone', () => {
    const out = html(
      <DataTable
        columns={[{ key: 'name', label: 'Team', subKey: 'note' }, { key: 'sl', label: 'SL', kind: 'bar' }, { key: 'state', label: 'State', toneKey: 'state' }]}
        rows={[{ name: 'Auto Loans', note: 'Promo spike', sl: 54, state: 'critical' }, { name: 'Digital', note: '', sl: 91, state: 'good' }]}
        highlightRows={[1]}
      />,
    );
    expect(out).toContain('Promo spike');
    expect(out).toContain('width:54%');
    expect(out).toContain('text-critical-700');
    expect(out).toContain('bg-brand/[0.06]');
  });

  it('data_table: a status column keeps its own word and takes the tone colour; bar values get separators', () => {
    const out = html(
      <DataTable columns={[{ key: 'state', label: 'State', kind: 'status', toneKey: 'tone' }, { key: 'n', label: 'Calls', kind: 'bar', max: 50000 }]} rows={[{ state: 'On Target', tone: 'good', n: 19420 }]} />,
    );
    expect(out).toContain('On Target');
    expect(out).toContain('19,420');
  });

  it('data_table stacked: options survive the narrow layout', () => {
    const out = html(
      <DataTable stack columns={[{ key: 'name', label: 'Team', subKey: 'note' }]} rows={[{ name: 'Auto Loans', note: 'Promo spike' }]} highlightRows={[0]} />,
    );
    expect(out.match(/Promo spike/g)?.length).toBe(2);
    expect(out).toContain('border-brand/40');
  });

  it('text and callout links', () => {
    expect(html(<Text text="Comptroller release" href="https://www.marylandcomptroller.gov" />)).toContain('target="_blank"');
    expect(html(<Callout title="Open the worklist" action={{ label: 'Open', href: '/worklist' }} />)).toContain('href="/worklist"');
  });

  it('target bar: limit and secondary span', () => {
    const out = html(<TargetBar value={60} target={80} limit={95} secondaryValue={75} max={100} />);
    expect(out).toContain('bg-critical-600');
    expect(out).toContain('opacity-35');
  });

  it('trend chart: event marker and projection', () => {
    const out = html(
      <TrendChart points={[{ label: 'Mon', value: 1 }, { label: 'Tue', value: 2 }, { label: 'Wed', value: 3 }]} format={(v) => String(v)} marker={{ at: 'Tue', label: 'Script change' }} projectedFrom="Tue" />,
    );
    expect(out).toContain('Script change');
    expect(out).toContain('stroke-dasharray="6 5"');
  });

  it('action cards: approved state and details', () => {
    const out = html(<ActionCardList actions={[{ id: 'a1', title: 'Page the lead', details: ['Draft task: page the lead'] }]} confirmedIds={['a1']} />);
    expect(out).toContain('Draft task: page the lead');
  });

  it('schemas accept the options and refuse colours that are not token names', () => {
    expect(stackProps.safeParse({ children: [{ type: 'text', props: { text: 'x' } }], eyebrow: 'Plan', title: 'Brief', anchor: 'stage-1' }).success).toBe(true);
    expect(chartProps.safeParse({ kind: 'bar', series: [{ name: 'a', points: [{ label: 'x', value: 1 }] }], colors: ['border', 'brand'], target: { value: 1 } }).success).toBe(true);
    expect(chartProps.safeParse({ kind: 'bar', series: [{ name: 'a', points: [{ label: 'x', value: 1 }] }], colors: ['#ff0000'] }).success).toBe(false);
    expect(dataTableProps.safeParse({ columns: [{ key: 'a', label: 'A', kind: 'bar', max: 10 }], rows: [], highlightRows: [0] }).success).toBe(true);
    expect(textProps.safeParse({ text: 'x', href: 'javascript:alert(1)' }).success).toBe(false);
  });
});

/**
 * Tier-3 blocks drawn from data: DataTable in both its wide and stacked
 * layouts, and Chart with and without its optional extras.
 *
 * recharts' ResponsiveContainer measures its parent, which is 0×0 in jsdom, so
 * it is swapped for one that hands the chart a fixed size, and bars and lines
 * skip their entry animation. Everything else is real recharts.
 */
import { describe, it, expect, vi } from 'vitest';
import { cloneElement, isValidElement, type ReactNode } from 'react';
import { render, screen, within } from '@testing-library/react';
import { DataTable, type DataTableColumn } from './DataTable';
import { Chart } from './Chart';

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();
  const { Bar, Line } = actual;
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) =>
      isValidElement(children) ? cloneElement(children as React.ReactElement<{ width: number; height: number }>, { width: 480, height: 220 }) : null,
    // Drawn at their final size at once, rather than grown over animation frames.
    Bar: (props: React.ComponentProps<typeof Bar>) => <Bar {...props} isAnimationActive={false} />,
    Line: (props: React.ComponentProps<typeof Line>) => <Line {...props} isAnimationActive={false} />,
  };
});

const columns: DataTableColumn[] = [
  { key: 'team', label: 'Team' },
  { key: 'calls', label: 'Calls', kind: 'number' },
  { key: 'state', label: 'State', kind: 'status' },
];
const rows = [
  { team: 'Auto Loans', calls: 412, state: 'critical' },
  { team: 'Digital', calls: null, state: 'good' },
];

describe('DataTable (wide)', () => {
  it('draws a header per column and a row per record, right-aligning numbers', () => {
    render(<DataTable columns={columns} rows={rows} caption="Queue health" />);
    const table = screen.getByRole('table', { name: 'Queue health' });
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Team', 'Calls', 'State']);
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    expect(screen.getByRole('columnheader', { name: 'Calls' })).toHaveClass('text-right');
    expect(screen.getByRole('cell', { name: '412' })).toHaveClass('tabular-nums');
  });

  it('shows an em dash for a missing value, and a status cell as a badge', () => {
    render(<DataTable columns={columns} rows={rows} />);
    expect(screen.getByRole('cell', { name: '—' })).toBeInTheDocument();
    expect(screen.getByText('critical')).toHaveClass('text-critical');
  });

  it('a bar column clamps to its max and prints the value with separators', () => {
    const { container } = render(<DataTable columns={[{ key: 'n', label: 'N', kind: 'bar', max: 1000 }]} rows={[{ n: 2500 }, { n: 250 }]} />);
    const fills = [...container.querySelectorAll('.bg-brand')].map((el) => (el as HTMLElement).style.width);
    expect(fills).toEqual(['100%', '25%']);
    expect(screen.getByText('2,500')).toBeInTheDocument();
  });

  it('an empty row list still draws the header', () => {
    render(<DataTable columns={columns} rows={[]} />);
    expect(screen.getAllByRole('columnheader')).toHaveLength(3);
    expect(screen.getAllByRole('row')).toHaveLength(1);
  });
});

describe('DataTable (stacked)', () => {
  it('draws the wide table and a card list labelled by the caption, one card per row', () => {
    render(<DataTable stack columns={columns} rows={rows} caption="Queue health" />);
    expect(screen.getByRole('table', { name: 'Queue health' })).toBeInTheDocument();
    const list = screen.getByRole('list', { name: 'Queue health' });
    const cards = within(list).getAllByRole('listitem');
    expect(cards).toHaveLength(2);
    expect([...cards[0].querySelectorAll('dt')].map((d) => d.textContent)).toEqual(['Team', 'Calls', 'State']);
    expect([...cards[0].querySelectorAll('dd')].map((d) => d.textContent)).toEqual(['Auto Loans', '412', 'critical']);
  });

  it('emphasises the highlighted row as a card too', () => {
    render(<DataTable stack columns={columns} rows={rows} caption="q" highlightRows={[1]} />);
    const cards = within(screen.getByRole('list', { name: 'q' })).getAllByRole('listitem');
    expect(cards[0]).not.toHaveClass('border-brand/40');
    expect(cards[1]).toHaveClass('border-brand/40');
  });

  it('a status column with a tone keeps its own word and takes the tone colour in the card', () => {
    render(
      <DataTable stack caption="q" columns={[{ key: 'state', label: 'State', kind: 'status', toneKey: 'tone' }]} rows={[{ state: 'Behind plan', tone: 'amber' }]} />,
    );
    const card = within(screen.getByRole('list', { name: 'q' })).getByRole('listitem');
    expect(within(card).getByText('Behind plan')).toHaveClass('text-warning');
  });

  it('marks a missing value in the card', () => {
    render(<DataTable stack caption="q" columns={columns} rows={[rows[1]]} />);
    const card = within(screen.getByRole('list', { name: 'q' })).getByRole('listitem');
    // The wide table marks the same gap with an em dash; the card uses an en dash.
    expect(card.querySelectorAll('dd')[1].textContent).toMatch(/^[–—]$/);
  });
});

describe('Chart', () => {
  const one = [{ name: 'Calls', points: [{ label: 'Mon', value: 10 }, { label: 'Tue', value: 20 }, { label: 'Wed', value: 15 }] }];
  const two = [...one, { name: 'Abandoned', points: [{ label: 'Mon', value: 2 }, { label: 'Tue', value: 4 }, { label: 'Wed', value: 3 }] }];

  it('captions the figure with its title, and has no caption without one', () => {
    const { container, rerender } = render(<Chart kind="bar" series={one} title="Calls by day" />);
    expect(container.querySelector('figcaption')).toHaveTextContent('Calls by day');
    rerender(<Chart kind="bar" series={one} />);
    expect(container.querySelector('figcaption')).toBeNull();
  });

  it('a bar chart draws one bar per point in the first chart colour, with no legend for one series', () => {
    const { container } = render(<Chart kind="bar" series={one} />);
    const bars = container.querySelectorAll('.recharts-bar-rectangle path');
    expect(bars).toHaveLength(3);
    bars.forEach((b) => expect(b.getAttribute('fill')).toBe('var(--color-chart-1)'));
    expect(container.querySelector('.recharts-legend-wrapper')).toBeNull();
    expect(container.textContent).toContain('Wed');
  });

  it('two series get a legend and the second chart colour; colours can be set by token name', () => {
    const { container, rerender } = render(<Chart kind="bar" series={two} />);
    expect(container.querySelector('.recharts-legend-wrapper')).toHaveTextContent('Abandoned');
    const fills = new Set([...container.querySelectorAll('.recharts-bar-rectangle path')].map((b) => b.getAttribute('fill')));
    expect(fills).toEqual(new Set(['var(--color-chart-1)', 'var(--color-chart-2)']));
    rerender(<Chart kind="bar" series={two} colors={['brand', 'border']} />);
    const tokenFills = new Set([...container.querySelectorAll('.recharts-bar-rectangle path')].map((b) => b.getAttribute('fill')));
    expect(tokenFills).toEqual(new Set(['var(--color-brand)', 'var(--color-border)']));
  });

  it('pointStatus colours the named bars by status and leaves the rest in the series colour', () => {
    const { container } = render(<Chart kind="bar" series={one} pointStatus={{ Tue: 'red', Wed: 'on time' }} />);
    const fills = [...container.querySelectorAll('.recharts-bar-rectangle path')].map((b) => b.getAttribute('fill'));
    expect(fills).toEqual(['var(--color-chart-1)', 'var(--color-critical-600)', 'var(--color-success-600)']);
  });

  it('a target draws a labelled dashed reference line', () => {
    const { container } = render(<Chart kind="line" series={one} target={{ value: 18, label: 'SLA 18' }} />);
    expect(container.querySelector('.recharts-reference-line line')).toHaveAttribute('stroke-dasharray', '5 4');
    expect(container.textContent).toContain('SLA 18');
  });

  it('a line chart draws one line per series and formats ticks with the unit', () => {
    const { container } = render(<Chart kind="line" series={two} unit="%" />);
    expect(container.querySelectorAll('.recharts-line-curve')).toHaveLength(2);
    expect(container.querySelector('.recharts-yAxis-tick-labels')?.textContent).toMatch(/\d+%/);
  });

  it('draws an empty frame, without throwing, when there are no series', () => {
    const { container } = render(<Chart kind="bar" series={[]} title="Nothing yet" />);
    expect(container.querySelector('figure')).toHaveTextContent('Nothing yet');
    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(0);
  });
});

/**
 * The KPI kit's drawing logic: where a bar fills to, what colour a gap takes,
 * what a summary counts, and how each piece copes with missing data.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TargetBar from './TargetBar';
import TrendChart from './TrendChart';
import PeerBar from './PeerBar';
import StatusSummary from './StatusSummary';
import Sparkline from './Sparkline';

/** The inline width of the first element matching `selector`. */
const widthOf = (root: HTMLElement, selector: string) => (root.querySelector(selector) as HTMLElement | null)?.style.width;
const leftOf = (root: HTMLElement, selector: string) => (root.querySelector(selector) as HTMLElement | null)?.style.left;

describe('TargetBar', () => {
  it('draws nothing for a missing or NaN value', () => {
    expect(render(<TargetBar value={null} target={80} />).container.innerHTML).toBe('');
    expect(render(<TargetBar value={undefined} />).container.innerHTML).toBe('');
    expect(render(<TargetBar value={Number.NaN} />).container.innerHTML).toBe('');
  });

  it('a percentage fills to its value and ticks the target on a 0–100 scale', () => {
    const { container } = render(<TargetBar value={73} target={95} percent status="bad" valueLabel="73%" targetLabel="95% floor" />);
    expect(widthOf(container, '.bg-critical')).toBe('73%');
    expect(leftOf(container, '.bg-text')).toBe('95%');
    expect(screen.getByRole('img')).toHaveAttribute('aria-label', '73%, 95% floor');
    expect(screen.getByText('95% floor')).toBeInTheDocument();
  });

  it('without a max, pads the scale so the larger of value and target sits at 1/1.2', () => {
    const { container } = render(<TargetBar value={50} target={100} status="good" />);
    expect(widthOf(container, '.bg-success')).toBe(`${(50 / 120) * 100}%`);
  });

  it('clamps a value beyond max to a full bar and below min to empty', () => {
    expect(widthOf(render(<TargetBar value={140} max={100} status="good" />).container, '.bg-success')).toBe('100%');
    expect(widthOf(render(<TargetBar value={-5} max={100} status="good" />).container, '.bg-success')).toBe('0%');
  });

  it('a zero value with no target still draws (no divide-by-zero)', () => {
    const { container } = render(<TargetBar value={0} status="warn" />);
    expect(widthOf(container, '.bg-warning')).toBe('0%');
  });

  it('an unknown status falls back to neutral', () => {
    const { container } = render(<TargetBar value={10} max={100} status={'odd' as never} />);
    expect(container.querySelector('.bg-text-subtle')).not.toBeNull();
  });

  it('the target label is dropped when there is no target, and compact hides the words', () => {
    render(<TargetBar value={40} max={100} valueLabel="40" targetLabel="Target 60" />);
    expect(screen.queryByText('Target 60')).toBeNull();
    expect(screen.getByRole('img')).toHaveAttribute('aria-label', '40');
    const { container } = render(<TargetBar value={40} target={60} max={100} valueLabel="40 now" targetLabel="60 target" compact />);
    expect(container.textContent).toBe('');
  });
});

describe('TrendChart', () => {
  const fmt = (v: number) => `${v}%`;
  const points = [
    { label: 'Jan', value: 80, n: 1200 },
    { label: 'Feb', value: 82, n: 1350 },
    { label: 'Mar', value: 85, n: null },
  ];

  it('states the summary, labels the latest value and draws the target line label', () => {
    const { container } = render(<TrendChart points={points} format={fmt} target={90} targetLabel="Goal 90%" summary="Up three points since January." />);
    expect(screen.getByText('Up three points since January.')).toBeInTheDocument();
    const chart = screen.getByRole('img');
    expect(chart).toHaveAccessibleName('Up three points since January.');
    expect(chart.textContent).toContain('85%');
    expect(screen.getByText('Goal 90%')).toBeInTheDocument();
    expect(container.querySelector('line[stroke-dasharray="5 4"]')).not.toBeNull();
  });

  it('"View as table" swaps the chart for its data, with a responses column when any point has n', () => {
    render(<TrendChart points={points} format={fmt} tableCaption="Satisfaction" />);
    const toggle = screen.getByRole('button', { name: 'View as table' });
    fireEvent.click(toggle);
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.getByRole('table', { name: 'Satisfaction' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Responses' })).toBeInTheDocument();
    expect(screen.getByRole('row', { name: 'Feb 82% 1,350' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View as chart' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('omits the responses column when no point carries n', () => {
    render(<TrendChart points={[{ label: 'Q1', value: 1 }, { label: 'Q2', value: 2 }]} format={String} />);
    fireEvent.click(screen.getByRole('button', { name: 'View as table' }));
    expect(screen.queryByRole('columnheader', { name: 'Responses' })).toBeNull();
  });

  it('a single point draws, centred, without dividing by zero', () => {
    const { container } = render(<TrendChart points={[{ label: 'Now', value: 5 }]} format={String} />);
    const path = container.querySelector('path[fill="none"]')?.getAttribute('d') ?? '';
    expect(path).toMatch(/^M[\d.]+,[\d.]+$/);
    expect(path).not.toContain('NaN');
  });

  it('a flat series draws without NaN', () => {
    const { container } = render(<TrendChart points={[{ label: 'A', value: 3 }, { label: 'B', value: 3 }]} format={String} />);
    expect(container.innerHTML).not.toContain('NaN');
  });

  it('more than eight points label only the first, middle and last tick', () => {
    const many = Array.from({ length: 12 }, (_, i) => ({ label: `P${i}`, value: i }));
    const { container } = render(<TrendChart points={many} format={String} />);
    const ticks = [...container.querySelectorAll('text[y]')].map((t) => t.textContent).filter((t) => t?.startsWith('P'));
    expect(ticks).toEqual(['P0', 'P5', 'P11']);
  });

  it('hovering reads out the nearest point', () => {
    render(<TrendChart points={points} format={fmt} />);
    const svg = screen.getByRole('img');
    svg.getBoundingClientRect = () => ({ left: 0, width: 640, top: 0, height: 200, right: 640, bottom: 200, x: 0, y: 0, toJSON: () => ({}) });
    // jsdom has no PointerEvent, so fireEvent.pointerMove would drop clientX.
    fireEvent(svg, new MouseEvent('pointermove', { bubbles: true, clientX: 0 }));
    expect(svg.textContent).toContain('Jan: 80%');
    fireEvent.pointerLeave(svg);
    expect(svg.textContent).not.toContain('Jan: 80%');
  });

  // With no points there is no last value to label; the chart draws nothing
  // rather than throwing (it used to read `points[-1]`).
  it('draws without throwing when there are no points', () => {
    expect(() => render(<TrendChart points={[]} format={String} />)).not.toThrow();
  });
});

describe('PeerBar', () => {
  it('colours the gap by whether it is good for the measure', () => {
    expect(render(<PeerBar value={80} peer={70} />).container.querySelector('.bg-success')).not.toBeNull();
    expect(render(<PeerBar value={80} peer={70} higherIsBetter={false} />).container.querySelector('.bg-critical')).not.toBeNull();
  });

  it('no peer, or no gap, reads as neutral and draws no tick', () => {
    const { container } = render(<PeerBar value={60} />);
    expect(container.querySelector('.bg-brand\\/60')).not.toBeNull();
    expect(container.querySelector('.bg-text')).toBeNull();
    expect(render(<PeerBar value={60} peer={60} />).container.querySelector('.bg-brand\\/60')).not.toBeNull();
  });

  it('places the bar and tick on the shared scale and prints the label', () => {
    const { container } = render(<PeerBar value={30} peer={45} min={0} max={60} valueLabel="30 days" />);
    expect(widthOf(container, '.bg-critical')).toBe('50%');
    expect(leftOf(container, '.bg-text')).toBe('75%');
    expect(screen.getByText('30 days')).toBeInTheDocument();
  });

  it('draws nothing without a value', () => {
    expect(render(<PeerBar value={null} peer={10} />).container.innerHTML).toBe('');
  });
});

describe('StatusSummary', () => {
  const segments = [
    { key: 'bad', label: 'Off target', count: 2, status: 'bad' as const },
    { key: 'warn', label: 'Near target', count: 1, status: 'warn' as const },
    { key: 'good', label: 'On target', count: 5, status: 'good' as const },
    { key: 'none', label: 'No target yet', count: 0, status: 'neutral' as const },
  ];

  it('counts each status, sizes the bar in proportion, and hides an empty neutral', () => {
    const { container } = render(<MemoryRouter><StatusSummary title="8 measures" segments={segments} /></MemoryRouter>);
    expect(screen.getByRole('region', { name: '8 measures' })).toBeInTheDocument();
    const terms = [...container.querySelectorAll('dt')].map((d) => d.textContent);
    expect(terms).toEqual(['Off target', 'Near target', 'On target']);
    const counts = [...container.querySelectorAll('dd')].map((d) => d.textContent);
    expect(counts).toEqual(['2', '1', '5']);
    expect(widthOf(container, '.bg-critical')).toBe(`${(2 / 8) * 100}%`);
    expect(widthOf(container, '.bg-success')).toBe(`${(5 / 8) * 100}%`);
  });

  it('shows a neutral status once it has members', () => {
    const { container } = render(
      <MemoryRouter><StatusSummary title="t" segments={segments.map((s) => (s.key === 'none' ? { ...s, count: 1 } : s))} /></MemoryRouter>,
    );
    expect(container.querySelectorAll('dt')).toHaveLength(4);
  });

  it('names the worst measures, linking those with a route', () => {
    render(
      <MemoryRouter>
        <StatusSummary title="t" segments={segments} worst={{ label: 'Off target', items: [{ label: 'Wait time', to: '/kpi/wait' }, { label: 'Backlog' }] }} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Wait time' })).toHaveAttribute('href', '/kpi/wait');
    expect(screen.getByText('Backlog').closest('a')).toBeNull();
  });

  it('all-zero segments draw no bar and no NaN', () => {
    const { container } = render(<MemoryRouter><StatusSummary title="t" segments={segments.map((s) => ({ ...s, count: 0 }))} /></MemoryRouter>);
    expect(container.innerHTML).not.toContain('NaN');
    expect(container.querySelectorAll('[aria-hidden="true"] > span')).toHaveLength(0);
  });
});

describe('Sparkline', () => {
  it('needs two real values to draw', () => {
    expect(render(<Sparkline values={null} />).container.innerHTML).toBe('');
    expect(render(<Sparkline values={[]} />).container.innerHTML).toBe('');
    expect(render(<Sparkline values={[4, null, undefined]} />).container.innerHTML).toBe('');
  });

  it('skips missing values and ends on the last real one', () => {
    const { container } = render(<Sparkline values={[1, null, 3]} width={100} height={20} />);
    const d = container.querySelector('path[fill="none"]')?.getAttribute('d') ?? '';
    expect(d.split('L')).toHaveLength(2);
    expect(container.querySelector('circle')?.getAttribute('cx')).toBe(String(100 - 3.5));
  });

  it('draws a target line only when given one', () => {
    expect(render(<Sparkline values={[1, 2]} />).container.querySelector('line')).toBeNull();
    expect(render(<Sparkline values={[1, 2]} target={1.5} />).container.querySelector('line')).not.toBeNull();
  });
});

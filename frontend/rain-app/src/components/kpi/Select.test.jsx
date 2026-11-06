/**
 * The KPI kit Select: a listbox that opens from the keyboard and the mouse,
 * moves with the arrow keys, selects with Enter, closes with Escape, filters
 * long lists, and names itself for screen readers.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import Select from './Select';

const OPTIONS = [
  { value: 'court', label: 'Court-wide' },
  { value: 'd1', label: 'Division One' },
  { value: 'd2', label: 'Division Two' },
];

describe('KPI kit Select', () => {
  afterEach(cleanup);

  it('names itself, opens on click and selects an option', () => {
    const onChange = vi.fn();
    render(<Select label="Show" value="court" onChange={onChange} options={OPTIONS} />);
    const trigger = screen.getByRole('button', { name: /show/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveTextContent('Court-wide');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Court-wide' })).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByRole('option', { name: 'Division Two' }));
    expect(onChange).toHaveBeenCalledWith('d2');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('works from the keyboard: arrows move, Enter selects, Escape closes', () => {
    const onChange = vi.fn();
    render(<Select label="Show" value="court" onChange={onChange} options={OPTIONS} />);
    const trigger = screen.getByRole('button', { name: /show/i });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const list = screen.getByRole('listbox');
    fireEvent.keyDown(list, { key: 'ArrowDown' });
    expect(list.getAttribute('aria-activedescendant')).toBe(screen.getByRole('option', { name: 'Division One' }).id);
    fireEvent.keyDown(list, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith('d1');
    fireEvent.keyDown(trigger, { key: 'Enter' });
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('groups options and searches a long list', () => {
    const groups = [
      { label: 'Divisions', options: OPTIONS.slice(1) },
      { label: 'Courthouses', options: Array.from({ length: 14 }, (_, i) => ({ value: `s${i}`, label: i === 3 ? 'Pasadena Courthouse' : `Courthouse ${i}` })) },
    ];
    const onChange = vi.fn();
    render(<Select label="Show" value="d1" onChange={onChange} groups={groups} />);
    fireEvent.click(screen.getByRole('button', { name: /show/i }));
    expect(screen.getByRole('group', { name: 'Courthouses' })).toBeInTheDocument();
    const search = screen.getByRole('textbox', { name: /search show/i });
    fireEvent.change(search, { target: { value: 'pasa' } });
    expect(screen.getAllByRole('option')).toHaveLength(1);
    fireEvent.keyDown(search, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith('s3');
  });

  it('does not open when disabled', () => {
    render(<Select label="Courthouse" value="court" onChange={() => {}} options={OPTIONS} disabled />);
    fireEvent.click(screen.getByRole('button', { name: /courthouse/i }));
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });
});

/**
 * The small shared badges: StatusBadge maps any status spelling (or a health
 * score) onto one colour and keeps the caller's word; SourceBadge picks a dot
 * colour by source name.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusBadge from './StatusBadge';
import SourceBadge from '@/components/chat/SourceBadge';

const badgeOf = (status: string | number, label?: string) =>
  render(<StatusBadge status={status} label={label} />).container.firstElementChild as HTMLElement;

describe('StatusBadge', () => {
  it.each([
    ['good', 'text-success'],
    ['ok', 'text-success'],
    [' Compliant ', 'text-success'],
    ['amber', 'text-warning'],
    ['at risk', 'text-warning'],
    ['critical', 'text-critical'],
    ['Past Due', 'text-critical'],
    ['info', 'text-text-muted'],
    ['in progress', 'text-text-muted'],
    ['something new', 'text-text-muted'],
  ])('"%s" draws as %s', (status, cls) => {
    expect(badgeOf(status)).toHaveClass(cls);
  });

  it.each([
    [92, 'text-success'],
    [80, 'text-success'],
    [79, 'text-warning'],
    [60, 'text-warning'],
    [59, 'text-critical'],
    [0, 'text-critical'],
  ])('a health score of %d draws as %s', (score, cls) => {
    expect(badgeOf(score)).toHaveClass(cls);
  });

  it('shows the value it was given unless a label is supplied', () => {
    expect(badgeOf('amber')).toHaveTextContent('amber');
    expect(badgeOf(72)).toHaveTextContent('72');
    expect(badgeOf('amber', 'Watch closely')).toHaveTextContent('Watch closely');
  });

  it('always pairs the colour with an icon (never colour alone)', () => {
    expect(badgeOf('critical').querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    expect(badgeOf('unknown-word').querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  });

  it('size lg uses the larger padding', () => {
    const el = render(<StatusBadge status="good" size="lg" />).container.firstElementChild;
    expect(el).toHaveClass('px-2.5');
  });
});

describe('SourceBadge', () => {
  const dotOf = (source?: string) => {
    const { container } = render(<SourceBadge source={source} />);
    return container.querySelector('span > span') as HTMLElement;
  };

  it('a known source gets its own dot colour and its name', () => {
    expect(dotOf('Genesys Cloud')).toHaveClass('bg-success-400');
    expect(dotOf('Fraud & Risk Signal Feed')).toHaveClass('bg-critical-400');
    expect(screen.getByText('Fraud & Risk Signal Feed')).toBeInTheDocument();
  });

  it('any "<Client> Member CRM" source is matched by its suffix', () => {
    expect(dotOf('Acme Member CRM')).toHaveClass('bg-category2-400');
    expect(dotOf('Member CRM Export')).toHaveClass('bg-text-subtle');
  });

  it('an unknown or missing source falls back to the neutral dot without throwing', () => {
    expect(dotOf('Spreadsheet')).toHaveClass('bg-text-subtle');
    expect(dotOf(undefined)).toHaveClass('bg-text-subtle');
  });
});


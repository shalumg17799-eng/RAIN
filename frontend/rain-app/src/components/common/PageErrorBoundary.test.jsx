import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PageErrorBoundary from './PageErrorBoundary';

function Boom({ explode }) {
  if (explode) throw new Error('render failed');
  return <p>content</p>;
}

describe('PageErrorBoundary', () => {
  it('renders children untouched when nothing throws', () => {
    const { container } = render(<PageErrorBoundary resetKey="/a"><Boom /></PageErrorBoundary>);
    expect(container.innerHTML).toBe('<p>content</p>');
  });

  it('contains a render error and clears it when the key changes', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { rerender } = render(<PageErrorBoundary resetKey="/a" label="page"><Boom explode /></PageErrorBoundary>);
    expect(screen.getByRole('alert')).toHaveTextContent("This page couldn't be displayed");
    rerender(<PageErrorBoundary resetKey="/b" label="page"><Boom /></PageErrorBoundary>);
    expect(screen.getByText('content')).toBeInTheDocument();
    spy.mockRestore();
  });

  it('retries in place', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    let explode = true;
    function Flaky() { if (explode) throw new Error('once'); return <p>recovered</p>; }
    render(<PageErrorBoundary resetKey="/a"><Flaky /></PageErrorBoundary>);
    explode = false;
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(screen.getByText('recovered')).toBeInTheDocument();
    spy.mockRestore();
  });
});

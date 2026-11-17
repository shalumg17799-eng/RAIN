import { useEffect, useRef, useState } from 'react';

/**
 * The rendered width of an element, kept current with a ResizeObserver. RAIN's
 * charts render in a wide workbench and in the 380-pixel Ask AI pane alike, so
 * they size their axis labels by their own width rather than the window's.
 */
export function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, width };
}

/** Axis props for category labels: angled and shortened when the chart is narrow. */
export function categoryAxis(width: number, short: (label: string) => string = (l) => l) {
  const narrow = width > 0 && width < 460;
  return narrow
    ? { interval: 0 as const, angle: -35, textAnchor: 'end' as const, height: 58, tick: { fontSize: 10 }, tickFormatter: short }
    : { interval: 0 as const, tick: { fontSize: 10 } };
}

import { useEffect } from 'react';
import { useIntraday } from '../context/IntradayContext';
import { useActiveManifest } from '@core/runtime/useActiveManifest';

/**
 * Mounted at AppShell scope so the Sticky Intelligence Widget can render the
 * briefing data on every route — not just on /ask. Pushes the active persona's
 * intraday baseline (its manifest's `briefing.baseline`) into IntradayContext,
 * and clears it for personas without one so the widget unmounts cleanly.
 */
export default function useBriefingBaseline() {
  const manifest = useActiveManifest();
  const { setBaseline, resetSnapshot } = useIntraday();
  const baseline = manifest?.briefing?.baseline ?? null;

  useEffect(() => {
    setBaseline(baseline);
    resetSnapshot();
  }, [baseline, setBaseline, resetSnapshot]);
}

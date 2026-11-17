import { useEffect, useState } from 'react';

/**
 * Reads from an async data-access function. This is the seam that lets the
 * Platform Admin Gen UI components stay untouched when the static governance
 * fixtures are swapped for live API calls — only the getter body changes.
 *
 * Usage: const data = useAsyncData(getFieldLedger);
 */
export function useAsyncData(getter) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.resolve(getter())
      .then((d) => { if (alive) setData(d); })
      .catch(() => { if (alive) setData(null); });
    return () => { alive = false; };
  }, [getter]);

  return data;
}

export default useAsyncData;

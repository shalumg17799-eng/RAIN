import { createContext, useContext, useState, useCallback } from 'react';
import { STORAGE_KEYS } from '@core/contract/storageKeys';

/**
 * Brand-context selector state — Newfold Digital only.
 *
 * Newfold is a portfolio of 80+ brands, so the care operation reads at two
 * altitudes: a cross-brand roll-up (the default) and a single-brand focus. This
 * context holds the active brand; the selector in TopHeader sets it, and
 * brand-aware components (e.g. the director's BrandRollupTable) narrow to it.
 *
 * 'all' = cross-brand roll-up. Other clients never mount the selector, so their
 * value stays 'all' and nothing changes for them.
 */
const BrandContext = createContext(null);
const SESSION_KEY = STORAGE_KEYS.activeBrand;

export function BrandProvider({ children }) {
  const [brand, setBrandState] = useState(() => {
    try {
      return sessionStorage.getItem(SESSION_KEY) || 'all';
    } catch {
      return 'all';
    }
  });

  const setBrand = useCallback((id) => {
    setBrandState(id);
    try {
      sessionStorage.setItem(SESSION_KEY, id);
    } catch {
      /* ignore */
    }
  }, []);

  return <BrandContext.Provider value={{ brand, setBrand }}>{children}</BrandContext.Provider>;
}

export function useBrand() {
  const ctx = useContext(BrandContext);
  // Components outside the provider (or non-Newfold clients) default to cross-brand.
  return ctx || { brand: 'all', setBrand: () => {} };
}

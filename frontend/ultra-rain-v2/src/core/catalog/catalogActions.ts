/** The chip/action callbacks a catalog component may use (provided by the workspace). */
import { createContext } from 'react';
import type { CatalogActions } from './types';

export const CatalogActionsContext = createContext<CatalogActions>({});
export const CatalogActionsProvider = CatalogActionsContext.Provider;

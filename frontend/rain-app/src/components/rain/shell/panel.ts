import { createContext, useContext } from 'react';

/** True inside the docked Cockpit pane (workbench mode), false in Cockpit mode. */
export const PanelContext = createContext(false);
export const usePanel = () => useContext(PanelContext);

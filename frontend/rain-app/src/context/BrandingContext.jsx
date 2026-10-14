import { createContext, useContext, useState, useEffect } from 'react';
import { CLIENTS, DEFAULT_CLIENT_ID, STORAGE_KEY } from '../config/clients';

const BrandingContext = createContext(null);

export function BrandingProvider({ children }) {
  const [clientId, setClientIdState] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved && CLIENTS[saved] ? saved : DEFAULT_CLIENT_ID;
  });

  const client = CLIENTS[clientId];

  // Update document title and favicon whenever client changes
  useEffect(() => {
    document.title = client.name;

    let link = document.querySelector("link[rel='icon']");
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }
    link.href = client.favicon;
  }, [client]);

  function setClientId(id) {
    if (!CLIENTS[id]) return;
    localStorage.setItem(STORAGE_KEY, id);
    setClientIdState(id);
  }

  return (
    <BrandingContext.Provider value={{ client, clientId, setClientId, CLIENTS }}>
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding() {
  return useContext(BrandingContext);
}

import { createContext, useContext, useState } from 'react';
import { STORAGE_KEY, CLIENTS, CREDENTIALS } from '@/clients/registry';

const AUTH_KEY = 'auth_state';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(AUTH_KEY) || 'null');
      // Ignore a session saved for a client this build doesn't include.
      return saved && CLIENTS[saved.clientId] ? saved : null;
    } catch {
      return null;
    }
  });

  // Standard credential login
  function login(username, password) {
    const key = username.toLowerCase().trim();
    const cred = CREDENTIALS[key];
    if (!cred || cred.password !== password) return false;

    const authState = { username: key, clientId: cred.clientId, mode: 'credentials' };
    localStorage.setItem(AUTH_KEY, JSON.stringify(authState));
    localStorage.setItem(STORAGE_KEY, cred.clientId);
    setAuth(authState);
    return true;
  }

  function logout() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(STORAGE_KEY);
    setAuth(null);
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!auth, auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

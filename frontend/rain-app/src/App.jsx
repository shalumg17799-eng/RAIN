import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { PersonaProvider } from './context/PersonaContext';
import { BrandingProvider } from './context/BrandingContext';
import AppShell from './components/layout/AppShell';
import LoginScreen from './screens/LoginScreen';
import AskTheAI from './screens/AskTheAI';
import MemberJourney from './screens/MemberJourney';
import RiskSignals from './screens/RiskSignals';
import DataSources from './screens/DataSources';
import PatientConversationView from './screens/PatientConversationView';

function AppContent() {
  const { isAuthenticated } = useAuth();

  // Patient-facing mobile app — a public route (a rural patient just opens the app,
  // no operator login). Self-contained and rendered outside the operator shell and
  // persona dropdown, with role-based access (the patient sees only their own info).
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/patient')) {
    return <PatientConversationView />;
  }

  // Not yet authenticated → RAIN login
  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  // Authenticated → full app
  return (
    <BrowserRouter>
      <BrandingProvider>
        <PersonaProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<AskTheAI />} />
              <Route path="/ask" element={<AskTheAI />} />
              <Route path="/journey" element={<MemberJourney />} />
              <Route path="/risk" element={<RiskSignals />} />
              <Route path="/data-sources" element={<DataSources />} />
            </Route>
          </Routes>
        </PersonaProvider>
      </BrandingProvider>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

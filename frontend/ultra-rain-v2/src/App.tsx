import { BrowserRouter, Routes, Route, Navigate, Outlet, useNavigate, useParams } from 'react-router-dom';
import { useEffect, lazy, Suspense } from 'react';
import type { ReactElement, ReactNode } from 'react';
import type { NavigateFunction } from 'react-router-dom';
import { SessionProvider, useSession } from './context/SessionContext';
import { ClientProvider, useClient } from './context/ClientContext';
import { PersonaProvider } from './context/PersonaContext';
import { BrandingProvider } from './context/BrandingContext';
import { ThemeProvider } from '@core/providers/ThemeProvider';
import { clientIdForSlug, LOGIN_PATH } from './config/access';
import { homePathFor } from './config/clients';
import AppShell from './components/layout/AppShell';
import ClientLoginScreen from './components/pages/ClientLoginScreen';
import AskTheAI from './components/pages/AskTheAI';
import DataSources from './components/pages/DataSources';

// One lazy page component serves the nine workbench routes; the patient's
// phone-framed SMS view renders inside the session but outside the app shell,
// because the patient does not use Cockpit.
const ValueBasedCarePage = lazy(() => import('./components/value-based-care/pages/ValueBasedCarePage'));
const ValueBasedCarePatientView = lazy(() => import('./components/value-based-care/patient/PatientView'));

declare global {
  interface Window {
    /** The router's navigate(), for the guided-demo runner (see DemoNavigateBridge). */
    demoNavigate?: NavigateFunction | null;
  }
}

/** A lazily loaded route: its path and the element it renders. */
type LazyRoute = [path: string, render: () => ReactElement];

/** Every lazily loaded page, by path. */
const LAZY_ROUTES: LazyRoute[] = [
  ...(['value-insights', 'quality-gate', 'low-value-care', 'model-governance', 'county-explorer', 'rhtp-reporting', 'worklist', 'scheduling', 'reminders'] as const)
    .map((page): LazyRoute => [`/${page}`, () => <ValueBasedCarePage page={page} />]),
];

/** The brief fill while a lazy route's chunk loads (one definition for every lazy route). */
function RouteSuspense({ children }: { children?: ReactNode }) {
  return <Suspense fallback={<div className="flex-1 bg-surface-2/50" />}>{children}</Suspense>;
}

// Expose navigate() for the demo runner
function DemoNavigateBridge() {
  const navigate = useNavigate();
  useEffect(() => {
    window.demoNavigate = navigate;
    return () => { window.demoNavigate = null; };
  }, [navigate]);
  return null;
}

/** `/login/<slug>` — the client's gate. */
function ClientGateRoute() {
  const { slug } = useParams();
  const { isUnlocked, scope } = useSession();
  // This route is `/login/:slug`, so the param is always present.
  const clientId = clientIdForSlug(slug!);

  // Unknown slug: no such tenant, so fall back to the one real door rather than
  // rendering a blank branded page for a client that does not exist.
  if (!clientId) return <Navigate to={LOGIN_PATH} replace />;
  // Already signed in as this client — nothing to do here.
  if (isUnlocked && scope === clientId) return <Navigate to={homePathFor(clientId)} replace />;

  return <ClientLoginScreen clientId={clientId} />;
}

/**
 * Everything behind the gate: the guard and the branded provider stack, as a
 * single pathless layout route.
 *
 * A layout route rather than a wrapper around a nested `<Routes>`, because a
 * descendant `<Routes>` resolves its paths relative to the parent and React
 * Router rejects the absolute `/ask`-style paths the app already uses. This
 * keeps every route absolute and declared in one list.
 */
function ProtectedShell() {
  const { isUnlocked, exitPath } = useSession();
  const { hasClient } = useClient();

  if (!isUnlocked) return <Navigate to={exitPath || LOGIN_PATH} replace />;
  if (!hasClient) return <Navigate to={LOGIN_PATH} replace />;

  return (
    <BrandingProvider>
      <ThemeProvider>
        <PersonaProvider>
          <DemoNavigateBridge />
          <Outlet />
        </PersonaProvider>
      </ThemeProvider>
    </BrandingProvider>
  );
}

/** `/` inside the app: the client's own landing page (the briefing). */
function HomeRedirect() {
  const { clientId } = useClient();
  return <Navigate to={homePathFor(clientId)} replace />;
}

function AppRoutes() {
  const { isUnlocked } = useSession();

  // The sign-in door has no brand tokens yet, so it needs a title of its own.
  // Once the session unlocks, BrandingProvider takes over and overrides this
  // with the client's name; signing out resets it back.
  useEffect(() => {
    if (!isUnlocked) document.title = 'RAIN';
  }, [isUnlocked]);

  return (
    <Routes>
      {/* The door. It lives above BrandingProvider — the session is not open
          yet, so there are no brand tokens to inherit. */}
      <Route path="/login/:slug" element={<ClientGateRoute />} />
      <Route path="/login" element={<Navigate to={LOGIN_PATH} replace />} />

      {/* The signed-in application. */}
      <Route element={<ProtectedShell />}>
        <Route path="/patient" element={<RouteSuspense><ValueBasedCarePatientView /></RouteSuspense>} />
        <Route element={<AppShell />}>
          <Route index element={<HomeRedirect />} />
          <Route path="/ask" element={<AskTheAI />} />
          {LAZY_ROUTES.map(([path, render]) => (
            <Route key={path} path={path} element={<RouteSuspense>{render()}</RouteSuspense>} />
          ))}
          <Route path="/data-sources" element={<DataSources />} />
          {/* Anything unrecognised inside the app goes to the briefing
              rather than to the gate — you are signed in, you just typed
              a route that does not exist. */}
          <Route path="*" element={<Navigate to="/ask" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    // SessionProvider sits above ClientProvider on purpose: its initialiser
    // runs first, so an `?access=` unlock is consumed before ClientProvider
    // reads the stored client id.
    //
    // BrowserRouter sits above BOTH, so that `/login/<slug>` is a real address
    // rather than a branch rendered above the router.
    <BrowserRouter>
      <SessionProvider>
        <ClientProvider>
          <AppRoutes />
        </ClientProvider>
      </SessionProvider>
    </BrowserRouter>
  );
}

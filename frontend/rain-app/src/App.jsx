import { BrowserRouter, Routes, Route, Navigate, Outlet, useNavigate, useParams } from 'react-router-dom';
import { useEffect, lazy, Suspense } from 'react';
import { SessionProvider, useSession } from './context/SessionContext';
import { ClientProvider, useClient } from './context/ClientContext';
import { PersonaProvider } from './context/PersonaContext';
import { BrandingProvider } from './context/BrandingContext';
import { BrandProvider } from './context/BrandContext';
import { ThemeProvider } from '@core/providers/ThemeProvider';
import { clientIdForSlug, slugForClientId, ULTRA_SLUG } from './config/access';

/** This standalone build serves one client; its door is the default landing page. */
const CLIENT_DOOR_SLUG = slugForClientId(DEFAULT_CLIENT_ID);
import { homePathFor, DEFAULT_CLIENT_ID } from './config/clients';
import AppShell from './components/layout/AppShell';
import LoginScreen from './screens/LoginScreen';
import ClientLoginScreen from './screens/ClientLoginScreen';
import AccessDeniedScreen from './screens/AccessDeniedScreen';
import ChooseClientScreen from './screens/ChooseClientScreen';
import AskTheAI from './screens/AskTheAI';
import DataSources from './screens/DataSources';

// SLED / RAIN. One lazy page component serves the nine workbench routes; the
// patient's phone-framed SMS view renders inside the session but outside the
// app shell, because the patient does not use Cockpit.
const RainPage = lazy(() => import('./components/rain/pages/RainPage'));
const RainPatientView = lazy(() => import('./components/rain/patient/PatientView'));
// The component catalog gallery (platform sign-ins only). Lazy: it pulls the
// whole catalog and zod's JSON Schema export, which no tenant needs.
const CatalogGallery = lazy(() => import('./screens/CatalogGallery'));

/**
 * Every lazily loaded page, by path. A tenant's pages download only when one of
 * its personas navigates to them, so no other tenant pays for them.
 */
const LAZY_ROUTES = [
  ...['value-insights', 'quality-gate', 'low-value-care', 'model-governance', 'county-explorer', 'rhtp-reporting', 'worklist', 'scheduling', 'reminders']
    .map((page) => [`/${page}`, () => <RainPage page={page} />]),
  ['/catalog', () => <CatalogGallery />],
];

/** The brief fill while a lazy route's chunk loads (one definition for every lazy route). */
function RouteSuspense({ children }) {
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

/**
 * Where an unauthenticated visitor gets sent: RAIN's own door. This standalone
 * build serves one client, so opening the app lands on RAIN's sign-in page.
 * The platform door (`/login/ultra`) still works and its picker lists RAIN.
 */
const LOCKED_REDIRECT_PATH = `/login/${CLIENT_DOOR_SLUG}`;

/**
 * `/login/ultra` — the platform gate, and the market picker behind it.
 *
 * Three ways this route resolves, and only two of them reach the picker:
 *
 *   `?access=…`        unlocked as platform scope before this even renders
 *                      (SessionContext consumes the token), so → picker.
 *   no session         → the platform sign-in form. Correct credentials unlock
 *                      platform scope and land on the picker.
 *   client scope       → refused. Signed in, but at somebody else's door.
 */
function UltraGateRoute() {
  const { isUnlocked, isPlatformScope, scopedClientId } = useSession();
  const { hasClient, clientId } = useClient();

  // A client-scoped session has no business at the platform picker. This used
  // to redirect quietly into their own tenant, which hid the refusal — a user
  // who typed this URL deserves to be told it is not theirs rather than to
  // wonder why the address bar changed.
  if (isUnlocked && !isPlatformScope) {
    return <AccessDeniedScreen clientId={scopedClientId} />;
  }
  if (!isUnlocked) return <LoginScreen />;
  // Picking a market and client is the last thing this route does; once a
  // client is chosen the app takes over. The picker used to be a branch rather
  // than a route, so selecting simply re-rendered — now it has to navigate.
  if (hasClient) return <Navigate to={homePathFor(clientId)} replace />;
  return <ChooseClientScreen />;
}

/** `/login/<slug>` — one client's own gate. */
function ClientGateRoute() {
  const { slug } = useParams();
  const { isUnlocked, scope } = useSession();
  const clientId = clientIdForSlug(slug);

  // Unknown slug: no such tenant, so fall back to the platform door rather than
  // rendering a blank branded page for a client that does not exist.
  if (!clientId) return <Navigate to={`/login/${CLIENT_DOOR_SLUG}`} replace />;
  // Already signed in as this client — nothing to do here.
  if (isUnlocked && scope === clientId) return <Navigate to={homePathFor(clientId)} replace />;

  return <ClientLoginScreen clientId={clientId} />;
}

/**
 * Everything behind the gates: the guard and the client-branded provider stack,
 * as a single pathless layout route.
 *
 * A layout route rather than a wrapper around a nested `<Routes>`, because a
 * descendant `<Routes>` resolves its paths relative to the parent and React
 * Router rejects the absolute `/ask`-style paths the app already uses. This
 * keeps every route absolute and declared in one list.
 */
function ProtectedShell() {
  const { isUnlocked, exitPath } = useSession();
  const { hasClient } = useClient();

  if (!isUnlocked) return <Navigate to={exitPath || LOCKED_REDIRECT_PATH} replace />;
  // Signed in at the platform door but no client picked yet — the picker is a
  // route now, so this is a redirect rather than a branch.
  if (!hasClient) return <Navigate to={`/login/${ULTRA_SLUG}`} replace />;

  return (
    <BrandingProvider>
      <ThemeProvider>
        <PersonaProvider>
          <BrandProvider>
            <DemoNavigateBridge />
            <Outlet />
          </BrandProvider>
        </PersonaProvider>
      </ThemeProvider>
    </BrandingProvider>
  );
}

/** `/` inside the app: the client's own landing page (most land on the briefing). */
function HomeRedirect() {
  const { clientId } = useClient();
  return <Navigate to={homePathFor(clientId)} replace />;
}

function AppRoutes() {
  const { hasClient } = useClient();

  // Default document title is "RAIN" (this build's one client, used by the
  // pre-app screens). Once signed in, BrandingProvider sets the client's name;
  // signing out resets it back.
  useEffect(() => {
    if (!hasClient) document.title = 'RAIN';
  }, [hasClient]);

  return (
    <Routes>
      {/* The two doors. Both live above BrandingProvider — there is no client
          selected yet, so there are no brand tokens to inherit. */}
      <Route path={`/login/${ULTRA_SLUG}`} element={<UltraGateRoute />} />
      <Route path="/login/:slug" element={<ClientGateRoute />} />
      <Route path="/login" element={<Navigate to={`/login/${CLIENT_DOOR_SLUG}`} replace />} />

      {/* The signed-in application. Mounts only once a client is resolved. */}
      <Route element={<ProtectedShell />}>
        <Route path="/patient" element={<RouteSuspense><RainPatientView /></RouteSuspense>} />
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
    // runs first, so an `?access=` unlock can drop the stored client id before
    // ClientProvider reads it — which is what makes the admin key land on the
    // picker rather than resuming whichever client was open last.
    //
    // BrowserRouter sits above BOTH. It used to mount inside the app, after the
    // gates had already passed, which meant the sign-in screen and the picker
    // had no URLs at all — they could not, there was no router above them. Per-
    // client sign-in needs `/login/<slug>` to be a real address, so the router
    // moved to the top and the gates became routes.
    <BrowserRouter>
      <SessionProvider>
        <ClientProvider>
          <AppRoutes />
        </ClientProvider>
      </SessionProvider>
    </BrowserRouter>
  );
}

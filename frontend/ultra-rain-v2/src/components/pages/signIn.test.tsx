/**
 * The sign-in door, driven through App's real routes: RAIN's own door at
 * `/login/<slug>`, its direct link, the admin access key, and where unknown or
 * bare paths land. This build serves one tenant, so there is no platform door
 * and no market picker; every path that needs a door ends at RAIN's.
 *
 * Every credential comes from `config/access.ts` (demo values that ship in the
 * bundle). The signed-in shell and its pages are stubbed: these tests are about
 * which door opens and into which scope, not about what the app draws inside.
 */
import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MotionGlobalConfig } from 'framer-motion';
import App from '@/App';
import { CLIENT_CREDENTIALS, ADMIN_ACCESS_KEY, LOGIN_PATH, RAIN_CLIENT_ID } from '@/config/access';
import { CLIENTS } from '@/config/clients';
import { STORAGE_KEYS } from '@core/contract/storageKeys';

vi.mock('@/components/layout/AppShell', async () => {
  const { Outlet } = await import('react-router-dom');
  const { useClient } = await import('@/context/ClientContext');
  return {
    default: function ShellStub() {
      const { clientId } = useClient();
      return (
        <div data-testid="app-shell" data-client={clientId}>
          <Outlet />
        </div>
      );
    },
  };
});
const { page } = vi.hoisted(() => ({
  page: (name: string) => ({ default: () => <p>{name} page</p> }),
}));
vi.mock('@/components/pages/AskTheAI', () => page('ask'));
vi.mock('@/components/pages/DataSources', () => page('data sources'));

const RAIN = CLIENT_CREDENTIALS[RAIN_CLIENT_ID];
const client = CLIENTS.rain;

beforeAll(() => {
  MotionGlobalConfig.skipAnimations = true;
});

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
});

afterEach(() => {
  vi.useRealTimers();
});

/** Open the app at `path`, as a fresh tab would. */
function open(path: string) {
  window.history.replaceState({}, '', path);
  return render(<App />);
}

/** Fill the visible sign-in form and wait out its deliberate delay. */
function signIn(username: string, password: string) {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: username } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
  act(() => {
    vi.advanceTimersByTime(400);
  });
}

const scope = () => sessionStorage.getItem(STORAGE_KEYS.session);
const path = () => window.location.pathname;

describe('the door: /login/<slug>', () => {
  it('carries the client name, tagline and logo', () => {
    const { container } = open(`/login/${RAIN.slug}`);
    const heading = screen.getByRole('heading', { level: 1 });
    for (const line of client.nameLines?.length ? client.nameLines : [client.name]) {
      expect(heading).toHaveTextContent(line);
    }
    expect(heading).not.toHaveTextContent('Ultra App');
    expect(screen.getByText(client.tagline)).toBeInTheDocument();
    expect(container.querySelector(`img[src="${client.logo}"]`)).not.toBeNull();
  });

  it('a slug is matched case-insensitively', () => {
    open(`/login/${RAIN.slug.toUpperCase()}`);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(client.nameLines[0]);
  });

  it('a wrong password shows an error and does not sign in', () => {
    open(`/login/${RAIN.slug}`);
    signIn(RAIN.slug, `${RAIN.password}x`);
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid username or password.');
    expect(scope()).toBeNull();
    expect(path()).toBe(`/login/${RAIN.slug}`);
    expect(screen.queryByTestId('app-shell')).toBeNull();
  });

  it('a wrong username does not sign in', () => {
    open(`/login/${RAIN.slug}`);
    signIn('someone-else', RAIN.password);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(scope()).toBeNull();
  });

  it('the right credential signs in and lands on the briefing', () => {
    open(`/login/${RAIN.slug}`);
    signIn(`  ${RAIN.slug.toUpperCase()} `, RAIN.password);
    expect(scope()).toBe(RAIN_CLIENT_ID);
    expect(path()).toBe('/ask');
    expect(screen.getByTestId('app-shell')).toHaveAttribute('data-client', RAIN_CLIENT_ID);
    expect(screen.getByText('ask page')).toBeInTheDocument();
  });

  it('a stored client id from elsewhere does not move the session', () => {
    localStorage.setItem(STORAGE_KEYS.selectedClient, 'some_other_tenant');
    open(`/login/${RAIN.slug}`);
    signIn(RAIN.slug, RAIN.password);
    expect(screen.getByTestId('app-shell')).toHaveAttribute('data-client', RAIN_CLIENT_ID);
  });

  it('a session already signed in skips the form', () => {
    sessionStorage.setItem(STORAGE_KEYS.session, RAIN_CLIENT_ID);
    open(`/login/${RAIN.slug}`);
    expect(path()).toBe('/ask');
    expect(screen.getByTestId('app-shell')).toHaveAttribute('data-client', RAIN_CLIENT_ID);
  });

  it('the direct link opens the tenant and strips the token', () => {
    open(`/login/${RAIN.slug}?access=${encodeURIComponent(RAIN.password)}`);
    expect(scope()).toBe(RAIN_CLIENT_ID);
    expect(path()).toBe('/ask');
    expect(window.location.search).not.toContain('access');
  });

  it('a wrong token in the direct link does not open it', () => {
    open(`/login/${RAIN.slug}?access=not-it`);
    expect(scope()).toBeNull();
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
  });

  it('the admin access key opens the tenant from any route', () => {
    open(`/ask?access=${encodeURIComponent(ADMIN_ACCESS_KEY)}`);
    expect(scope()).toBe(RAIN_CLIENT_ID);
    expect(path()).toBe('/ask');
    expect(window.location.search).not.toContain('access');
  });
});

describe('where other paths go', () => {
  it('an unknown slug falls back to the door', () => {
    open('/login/no-such-client');
    expect(path()).toBe(LOGIN_PATH);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(client.nameLines[0]);
  });

  it('bare /login goes to the door', () => {
    open('/login');
    expect(path()).toBe(LOGIN_PATH);
  });

  it('a locked visitor to an app route is sent to the door', () => {
    open('/ask');
    expect(path()).toBe(LOGIN_PATH);
    expect(screen.queryByTestId('app-shell')).toBeNull();
  });

  it('a signed-in visitor to an unknown app route lands on the briefing', () => {
    sessionStorage.setItem(STORAGE_KEYS.session, RAIN_CLIENT_ID);
    open('/no-such-page');
    expect(path()).toBe('/ask');
  });
});

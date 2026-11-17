import { describe, it, expect } from 'vitest';
import {
  verifyClientLogin,
  clientIdForSlug,
  slugForClientId,
  loginPathForClientId,
  clientIdForAccessLink,
  directAccessUrl,
  CLIENT_CREDENTIALS,
  ADMIN_ACCESS_KEY,
  RAIN_CLIENT_ID,
  LOGIN_PATH,
} from './access';
import { CLIENTS } from './clients';

describe('ADMIN_ACCESS_KEY', () => {
  it('is a non-empty token', () => {
    expect(typeof ADMIN_ACCESS_KEY).toBe('string');
    expect(ADMIN_ACCESS_KEY.length).toBeGreaterThan(0);
  });
});

// `clients.js` is untyped JS, so TS infers a literal object with no index
// signature. The test iterates it by key, which is exactly what a
// registry-completeness check has to do.
const CLIENT_REGISTRY = CLIENTS as Record<string, { loginSlug: string }>;
const CLIENT_IDS = Object.keys(CLIENT_REGISTRY);

/**
 * The registry-completeness checks: they catch registering a client and
 * forgetting its front door.
 */
describe('CLIENT_CREDENTIALS covers the client registry', () => {
  it.each(CLIENT_IDS)('%s has a credential', (id) => {
    expect(CLIENT_CREDENTIALS[id]).toBeDefined();
    expect(CLIENT_CREDENTIALS[id].slug.length).toBeGreaterThan(0);
    expect(CLIENT_CREDENTIALS[id].password.length).toBeGreaterThan(0);
  });

  it('has no credential for a client that does not exist', () => {
    Object.keys(CLIENT_CREDENTIALS).forEach((id) => {
      expect(CLIENT_IDS).toContain(id);
    });
  });

  it('agrees with the loginSlug declared on each client', () => {
    CLIENT_IDS.forEach((id) => {
      expect(CLIENT_REGISTRY[id].loginSlug).toBe(CLIENT_CREDENTIALS[id].slug);
    });
  });

  it('is URL-safe — a slug goes in a path, so it cannot carry a & or a space', () => {
    CLIENT_IDS.forEach((id) => {
      expect(CLIENT_CREDENTIALS[id].slug).toMatch(/^[a-z0-9-]+$/);
    });
  });

  it('serves exactly one tenant, through /login/rain', () => {
    expect(CLIENT_IDS).toEqual([RAIN_CLIENT_ID]);
    expect(LOGIN_PATH).toBe('/login/rain');
  });
});

describe('verifyClientLogin', () => {
  it.each(CLIENT_IDS)('accepts %s own credential', (id) => {
    const { slug, password } = CLIENT_CREDENTIALS[id];
    expect(verifyClientLogin(id, slug, password)).toBe(true);
  });

  it('is case-insensitive on the username and tolerates surrounding space', () => {
    expect(verifyClientLogin('rain', '  RAIN  ', CLIENT_CREDENTIALS.rain.password)).toBe(true);
  });

  it('is case-sensitive on the password', () => {
    const { slug, password } = CLIENT_CREDENTIALS.rain;
    expect(verifyClientLogin('rain', slug, password.toUpperCase())).toBe(false);
  });

  it('rejects a wrong password and the access token typed as a password', () => {
    expect(verifyClientLogin('rain', 'rain', 'wrong')).toBe(false);
    expect(verifyClientLogin('rain', 'rain', ADMIN_ACCESS_KEY)).toBe(false);
  });

  it('fails closed on an unknown client, empty input and non-strings', () => {
    expect(verifyClientLogin('nope', 'nope', 'nope@9705')).toBe(false);
    expect(verifyClientLogin('rain', '', '')).toBe(false);
    expect(verifyClientLogin('rain', undefined as unknown as string, 'x')).toBe(false);
    expect(verifyClientLogin('rain', 'rain', null as unknown as string)).toBe(false);
  });
});

describe('slug helpers', () => {
  it('round-trips every client id through its slug', () => {
    CLIENT_IDS.forEach((id) => {
      expect(clientIdForSlug(slugForClientId(id) as string)).toBe(id);
    });
  });

  it('returns null for anything unknown', () => {
    expect(clientIdForSlug('ultra')).toBeNull();
    expect(clientIdForSlug('nonsense')).toBeNull();
    expect(clientIdForSlug(undefined as unknown as string)).toBeNull();
    expect(slugForClientId('nope')).toBeNull();
  });

  it('builds a login path, falling back to the one door', () => {
    expect(loginPathForClientId('rain')).toBe('/login/rain');
    expect(loginPathForClientId(null)).toBe('/login/rain');
    expect(loginPathForClientId('nope')).toBe('/login/rain');
  });
});

describe('clientIdForAccessLink', () => {
  it("opens the client door with the client's own password", () => {
    for (const [clientId, { slug, password }] of Object.entries(CLIENT_CREDENTIALS)) {
      expect(clientIdForAccessLink(`/login/${slug}`, password)).toBe(clientId);
      expect(clientIdForAccessLink(`/login/${slug}/`, password)).toBe(clientId);
    }
  });

  it('does not open the client door with the admin key (that works on any route instead)', () => {
    for (const { slug } of Object.values(CLIENT_CREDENTIALS)) {
      expect(clientIdForAccessLink(`/login/${slug}`, ADMIN_ACCESS_KEY)).toBeNull();
    }
  });

  it('refuses a wrong token, other paths and non-strings', () => {
    expect(clientIdForAccessLink('/login/rain', 'nope')).toBeNull();
    expect(clientIdForAccessLink('/login/rain', '')).toBeNull();
    expect(clientIdForAccessLink('/login/rain', null)).toBeNull();
    expect(clientIdForAccessLink('/login/unknown', 'unknown@9705')).toBeNull();
    expect(clientIdForAccessLink('/ask', 'rain@9705')).toBeNull();
  });
});

describe('directAccessUrl', () => {
  it('builds a link that opens its own client', () => {
    const url = new URL(directAccessUrl('rain', 'http://localhost:5550')!);
    expect(clientIdForAccessLink(url.pathname, url.searchParams.get('access'))).toBe('rain');
    expect(directAccessUrl('rain', 'http://localhost:5550')).toBe(
      'http://localhost:5550/login/rain/?access=rain@9705',
    );
  });

  it('returns null for an unknown client', () => {
    expect(directAccessUrl('nobody', 'https://x')).toBeNull();
  });
});

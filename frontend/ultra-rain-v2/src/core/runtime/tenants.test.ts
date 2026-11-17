/**
 * The tenant list is complete.
 *
 * Rule 9 (shared code names no client) is enforced by lint and counted by the
 * standard audit, and both read their client names and tenant folders from
 * `tenants.config.json`. A client the list does not name would pass both
 * silently, so this test ties the list to the registry and the folders on
 * disk: a new client or component folder fails here until it is listed. It
 * also holds the component layout: folders are named for a purpose, never a
 * client, and every client-owned component sits in a folder with an owner.
 * `npm run scaffold:client` adds the entries itself.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { getMarkets } from './registry';

interface TenantsConfig {
  clientNames: string[];
  tenantFolders: string[];
  componentOwners: Record<string, string>;
  sharedComponentFolders: string[];
  otherComponentFolders: Record<string, string>;
}

// Vitest runs from app/ (the jsdom environment has no file: import.meta.url).
const APP = process.cwd();
const config: TenantsConfig = JSON.parse(readFileSync(join(APP, 'tenants.config.json'), 'utf8'));
const src = (p: string) => join(APP, 'src', p);
const folders = (p: string) => readdirSync(src(p)).filter((n) => statSync(src(`${p}/${n}`)).isDirectory());
const clients = getMarkets().flatMap((m) => m.clients);
const named = (id: string) => config.clientNames.some((n) => id === n || id.startsWith(`${n}_`));

describe('tenants.config.json', () => {
  it('names every registered client', () => {
    for (const c of clients) {
      expect(named(c.id), `client "${c.id}" is not in clientNames: shared code could name it unnoticed`).toBe(true);
    }
  });

  it('names no client that is not registered', () => {
    for (const n of config.clientNames) {
      expect(clients.some((c) => c.id === n || c.id.startsWith(`${n}_`)), `clientNames has "${n}", which no registered client matches`).toBe(true);
    }
  });

  const domainFolders = [...new Set(Object.keys(config.componentOwners).map((d) => d.split('/')[0]))];

  it('places every folder under src/components in exactly one list', () => {
    const lists = [config.sharedComponentFolders, domainFolders, Object.keys(config.otherComponentFolders)];
    for (const dir of folders('components')) {
      const n = lists.filter((l) => l.includes(dir)).length;
      expect(n, `src/components/${dir} must be a shared folder, a purpose folder with an owner in componentOwners, or an other folder (found in ${n})`).toBe(1);
    }
  });

  it('names no folder under src/components after a client: components are filed by purpose', () => {
    const clientWords = new Set([...config.clientNames, ...config.tenantFolders, ...clients.map((c) => c.id), ...clients.map((c) => c.id.replace(/_/g, '-'))].map((w) => w.toLowerCase()));
    const bad: string[] = [];
    const walk = (p: string) => {
      for (const n of folders(p)) {
        if (clientWords.has(n.toLowerCase())) bad.push(`${p}/${n}`);
        walk(`${p}/${n}`);
      }
    };
    walk('components');
    expect(bad).toEqual([]);
  });

  it('gives every client-owned component a registered owner, and every file in a purpose folder an owner', () => {
    const ids = new Set(clients.map((c) => c.id));
    for (const [dir, owner] of Object.entries(config.componentOwners)) {
      expect(existsSync(src(`components/${dir}`)), `componentOwners: src/components/${dir} does not exist`).toBe(true);
      expect(ids.has(owner), `componentOwners: "${owner}" (for ${dir}) is not a registered client id`).toBe(true);
    }
    const owned = Object.keys(config.componentOwners);
    const unowned: string[] = [];
    const walk = (p: string) => {
      for (const n of readdirSync(src(p))) {
        const rel = `${p}/${n}`.replace(/^components\//, '');
        if (statSync(src(`${p}/${n}`)).isDirectory()) walk(`${p}/${n}`);
        else if (!owned.some((d) => rel.startsWith(`${d}/`))) unowned.push(rel);
      }
    };
    for (const top of domainFolders) walk(`components/${top}`);
    expect(unowned, 'files in a purpose folder that no componentOwners entry covers').toEqual([]);
  });

  it('lists only folders that exist', () => {
    for (const dir of config.tenantFolders) {
      expect(existsSync(src(`data/${dir}`)), `tenant folder "${dir}" does not exist in src/data`).toBe(true);
    }
    for (const dir of [...config.sharedComponentFolders, ...Object.keys(config.otherComponentFolders)]) {
      expect(existsSync(src(`components/${dir}`)), `src/components/${dir} does not exist`).toBe(true);
    }
  });
});

/**
 * The two layout rules. Every component lives in src/components; src/data
 * holds exactly one folder per registered client (its id with '_' as '-') and
 * nothing else, and that folder holds data, not UI.
 */
describe('layout: one data folder per client, every component in src/components', () => {
  const walk = (p: string): string[] =>
    readdirSync(src(p)).flatMap((n) => (statSync(src(`${p}/${n}`)).isDirectory() ? walk(`${p}/${n}`) : [`${p}/${n}`]));
  const isTest = (f: string) => /\.test\.[jt]sx?$/.test(f);
  const code = (f: string) => /\.(m?js|jsx|tsx?)$/.test(f);
  const dataFolderOf = (id: string) => id.replace(/_/g, '-');

  it('gives src/data exactly one folder per registered client, and nothing else', () => {
    const expected = clients.map((c) => dataFolderOf(c.id)).sort();
    expect(folders('data').sort(), 'src/data folders vs registered clients').toEqual(expected);
    const loose = readdirSync(src('data')).filter((n) => n !== '.DS_Store' && !statSync(src(`data/${n}`)).isDirectory());
    expect(loose, 'files at the top of src/data (each belongs in its client\'s folder)').toEqual([]);
    expect([...config.tenantFolders].sort(), 'tenants.config.json tenantFolders vs registered clients').toEqual(expected);
  });

  it('names each client\'s data folder after it, the same as its folder under src/markets', () => {
    for (const m of getMarkets()) {
      for (const c of m.clients) {
        const marketsDir = folders('markets').find((d) => existsSync(src(`markets/${d}/clients/${dataFolderOf(c.id)}`)));
        expect(marketsDir, `client "${c.id}" has no src/markets/*/clients/${dataFolderOf(c.id)} folder`).toBeDefined();
      }
    }
  });

  it('keeps UI out of src/data: no .jsx or .tsx outside tests, and no React', () => {
    const files = walk('data').filter((f) => code(f) && !isTest(f));
    expect(files.filter((f) => /\.(jsx|tsx)$/.test(f)), 'component files in src/data (they belong in src/components)').toEqual([]);
    expect(files.filter((f) => /from ['"]react['"]/.test(readFileSync(src(f), 'utf8'))), 'src/data files importing React').toEqual([]);
  });

  it('keeps component files out of src/markets: no .jsx and no pages/ folders', () => {
    const files = walk('markets');
    expect(files.filter((f) => f.endsWith('.jsx')), '.jsx files in src/markets (components belong in src/components)').toEqual([]);
    expect(files.filter((f) => f.includes('/pages/')), 'pages/ folders in src/markets (page containers go in src/components/<purpose>/pages)').toEqual([]);
  });

  it('has no other folder for UI at the top of src', () => {
    const allowed = ['assets', 'components', 'config', 'context', 'core', 'data', 'demo', 'hooks', 'lib', 'markets', 'test', 'utils', 'vendor'];
    expect(folders('').filter((d) => !allowed.includes(d)), 'unexpected top-level folders in src (components go in src/components)').toEqual([]);
  });

  it('lets a component read only its own client\'s data folder, and a shared component none', () => {
    const owners = Object.entries(config.componentOwners).sort((a, b) => b[0].length - a[0].length);
    const bad: string[] = [];
    for (const f of walk('components').filter((p) => code(p) && !isTest(p))) {
      const rel = f.replace(/^components\//, '');
      const owner = owners.find(([dir]) => rel.startsWith(`${dir}/`))?.[1];
      for (const m of readFileSync(src(f), 'utf8').matchAll(/from\s+['"](?:@\/|(?:\.\.\/)+)data\/([^/'"]+)/g)) {
        if (!owner || dataFolderOf(owner) !== m[1]) bad.push(`${f} → data/${m[1]}${owner ? ` (owned by ${owner})` : ' (shared)'}`);
      }
    }
    expect(bad).toEqual([]);
  });
});

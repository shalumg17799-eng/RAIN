/**
 * The tenant list is complete.
 *
 * Rule 9 (shared code names no client) is enforced by lint and counted by the
 * standard audit, and both read their client names and tenant folders from
 * `tenants.config.json`. A client the list does not name would pass both
 * silently, so this test ties the list to the registry and the folders on
 * disk: a new client or component folder fails here until it is listed.
 * `npm run scaffold:client` adds the entries itself.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { getMarkets } from './registry';

interface TenantsConfig {
  clientNames: string[];
  platformClients: Record<string, string>;
  tenantFolders: string[];
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
  it('names every registered client (or lists it as a platform client, with a reason)', () => {
    for (const c of clients) {
      expect(named(c.id) || c.id in config.platformClients, `client "${c.id}" is not in clientNames: shared code could name it unnoticed`).toBe(true);
    }
  });

  it('names no client that is not registered', () => {
    for (const n of config.clientNames) {
      expect(clients.some((c) => c.id === n || c.id.startsWith(`${n}_`)), `clientNames has "${n}", which no registered client matches`).toBe(true);
    }
    for (const id of Object.keys(config.platformClients)) expect(clients.some((c) => c.id === id), `platform client "${id}" is not registered`).toBe(true);
  });

  it('places every folder under src/components in exactly one list', () => {
    const lists = [config.sharedComponentFolders, config.tenantFolders, Object.keys(config.otherComponentFolders)];
    for (const dir of folders('components')) {
      const n = lists.filter((l) => l.includes(dir)).length;
      expect(n, `src/components/${dir} must be in exactly one of sharedComponentFolders, tenantFolders, otherComponentFolders (found in ${n})`).toBe(1);
    }
  });

  it('lists only folders that exist', () => {
    for (const dir of config.tenantFolders) {
      expect(existsSync(src(`components/${dir}`)) || existsSync(src(`data/${dir}`)), `tenant folder "${dir}" exists in neither src/components nor src/data`).toBe(true);
    }
    for (const dir of [...config.sharedComponentFolders, ...Object.keys(config.otherComponentFolders)]) {
      expect(existsSync(src(`components/${dir}`)), `src/components/${dir} does not exist`).toBe(true);
    }
  });
});

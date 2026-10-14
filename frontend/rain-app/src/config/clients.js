/**
 * Compatibility shim.
 * The client config now lives in the registry (src/clients/registry.js), which
 * assembles everything from the per-client manifests in src/clients/<id>/.
 * This file re-exports the branding-related pieces so existing imports keep
 * working. Prefer importing from '@/clients/registry' in new code.
 */
export { CLIENTS, DEFAULT_CLIENT_ID, STORAGE_KEY } from '@/clients/registry';

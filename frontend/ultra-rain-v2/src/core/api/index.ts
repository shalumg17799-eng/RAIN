/**
 * The app's API client. One instance, chosen by environment:
 *
 *   VITE_ULTRA_API_MODE=recorded (default)  answers from the scripted manifests
 *   VITE_ULTRA_API_MODE=http                calls VITE_ULTRA_API_BASE
 *
 * Import this lazily (`await import('@core/api')`): the recorded adapter pulls
 * in the catalog and every manifest loader, which the main bundle must not
 * carry for demos that never switch modes.
 */
import { createRecordedApi } from './recorded';
import { createHttpApi } from './http';
import type { UltraApi } from './types';

export { API_MODE } from './mode';
export type * from './types';
export { ApiError } from './recorded';

let instance: UltraApi | null = null;

export function getApi(): UltraApi {
  if (!instance) {
    const base = import.meta.env.VITE_ULTRA_API_BASE as string | undefined;
    instance = import.meta.env.VITE_ULTRA_API_MODE === 'http' && base ? createHttpApi(base) : createRecordedApi();
  }
  return instance;
}

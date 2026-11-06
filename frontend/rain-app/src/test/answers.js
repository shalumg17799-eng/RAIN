/**
 * A persona's recorded answer for one message, as the elements the chat draws
 * (tests only). Bespoke types resolve directly; catalog types go through the
 * lazy, schema-checked renderer. `undefined` when the turn draws nothing, like
 * the workspace.
 */
import { indexBespoke } from '@core/catalog/bespokeContext';
import { bespokeElement, catalogElement } from '@core/catalog/resolve';

export function answerElements(manifest, msg) {
  const specs = manifest.answers?.(msg, manifest.signals ?? []);
  if (!specs?.length) return undefined;
  const index = indexBespoke(manifest.catalog);
  return specs.map((s, i) => bespokeElement(s, index, {}, i) ?? catalogElement(s, i));
}

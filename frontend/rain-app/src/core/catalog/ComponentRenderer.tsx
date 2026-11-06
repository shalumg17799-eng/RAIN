/**
 * ComponentRenderer — the one renderer (the Oct 21 contract).
 *
 * Draws an `AiTurn.components[]` list: resolves each `type` in the catalog,
 * validates its props against the published schema, adapts them for the
 * component, and draws it lazily inside an error boundary. A type the catalog
 * does not know is skipped; props that do not match the schema draw a small
 * notice instead of a broken card. Neither ever takes down the thread.
 */
import { Suspense, lazy, useContext, type ComponentType, type LazyExoticComponent } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { ComponentSpec } from '../contract/aiTurn';
import { devWarn } from '../log';
import { CATALOG, getCatalogEntry } from './registry';
import { CatalogActionsContext } from './catalogActions';
import VizErrorBoundary from '@/components/chat/VizErrorBoundary';
import { BespokeContext } from './bespokeContext';
import { bespokeElement } from './resolve';
import type { ContractSpec } from '../contract/spec';

// One lazy component per catalog type, made once at module load. Nothing is
// fetched until a type is first drawn; each type is its own chunk.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const LAZY: Record<string, LazyExoticComponent<ComponentType<any>>> = Object.fromEntries(
  CATALOG.map((e) => [e.type, lazy(e.load)]),
);

function InvalidProps({ type }: { type: string }) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-border bg-surface px-4 py-3" role="note">
      <AlertTriangle className="h-4 w-4 flex-shrink-0 text-text-subtle" aria-hidden="true" />
      <p className="text-xs font-semibold text-text-muted">This {type.replace(/_/g, ' ')} couldn&apos;t be shown: its data didn&apos;t match the catalog.</p>
    </div>
  );
}

function Placeholder() {
  return <div className="h-16 animate-pulse rounded-xl border border-border bg-surface-2" aria-hidden="true" />;
}

export function RenderSpec({ spec }: { spec: ComponentSpec }) {
  const actions = useContext(CatalogActionsContext);
  const own = bespokeElement(spec as ContractSpec, useContext(BespokeContext), actions);
  if (own) return own;
  const entry = getCatalogEntry(spec.type);
  if (!entry) {
    devWarn(`[ComponentRenderer] Unknown component type "${spec.type}" — skipped. Add it to core/catalog/registry.ts.`);
    return null;
  }
  if ((spec.version ?? 1) > entry.version) {
    devWarn(`[ComponentRenderer] "${spec.type}" v${spec.version} is newer than the catalog's v${entry.version}.`);
  }
  const parsed = entry.schema.safeParse(spec.props ?? {});
  if (!parsed.success) {
    devWarn(`[ComponentRenderer] "${spec.type}" props do not match the catalog schema:`, parsed.error.issues);
    return <InvalidProps type={spec.type} />;
  }
  const props = entry.adapt ? entry.adapt(parsed.data as Record<string, unknown>, actions) : (parsed.data as Record<string, unknown>);
  const Component = LAZY[spec.type];
  return (
    <VizErrorBoundary>
      <Suspense fallback={<Placeholder />}>
        <Component {...props} />
      </Suspense>
    </VizErrorBoundary>
  );
}

export interface ComponentRendererProps {
  components: ComponentSpec[] | undefined;
  /** Wrap each component (e.g. spacing in the chat column). Defaults to none. */
  className?: string;
}

export default function ComponentRenderer({ components, className }: ComponentRendererProps) {
  if (!components?.length) return null;
  const items = components.map((spec, i) => <RenderSpec key={`${spec.type}-${i}`} spec={spec} />);
  return className ? <div className={className}>{items}</div> : <>{items}</>;
}

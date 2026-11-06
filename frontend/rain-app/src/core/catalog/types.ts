/**
 * A catalog entry: everything the backend, the LLM and the renderer need to
 * know about one component type. See docs/standard/README.md §3.
 */
import type { ComponentType } from 'react';
import type { z } from 'zod';

/** 1 shell · 2 catalog (Gen UI) · 3 compose building block · 4 bespoke. */
export type Tier = 1 | 2 | 3 | 4;

/** What the renderer hands every component besides its props. */
export interface CatalogActions {
  /** Send a chip as if the user clicked it. */
  onChip?: (text: string) => void;
  /** Confirm an action card by id. */
  onAction?: (actionId: string) => void;
}

export interface CatalogEntry<P = Record<string, unknown>> {
  /** snake_case id the backend sends. */
  type: string;
  version: number;
  title: string;
  /** When to use it — the sentence the LLM reads. */
  description: string;
  tier: Tier;
  /** Props schema; exported as JSON Schema for the backend. */
  schema: z.ZodType<P>;
  /** A props payload that validates and renders (the gallery and contract tests use it). */
  example: P;
  /**
   * Lazy import of the component. Typed loosely on purpose: the schema, not the
   * component's own prop types, is the contract, and `adapt` bridges the two.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  load: () => Promise<{ default: ComponentType<any> }>;
  /**
   * Contract props → the component's props, for components that predate the
   * contract (a format function, a click handler, legacy key names). Omitted
   * when the contract props are the component props.
   */
  adapt?: (props: P, actions: CatalogActions) => Record<string, unknown>;
  /** Clients that use it today (informational). */
  tenants?: string[];
}

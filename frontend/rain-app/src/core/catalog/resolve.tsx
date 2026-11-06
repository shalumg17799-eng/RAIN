/**
 * Drawing a turn's answer: `components[]` → elements (the Oct 21 contract's
 * single renderer, on the chat path).
 *
 * A spec whose type is one of the persona's bespoke entries (tier 4) is drawn
 * here, synchronously — the component is already in the persona's chunk. Any
 * other type is a catalog type (tiers 2–3) and goes to the lazy catalog
 * renderer, which validates its props against the published schema. A spec may
 * nest specs under `props.children` (a section with a card inside it).
 *
 * Shell code: the workspace and the render nets both call `bespokeElement`, so
 * the nets fingerprint exactly what the chat draws.
 */
import type { ReactElement, ReactNode } from 'react';
import type { ContractSpec } from '../contract/spec';
import { isContractSpec } from '../contract/spec';
import type { CatalogActions } from './types';
import type { BespokeIndex } from './bespokeContext';
import AnswerSpec, { CatalogAnswer } from './answers';

/** Nested specs under `props.children` → elements; anything else passes through. */
function childrenOf(children: unknown, index: BespokeIndex, actions: CatalogActions): ReactNode {
  if (children === undefined) return undefined;
  const one = (c: unknown, key?: string | number): ReactNode =>
    isContractSpec(c) ? (bespokeElement(c, index, actions, key) ?? <CatalogAnswer key={key} spec={c} />) : (c as ReactNode);
  return Array.isArray(children) ? (children.length === 1 ? one(children[0]) : children.map((c, i) => one(c, i))) : one(children);
}

/** The element for a bespoke spec, or `null` when its type is not the persona's own. */
export function bespokeElement(spec: ContractSpec, index: BespokeIndex, actions: CatalogActions = {}, key?: string | number): ReactElement | null {
  const entry = index[spec.type];
  if (!entry) return null;
  const { children, ...rest } = spec.props ?? {};
  const props = entry.adapt ? entry.adapt(rest, actions) : rest;
  const kids = childrenOf(children, index, actions);
  const Component = entry.component;
  const own = entry.frame ? undefined : key;
  const el = kids === undefined ? <Component key={own} {...props} /> : <Component key={own} {...props}>{kids}</Component>;
  if (!entry.frame) return el;
  return entry.frame === true ? <div key={key}>{el}</div> : <div key={key} className={entry.frame}>{el}</div>;
}

/** A catalog-type spec as an element (lazy, schema-checked). */
export function catalogElement(spec: ContractSpec, key?: string | number): ReactElement {
  return <CatalogAnswer key={key} spec={spec} />;
}

/** A turn's specs as sibling elements, the way the chat column lists cards. */
export function answerNodes(specs: ContractSpec[] | undefined): ReactElement[] {
  return (specs ?? []).map((s, i) => <AnswerSpec key={`${s.type}-${i}`} spec={s} />);
}

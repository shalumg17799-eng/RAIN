/** One answer component, bespoke or catalog (see ./resolve). */
import { Suspense, lazy, useContext } from 'react';
import type { ContractSpec } from '../contract/spec';
import { BespokeContext } from './bespokeContext';
import { CatalogActionsContext } from './catalogActions';
import { bespokeElement, catalogElement } from './resolve';

const CatalogSpec = lazy(() => import('./ComponentRenderer').then((m) => ({ default: m.RenderSpec })));

/** A catalog-type spec: lazy, schema-checked (see ComponentRenderer). */
export function CatalogAnswer({ spec }: { spec: ContractSpec }) {
  return (
    <Suspense fallback={null}>
      <CatalogSpec spec={spec} />
    </Suspense>
  );
}

export default function AnswerSpec({ spec }: { spec: ContractSpec }) {
  const index = useContext(BespokeContext);
  const actions = useContext(CatalogActionsContext);
  return bespokeElement(spec, index, actions) ?? catalogElement(spec);
}

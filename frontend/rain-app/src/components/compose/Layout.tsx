/**
 * Tier 3 layout blocks: `stack` and `grid`. Their children are component specs
 * drawn through the catalog renderer, which is what makes compose recursive —
 * the AI can nest any catalog type inside a layout without new code.
 */
import type { ComponentSpec } from '@core/contract/aiTurn';
import ComponentRenderer from '@core/catalog/ComponentRenderer';

const GAP = { sm: 'gap-2', md: 'gap-3', lg: 'gap-5' } as const;

export interface StackProps {
  children: ComponentSpec[];
  gap?: keyof typeof GAP;
}

export function Stack({ children, gap = 'md' }: StackProps) {
  return (
    <div className={`flex flex-col ${GAP[gap]}`}>
      <ComponentRenderer components={children} />
    </div>
  );
}

const COLS = { 1: 'sm:grid-cols-1', 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3', 4: 'sm:grid-cols-2 lg:grid-cols-4' } as const;

export interface GridProps {
  children: ComponentSpec[];
  columns?: 1 | 2 | 3 | 4;
  gap?: keyof typeof GAP;
}

export function Grid({ children, columns = 2, gap = 'md' }: GridProps) {
  return (
    <div className={`grid grid-cols-1 ${COLS[columns]} ${GAP[gap]}`}>
      <ComponentRenderer components={children} />
    </div>
  );
}

import { useState } from 'react';
import type { CountyId } from '@/data/rain/_shared/constants';
import { COUNTIES, STATE, num } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { useRainState } from '../shell/store';
import type { MapLayer } from '../cards/state';
import { CountyMap, CountyTable } from '../cards/state';
import { usePaneContext } from './useWorkbench';

/**
 * County Explorer (P1): the county map with layer toggles (PLACES, SVI, HPSA,
 * broadband) beside the county table, aggregated and de-identified, small
 * cells suppressed. Clicking a county updates the Cockpit pane; when the
 * funding step runs, the targeted counties light up on the map.
 */
export default function CountyExplorer({ access }: { access: Access }) {
  const { targetCounties } = useRainState();
  const [county, setCounty] = useState<CountyId | null>(null);
  const [layer, setLayer] = useState<MapLayer>('ed');
  const c = COUNTIES.find((x) => x.id === county);
  usePaneContext(
    c
      ? { label: `${c.name} County`, chips: [`${c.name} County: what changed since January?`, 'Where should Outcomes Accelerator funds go first?'], kind: 'county', id: c.id }
      : { label: `County view: ${STATE.counties} rural counties, ${num(STATE.members)} members`, chips: ['Where should Outcomes Accelerator funds go first?', 'Show the trend since January'] },
  );
  return (
    <WorkbenchLayout meta={WORKBENCHES.countyExplorer} access={access} label="Aggregated, de-identified">
      <div className="grid gap-4 @5xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <CountyMap mode={targetCounties.length ? 'target' : 'layers'} layer={layer} onLayer={setLayer} selected={county} onSelect={setCounty} />
        <CountyTable selected={county} onSelect={setCounty} />
      </div>
      {targetCounties.length > 0 && (
        <p className="rounded-xl bg-brand/[0.06] px-3 py-2 text-[12.5px] text-text">
          Targeted for option A: {targetCounties.map((id) => COUNTIES.find((x) => x.id === id)?.name).join(' and ')}. Red dots mark the six low-broadband places for option C mobile clinic days.
        </p>
      )}
    </WorkbenchLayout>
  );
}

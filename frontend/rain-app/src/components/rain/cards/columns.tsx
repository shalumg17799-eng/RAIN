/** Column sets shared by the member tables in answers and workbenches. */
import type { CampaignMember } from '@/data/rain/_shared/records';
import { Pill } from '../shell/rainKit';

export const memberColumns = (opts: { cuff?: boolean; orders?: boolean; contact?: boolean } = {}) => {
  const cols = [
    { key: 'rank', label: '#', align: 'right' as const, render: (m: CampaignMember) => m.rank },
    { key: 'name', label: 'Member', render: (m: CampaignMember) => <span className="font-semibold">{m.name}</span> },
    { key: 'reasons', label: 'Top reasons', render: (m: CampaignMember) => <span className="text-[12px] text-text-muted">{m.reasons.join(' · ')}</span> },
    { key: 'likelihood', label: 'Likely to control', align: 'right' as const, render: (m: CampaignMember) => `${m.likelihood}%` },
    { key: 'mode', label: 'Visit mode', render: (m: CampaignMember) => <Pill tone={m.mode === 'Telehealth' ? 'brand' : 'neutral'}>{m.mode}</Pill> },
  ];
  if (opts.cuff) cols.push({ key: 'cuff', label: 'Cuff', render: (m: CampaignMember) => (m.cuff === 'Ship first' ? <Pill tone="warning">Ship first</Pill> : <span className="text-[12px] text-text-muted">{m.cuff}</span>) });
  if (opts.orders) cols.push({ key: 'order', label: 'Standing order', render: (m: CampaignMember) => <span className="text-[12px] text-text-muted">{m.standingOrder}</span> });
  return cols;
};


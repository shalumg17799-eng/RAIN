import { useState } from 'react';
import { PenLine, ShieldCheck } from 'lucide-react';
import { MODEL } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import { FEATURES } from '@/data/rain/_shared/records';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { Button, Pill, RainCard } from '../shell/rainKit';
import { isReleased, sign, useRainState } from '../shell/store';
import { BeforeAfter, DriveScatter, FeatureTable, ModelCard, SubgroupBars, SwapTable } from '../cards/governance';
import { CountyMap } from '../cards/state';
import { usePaneContext } from './useWorkbench';

/**
 * Model Governance (P1): model card, subgroup check, feature list, before and
 * after, and sign-off. The CIO signs; the CMO co-signs here. Steps 3 and 4 of
 * the CIO's conversation update this screen as the pane runs them.
 */
export default function ModelGovernance({ access }: { access: Access }) {
  const store = useRainState();
  const [feature, setFeature] = useState<string | null>(null);
  const f = FEATURES.find((x) => x.id === feature);
  const released = isReleased(store);
  usePaneContext(
    f
      ? { label: `Feature: ${f.name}`, chips: ['Explain this feature', 'What changes if we fix it?'], kind: 'feature', id: f.id }
      : { label: store.fixPreview ? `Subgroup check: ${MODEL.frontierGapPct}% to ${MODEL.frontierGapAfterPct}% after the fix` : `Subgroup check: frontier gap ${MODEL.frontierGapPct}%`, chips: ['What changes if we fix it?', 'Which features cause it?', 'Explain this feature'] },
  );
  const cosign = access === 'cosign';
  return (
    <WorkbenchLayout
      meta={WORKBENCHES.modelGovernance}
      access={access}
      actions={
        released ? (
          <Pill tone="good">
            <ShieldCheck className="h-3 w-3" aria-hidden="true" /> {MODEL.candidate} released
          </Pill>
        ) : cosign ? (
          <Button variant="primary" disabled={!store.signed.cio || store.signed.cmo} title={!store.signed.cio ? 'Waits for the CIO to sign first' : undefined} onClick={() => sign('cmo')}>
            <PenLine className="h-3.5 w-3.5" aria-hidden="true" /> {store.signed.cmo ? 'Co-signed' : 'Co-sign release'}
          </Button>
        ) : (
          <Button variant="primary" disabled={!store.fixPreview || store.signed.cio} title={!store.fixPreview ? 'Preview the access-adjusted model first' : undefined} onClick={() => sign('cio')}>
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> {store.signed.cio ? 'Signed by CIO' : 'Sign off'}
          </Button>
        )
      }
    >
      {cosign && !released && (
        <p className="rounded-xl border border-border bg-surface-2/60 px-3 py-2 text-[12.5px] text-text-muted">
          {store.signed.cio ? 'Raj Malhotra has signed the governance packet. Your co-sign releases the access-adjusted ranking to the care team.' : store.cosignRequested ? 'Co-sign requested. It opens once the CIO signs.' : 'Co-sign opens once the CIO signs the governance packet.'}
        </p>
      )}
      <div className="grid gap-4 @4xl:grid-cols-2">
        <ModelCard />
        <SubgroupBars />
      </div>
      <div className="grid gap-4 @4xl:grid-cols-2">
        <FeatureTable selected={feature} onSelect={(x) => setFeature(x.id)} />
        <DriveScatter />
      </div>
      {store.fixPreview || released ? (
        <div className="grid gap-4 @4xl:grid-cols-2">
          <BeforeAfter />
          <SwapTable />
        </div>
      ) : (
        <RainCard eyebrow="Before and after" title="Run the access-adjusted preview">
          <p className="text-[13px] text-text-muted">Ask “What changes if we fix it?” in the Ask AI pane to preview {MODEL.candidate} with drive time, broadband, missed appointments and shortage-area status added.</p>
        </RainCard>
      )}
      <CountyMap mode="frontier" />
    </WorkbenchLayout>
  );
}

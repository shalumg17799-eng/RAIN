/**
 * /agent-inventory — the standing view of an AI governance registry.
 *
 * Only a persona that declares `pages.agentInventory` has one (today the NFCU
 * AI Governance Admin); a hand-typed URL by anyone else gets the notice rather
 * than an empty page.
 */
import { usePersonaPage } from '@core/runtime/usePersonaPage';

export default function AgentInventory() {
  const { ready, Page } = usePersonaPage('agentInventory');
  if (!ready) return null;
  if (Page) return <Page />;
  return (
    <div className="flex items-center justify-center h-full text-text-muted text-sm">
      Agent Inventory is available for the AI Governance Admin only.
    </div>
  );
}

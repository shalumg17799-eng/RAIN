/**
 * /agent-observability — Agent Observability.
 *
 * Two consoles share the route because both answer "is the AI fleet healthy?"
 * — but they watch different fleets over data shapes with nothing in common,
 * so each persona declares its own in `pages.agentObservability` (the NFCU
 * platform admin's gateway/SLM/KAG fleet; the AT&T platform admin's four
 * billing-pipeline agents). A hand-typed URL by anyone else gets the notice.
 */
import { usePersonaPage } from '@core/runtime/usePersonaPage';

export default function AgentObservability() {
  const { ready, Page } = usePersonaPage('agentObservability');
  if (!ready) return null;
  if (Page) return <Page />;
  return (
    <div className="flex items-center justify-center h-full text-text-muted text-sm">
      Agent Observability is available for the AI Governance Admin only.
    </div>
  );
}

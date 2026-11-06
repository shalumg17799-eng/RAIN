/**
 * /governance — Governance.
 *
 * A persona with a governance surface declares it in its manifest's
 * `pages.governance` (NFCU's model governance per persona, the NFCU platform
 * admin's sovereignty and tokenomics view); for everyone else the route says
 * the page is not available. No persona or client is named here.
 */
import { usePersonaPage } from '@core/runtime/usePersonaPage';

export default function Governance() {
  const { ready, Page } = usePersonaPage('governance');
  if (!ready) return null;
  if (Page) return <Page />;
  return (
    <div className="flex items-center justify-center h-full text-text-muted text-sm">
      Model Governance is not available for the active persona.
    </div>
  );
}

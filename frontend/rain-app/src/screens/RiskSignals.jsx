/**
 * /risk — the Risk Signals page.
 *
 * A persona that has its own version of this page declares it in its
 * manifest's `pages.risk` (executive signal views, governance signals, quality
 * signals, disclosure calendars…); everyone else gets the generic two-column
 * risk view. No persona or client is named here.
 */
import RiskSignalsTable from '@/components/tables/RiskSignalsTable';
import { AMLClustersCard, CreditRiskCard, RegulatoryReadinessCard } from '@/components/cards/RiskSignalCard';
import ComplaintTrajectory from '@/components/charts/ComplaintTrajectory';
import SignalsColumnsPage from '@/components/layout/SignalsColumnsPage';
import riskExtras from '@/data/riskScreenExtras.json';
import riskSignals from '@/data/risk_signals.json';
import { usePersonaPage } from '@core/runtime/usePersonaPage';

export default function RiskSignals() {
  const { ready, Page } = usePersonaPage('risk');
  if (!ready) return null;
  if (Page) return <Page />;
  return (
    <SignalsColumnsPage
      leftLabel="Active Risk Signals"
      rightLabel="Forward-Looking Summary"
      left={(
        <>
          <RiskSignalsTable riskSignals={riskSignals} />
          <AMLClustersCard riskSignals={riskSignals} />
        </>
      )}
      right={(
        <>
          <CreditRiskCard riskExtras={riskExtras} />
          <RegulatoryReadinessCard riskExtras={riskExtras} />
          <ComplaintTrajectory riskExtras={riskExtras} />
        </>
      )}
      chips={riskExtras.riskScreenChips}
      placeholder="Ask about risk signals..."
    />
  );
}

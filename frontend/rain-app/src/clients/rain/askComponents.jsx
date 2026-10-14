/** RAIN personas' inline component maps for AskTheAI (rendered in the chat thread). */
import SignalCard from '@/components/cards/SignalCard';
import MaternalRiskStratification from '@/clients/rain/components/delgado/MaternalRiskStratification';
import NevadaAccessMap from '@/clients/rain/components/delgado/NevadaAccessMap';
import TelehealthScenarioModel from '@/clients/rain/components/delgado/TelehealthScenarioModel';
import MaternalOutreachPreview from '@/clients/rain/components/delgado/MaternalOutreachPreview';
import DeteriorationBoard from '@/clients/rain/components/whitehorse/DeteriorationBoard';
import RiskTieredOutreach from '@/clients/rain/components/whitehorse/RiskTieredOutreach';
import Tier1ActionPackage from '@/clients/rain/components/whitehorse/Tier1ActionPackage';
import OpsTrafficLightTiles from '@/clients/rain/components/tomley/OpsTrafficLightTiles';
import TransportQueueTimeline from '@/clients/rain/components/tomley/TransportQueueTimeline';
import TripTelehealthConversion from '@/clients/rain/components/tomley/TripTelehealthConversion';
import OperationsPlanPreview from '@/clients/rain/components/tomley/OperationsPlanPreview';
import CascadeDiagram from '@/clients/rain/components/nair/CascadeDiagram';
import NevadaCountyChoropleth from '@/clients/rain/components/nair/NevadaCountyChoropleth';
import InterventionComparison from '@/clients/rain/components/nair/InterventionComparison';
import EquityBriefPreview from '@/clients/rain/components/nair/EquityBriefPreview';
import DataHealthBoard from '@/clients/rain/components/yazzie/DataHealthBoard';
import ReconciliationBreakdown from '@/clients/rain/components/yazzie/ReconciliationBreakdown';
import DownstreamImpactMap from '@/clients/rain/components/yazzie/DownstreamImpactMap';
import RemediationPlanPreview from '@/clients/rain/components/yazzie/RemediationPlanPreview';

// Helper: prepend the matching SignalCard for a signal walkthrough.
const withSignal = (components, signals, id, key) => {
  const sig = signals.find((s) => s.id === id);
  if (sig) components.push(<SignalCard key={key} signal={sig} />);
};

export const rainInlineComponents = {
  rain_delgado: (msg, signals) => {
    const c = [];
    if (msg.flowKey === 'turn_1_cohort') {
      withSignal(c, signals, 'SIG-RAIN-DELGADO-001', 'delgado-sig1');
      c.push(<NevadaAccessMap key="delgado-map" />);
      c.push(<MaternalRiskStratification key="delgado-strat" />);
    }
    if (msg.flowKey === 'signal_prenatal_gap') withSignal(c, signals, 'SIG-RAIN-DELGADO-002', 'delgado-sig2');
    if (msg.flowKey === 'signal_ed_delivery') withSignal(c, signals, 'SIG-RAIN-DELGADO-003', 'delgado-sig3');
    if (msg.flowKey === 'turn_2_telehealth') c.push(<TelehealthScenarioModel key="delgado-telehealth" />);
    if (msg.flowKey === 'turn_3_outreach') c.push(<MaternalOutreachPreview key="delgado-outreach" />);
    return c.length ? c : undefined;
  },
  rain_whitehorse: (msg, signals) => {
    const c = [];
    if (msg.flowKey === 'turn_1_cluster') {
      withSignal(c, signals, 'SIG-RAIN-WHITEHORSE-001', 'wh-sig1');
      c.push(<DeteriorationBoard key="wh-board" />);
    }
    if (msg.flowKey === 'signal_diabetes') withSignal(c, signals, 'SIG-RAIN-WHITEHORSE-002', 'wh-sig2');
    if (msg.flowKey === 'signal_hypertension') withSignal(c, signals, 'SIG-RAIN-WHITEHORSE-003', 'wh-sig3');
    if (msg.flowKey === 'turn_2_outreach') c.push(<RiskTieredOutreach key="wh-tiers" />);
    if (msg.flowKey === 'turn_3_activate') c.push(<Tier1ActionPackage key="wh-actions" />);
    return c.length ? c : undefined;
  },
  rain_tomley: (msg, signals) => {
    const c = [];
    if (msg.flowKey === 'turn_1_queue') {
      withSignal(c, signals, 'SIG-RAIN-TOMLEY-001', 'tom-sig1');
      c.push(<OpsTrafficLightTiles key="tom-tiles" />);
      c.push(<TransportQueueTimeline key="tom-timeline" />);
    }
    if (msg.flowKey === 'signal_telehealth_capacity') withSignal(c, signals, 'SIG-RAIN-TOMLEY-002', 'tom-sig2');
    if (msg.flowKey === 'signal_ems') withSignal(c, signals, 'SIG-RAIN-TOMLEY-003', 'tom-sig3');
    if (msg.flowKey === 'turn_2_telehealth') c.push(<TripTelehealthConversion key="tom-convert" />);
    if (msg.flowKey === 'turn_3_plan') c.push(<OperationsPlanPreview key="tom-plan" />);
    return c.length ? c : undefined;
  },
  rain_nair: (msg, signals) => {
    const c = [];
    if (msg.flowKey === 'turn_1_cascade') {
      withSignal(c, signals, 'SIG-RAIN-NAIR-001', 'nair-sig1');
      c.push(<CascadeDiagram key="nair-cascade" />);
      c.push(<NevadaCountyChoropleth key="nair-choropleth" />);
    }
    if (msg.flowKey === 'signal_ed') withSignal(c, signals, 'SIG-RAIN-NAIR-002', 'nair-sig2');
    if (msg.flowKey === 'signal_telehealth_equity') withSignal(c, signals, 'SIG-RAIN-NAIR-003', 'nair-sig3');
    if (msg.flowKey === 'turn_2_target') c.push(<InterventionComparison key="nair-options" />);
    if (msg.flowKey === 'turn_3_brief') c.push(<EquityBriefPreview key="nair-brief" />);
    return c.length ? c : undefined;
  },
  rain_yazzie: (msg, signals) => {
    const c = [];
    if (msg.flowKey === 'turn_1_reconciliation') {
      withSignal(c, signals, 'SIG-RAIN-YAZZIE-001', 'yaz-sig1');
      c.push(<DataHealthBoard key="yaz-health" />);
      c.push(<ReconciliationBreakdown key="yaz-recon" />);
    }
    if (msg.flowKey === 'signal_rpm_gap') withSignal(c, signals, 'SIG-RAIN-YAZZIE-002', 'yaz-sig2');
    if (msg.flowKey === 'signal_fhir') withSignal(c, signals, 'SIG-RAIN-YAZZIE-003', 'yaz-sig3');
    if (msg.flowKey === 'turn_2_downstream') c.push(<DownstreamImpactMap key="yaz-downstream" />);
    if (msg.flowKey === 'turn_3_remediation') c.push(<RemediationPlanPreview key="yaz-remediation" />);
    return c.length ? c : undefined;
  },
};

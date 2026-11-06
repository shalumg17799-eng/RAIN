// ─── Risk & Fraud Executive (James R.) ──────────────────────────
import riskChatFlows from '../risk/chatFlows.json';

const riskConfig = {
  chatFlows: riskChatFlows,
  chipToFlowKey: {
    'Yes, walk me through them': 'risk_signal_1_structuring',
    'Next signal': '__next_signal__',
    'What anomalies were detected overnight?': 'risk_turn_1_anomalies',
    'What anomalies were detected?': 'risk_turn_1_anomalies',
    'Show me the regulatory exposure': 'risk_turn_2_regulatory',
    'Show me our regulatory exposure': 'risk_turn_2_regulatory',
    'What needs escalation?': 'risk_turn_3_escalation',
    'Flag accounts needing escalation': 'risk_turn_3_escalation',
    'Show me the structuring pattern details': 'risk_structuring_details',
    'Show me the wire transfer timeline': 'risk_wire_timeline',
    "What's driving the complaint increase?": 'risk_complaint_drivers',
    'Summarize BSA/AML posture': 'risk_bsa_posture',
    'Show me active anomalies': 'risk_turn_1_anomalies',
    'Show me SAR filing status': 'risk_bsa_posture',
    'Show me the NCUA score': 'risk_turn_2_regulatory',
    'Show me open investigations': 'risk_escalation_status',
    'Generate an audit trail for compliance': 'risk_audit_trail',
    'Generate a board-level risk summary': 'risk_board_summary',
    'Show me the escalation pipeline': 'risk_escalation_status',
    'Who are these account holders?': 'risk_wire_timeline',
  },
  signalSequence: ['risk_signal_1_structuring', 'risk_signal_2_wire_anomaly', 'risk_signal_3_ncua_decline'],
  askTurnSequence: ['risk_turn_1_anomalies', 'risk_turn_2_regulatory', 'risk_turn_3_escalation'],
  actionTurnKey: 'risk_turn_3_escalation',
  actionConfirmMap: {
    'ACT-RISK-001': { responseKey: 'ACT-RISK-001', nextChips: ['Generate an audit trail for compliance'] },
    'ACT-RISK-002': { responseKey: 'ACT-RISK-002', nextChips: ['Generate a board-level risk summary'] },
    'ACT-RISK-003': { responseKey: 'ACT-RISK-003', nextChips: ['What anomalies were detected overnight?'] },
  },
};

export default riskConfig;

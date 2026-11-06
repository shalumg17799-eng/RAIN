// ─── CX Operator (Priya K.) ──────────────────────────────────────
import cxChatFlows from '../cx/chatFlows.json';

const cxConfig = {
  chatFlows: cxChatFlows,
  chipToFlowKey: {
    'Yes, walk me through them': 'cx_signal_1_channel_switch',
    'Next signal': '__next_signal__',
    'Where are members hitting friction?': 'cx_turn_1_channel_friction',
    'Show me the journey drop-offs': 'cx_turn_2_journey_friction',
    'Show me which journeys underperform': 'cx_turn_2_journey_friction',
    "Which journeys underperform this week?": 'cx_turn_2_journey_friction',
    'What intervention is needed?': 'cx_turn_3_intervention',
    'Show me channel switching patterns': 'cx_channel_patterns',
    "What's driving the IVR escalation spike?": 'cx_ivr_escalation_detail',
    'Show me the escalation breakdown': 'cx_ivr_escalation_detail',
    'Summarize service recovery gaps': 'cx_service_recovery_gaps',
    'Show me open cases': 'cx_service_recovery_gaps',
    'Show me active journey performance': 'cx_turn_2_journey_friction',
    "What's the CSAT trend?": 'cx_csat_trend',
    "What's the CSAT impact?": 'cx_csat_trend',
    'Show me the CSAT trend by journey': 'cx_csat_trend',
    'Who are these members?': 'cx_who_are_members',
    'Drill into mortgage journey friction': 'cx_mortgage_friction_detail',
    'Draft proactive outreach message': 'cx_outreach_draft',
    'Yes, send to callback campaign': 'cx_send_to_callback',
    'Yes, generate the slide deck': 'cx_service_recovery_report',
  },
  signalSequence: ['cx_signal_1_channel_switch', 'cx_signal_2_journey_abandon', 'cx_signal_3_ivr_escalation'],
  askTurnSequence: ['cx_turn_1_channel_friction', 'cx_turn_2_journey_friction', 'cx_turn_3_intervention'],
  actionTurnKey: 'cx_turn_3_intervention',
  actionConfirmMap: {
    'ACT-CX-001': { responseKey: 'ACT-CX-001', nextChips: ['Summarize service recovery gaps'] },
    'ACT-CX-002': { responseKey: 'ACT-CX-002', nextChips: ['Show me the escalation breakdown'] },
    'ACT-CX-003': { responseKey: 'ACT-CX-003', nextChips: ['Yes, generate the slide deck'] },
  },
};

export default cxConfig;

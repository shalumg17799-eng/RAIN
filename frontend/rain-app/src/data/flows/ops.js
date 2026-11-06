// ─── Operations & Analytics (Maya J.) ────────────────────────────
import opsChatFlows from '../chatFlows.json';

const opsConfig = {
  chatFlows: opsChatFlows,
  chipToFlowKey: {
    // Home screen flow
    'Yes, walk me through them': 'signal_1_mortgage',
    'Next signal': '__next_signal__',
    'Show me the full member journey': 'show_journey_from_home',
    'Who are these members?': 'turn_2_segmentation',
    'What should we do?': 'turn_4_actions',
    'Show me the member sentiment': 'member_sentiment',
    'Which segments?': 'turn_2_segmentation',
    'Pull the Genesys themes': 'genesys_themes',
    'How does this affect NPS?': 'nps_impact',
    "I'm ready to act": 'turn_4_actions',

    // Ask the AI flow
    "What's driving the mortgage drop-off?": 'turn_1_mortgage_dropoff',
    "Yes, show me who's affected": 'turn_2_segmentation',
    "What's the revenue impact?": 'revenue_impact',
    'Help me act on this': 'turn_4_actions',
    'Yes, create the segment': 'create_segment_confirm',
    'Not yet — show me more': 'turn_3_predictive',
    'Which members are most at risk of leaving?': 'turn_3_predictive',
    'Yes, model the impact': 'model_retention_impact',
    'Pull the Genesys themes for that segment': 'genesys_themes_segment',
    'What would you recommend?': 'turn_5_anomaly_detection',
    'Tell me about the CD complaint cluster': 'signal_3_cd_complaint',
    'Tell me about the auto loan trend': 'signal_2_auto_loan',
    'Scan for anomalies across systems': 'turn_5_anomaly_detection',
    'Escalate flagged accounts': 'escalate_flagged_accounts',
    'Show the full audit trail': 'anomaly_audit_trail',

    // Sub-flow follow-ups
    'Draft member outreach message': 'draft_outreach',
    'Send to marketing team': 'send_to_marketing',
    'Yes, notify them in Slack': 'slack_notify_confirm',
    'Not now': 'turn_5_anomaly_detection',
    'Generate a member friction brief': 'member_friction_brief',

    // Report format options
    'PowerPoint slide': 'report_powerpoint',
    'One-page PDF': 'report_pdf',
    'Email draft for my team': 'report_email',

    // Data Overview card triggers
    'Show me at-risk members': 'active_members_overview',
    'Show me active member breakdown': 'active_members_overview',
    'Summarize active alerts': 'alerts_overview',
    'Show me active alerts': 'alerts_overview',
    'Show process health': 'processes_overview',
    'Show me process health': 'processes_overview',

    // Risk screen flow
    "What's driving the transaction anomaly cluster?": 'risk_anomaly_explanation',
    'How does our NCUA posture compare to last quarter?': 'ncua_comparison',
    'Generate a board-level risk summary': 'board_risk_summary',
  },
  signalSequence: ['signal_1_mortgage', 'signal_2_auto_loan', 'signal_3_cd_complaint'],
  askTurnSequence: ['turn_1_mortgage_dropoff', 'turn_2_segmentation', 'turn_3_predictive', 'turn_5_anomaly_detection', 'turn_4_actions'],
  actionTurnKey: 'turn_4_actions',
  actionConfirmMap: {
    'ACT-001': { responseKey: 'jira', nextChips: ['Yes, notify them in Slack', 'Not now'] },
    'ACT-002': { responseKey: 'calendar', nextChips: ['Generate a member friction brief'] },
    'ACT-003': { responseKey: 'anomaly_scan', nextChips: ['Scan for anomalies across systems'] },
  },
};

export default opsConfig;

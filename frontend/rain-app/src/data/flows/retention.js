// ─── Member Retention Analyst (Derek T.) ─────────────────────────
import retChatFlows from '../retention/chatFlows.json';

const retConfig = {
  chatFlows: retChatFlows,
  chipToFlowKey: {
    'Yes, walk me through them': 'ret_signal_1_churn_surge',
    'Next signal': '__next_signal__',
    'Show me the churn signals': 'ret_turn_1_churn_signals',
    'Show me at-risk members': 'ret_turn_1_churn_signals',
    'Show me the churn rate': 'ret_turn_1_churn_signals',
    'Which segments are most at risk?': 'ret_turn_2_risk_segments',
    'Model the retention impact': 'ret_turn_3_retention_action',
    'Which members are most at risk of leaving?': 'ret_turn_1_churn_signals',
    "What's driving disengagement this month?": 'ret_churn_drivers',
    'Model the retention impact of outreach': 'ret_impact_model',
    'Generate a retention brief for leadership': 'ret_retention_brief',
    'Show me the engagement trend': 'ret_engagement_trend',
    'Show me campaign performance': 'ret_campaign_performance',
    'Show me the retiree sentiment details': 'ret_retiree_sentiment',
    'Which segments are driving this?': 'ret_which_segments_driving',
    "What's the revenue impact?": 'ret_impact_model',
  },
  signalSequence: ['ret_signal_1_churn_surge', 'ret_signal_2_engagement_decay', 'ret_signal_3_retiree_disengage'],
  askTurnSequence: ['ret_turn_1_churn_signals', 'ret_turn_2_risk_segments', 'ret_turn_3_retention_action'],
  actionTurnKey: 'ret_turn_3_retention_action',
  actionConfirmMap: {
    'ACT-RET-001': { responseKey: 'ACT-RET-001', nextChips: ['Show me campaign performance'] },
    'ACT-RET-002': { responseKey: 'ACT-RET-002', nextChips: ['Generate a retention brief for leadership'] },
    'ACT-RET-003': { responseKey: 'ACT-RET-003', nextChips: ['Show me campaign performance'] },
  },
};

export default retConfig;

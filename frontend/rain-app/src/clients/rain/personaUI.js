import {
  Baby, HeartPulse, CalendarCheck, MapPin, Bus, Ambulance, Video,
  Users, AlertTriangle, Droplet, Pill, Wifi,
  Map, Truck, Layers, Building2,
  DollarSign, Activity, WifiOff,
  Database, ShieldCheck, UserX, Clock,
  MessageSquare, ClipboardList,
} from 'lucide-react';

/**
 * RAIN persona UI configs — suggested-query chips, KPI stats, signal→chip routing,
 * golden path, and capability tags for each rural Nevada health persona. Personas
 * are added here as each phase is completed (see manifest allowlist in index.js).
 */

const delgadoUI = {
  initialChips: [
    'Show me all elevated-risk pregnancies in the service area',
    'Which patients have missed prenatal visits since the Battle Mountain closure?',
    'Cross-reference pregnancy risk with chronic conditions',
    'Which patients have no transport scheduled to their next appointment?',
    'Show me telehealth-eligible prenatal patients by connectivity',
    'What is our prenatal completion rate trend?',
    'Generate a maternal access brief for the board',
    'Which ZIP codes have the highest maternal access risk?',
  ],
  goldenPathChip: {
    greeting: 'Walk me through the high-risk cohort',
    turn_1_cohort: 'Which patients need telehealth prenatal visits?',
    turn_2_telehealth: 'Generate a priority outreach list',
    turn_3_outreach: 'Generate a maternal access brief for the board',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_cohort: 'ask_turn_1',
    signal_prenatal_gap: 'ask_turn_1',
    signal_ed_delivery: 'ask_turn_1',
    turn_2_telehealth: 'ask_turn_2',
    turn_3_outreach: 'ask_turn_3',
  },
  stats: [
    { id: 'active_pregnancies', label: 'Active Pregnancies in Service Area', value: '126', trend: 'Clinical EHR + Maternal Registry', positive: true, icon: Baby, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: 'Show me all elevated-risk pregnancies in the service area' },
    { id: 'elevated_risk', label: 'Elevated-Risk Pregnancies', value: '38', trend: 'Maternal Registry + RAIN Risk Engine', positive: false, icon: HeartPulse, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Walk me through the high-risk cohort' },
    { id: 'prenatal_completion', label: 'Prenatal Visit Completion Rate', value: '61%', trend: 'was 84% — Clinical EHR + Scheduling', positive: false, icon: CalendarCheck, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'What is our prenatal completion rate trend?' },
    { id: 'distance_delivery', label: 'Avg. Distance to Delivering Hospital', value: '115 mi', trend: 'Geospatial + Facility Registry', positive: false, icon: MapPin, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: null },
    { id: 'no_transport', label: 'Patients Without Scheduled Transport', value: '22', trend: 'NEMT Logs + Scheduling', positive: false, icon: Bus, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which patients have no transport scheduled to their next appointment?' },
    { id: 'ed_deliveries', label: 'ED Deliveries / Births Before Arrival (60-day)', value: '3', trend: 'Clinical EHR + EMS Dispatch', positive: false, icon: Ambulance, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Show me the ED delivery risk trend' },
    { id: 'telehealth_booked', label: 'Telehealth-Eligible Prenatal Visits Booked', value: '47', trend: 'Telehealth Platform + Scheduling', positive: true, icon: Video, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'Show me telehealth-eligible prenatal patients by connectivity' },
  ],
  signalToChip: {
    'SIG-RAIN-DELGADO-001': 'Walk me through the high-risk cohort',
    'SIG-RAIN-DELGADO-002': 'Show me the prenatal care gaps',
    'SIG-RAIN-DELGADO-003': 'Show me the ED delivery risk trend',
  },
  greetingFlowKey: 'greeting',
};

const whitehorseUI = {
  initialChips: [
    'Show me chronic disease patients with worsening RPM readings',
    'Which patients have a medication gap over 30 days?',
    'Cross-reference deterioration with transportation barriers',
    'Which patients lost their provider after the Battle Mountain closure?',
    'Show me diabetes patients overdue for an A1c',
    'What is our RPM transmission compliance trend?',
    'Generate a risk-ranked outreach list',
    'Model avoidable hospitalizations for the elevated-risk cohort',
  ],
  goldenPathChip: {
    greeting: 'Walk me through the deterioration cluster',
    turn_1_cluster: 'Generate an outreach list ranked by risk',
    turn_2_outreach: 'Activate Tier 1 outreach',
    turn_3_activate: 'Generate a chronic disease status report for Dr. Delgado-Reyes',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_cluster: 'ask_turn_1',
    signal_diabetes: 'ask_turn_1',
    signal_hypertension: 'ask_turn_1',
    turn_2_outreach: 'ask_turn_2',
    turn_3_activate: 'ask_turn_3',
  },
  stats: [
    { id: 'monitored', label: 'Chronic Disease Patients Monitored', value: '1,340', trend: 'Clinical EHR + RPM Platform', positive: true, icon: Users, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: null },
    { id: 'elevated_cohort', label: 'Elevated-Risk Cohort (All Conditions)', value: '208', trend: 'RAIN Risk Engine', positive: false, icon: AlertTriangle, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Generate a risk-ranked outreach list' },
    { id: 'worsening_rpm', label: 'CHF/COPD Patients With Worsening RPM', value: '17', trend: 'RPM Platform', positive: false, icon: HeartPulse, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Show me chronic disease patients with worsening RPM readings' },
    { id: 'overdue_a1c', label: 'Diabetes Patients Without Recent A1c', value: '112', trend: 'Clinical EHR + Claims', positive: false, icon: Droplet, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Show me diabetes patients overdue for an A1c' },
    { id: 'med_nonadherence', label: 'Medication Non-Adherence (30+ days)', value: '94', trend: 'Pharmacy Claims', positive: false, icon: Pill, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Which patients have a medication gap over 30 days?' },
    { id: 'rpm_compliance', label: 'RPM Transmission Compliance', value: '58%', trend: 'was 79% — RPM Platform', positive: false, icon: Wifi, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'What is our RPM transmission compliance trend?' },
    { id: 'transport_barrier', label: 'Patients With SDOH Transport Barrier', value: '186', trend: 'SDOH Data + NEMT Logs', positive: false, icon: Bus, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: 'Cross-reference deterioration with transportation barriers' },
  ],
  signalToChip: {
    'SIG-RAIN-WHITEHORSE-001': 'Walk me through the deterioration cluster',
    'SIG-RAIN-WHITEHORSE-002': 'Show me the diabetes control gaps',
    'SIG-RAIN-WHITEHORSE-003': 'What is happening with RPM adherence?',
  },
  greetingFlowKey: 'greeting',
};

const tomleyUI = {
  initialChips: [
    "Show me today's transport queue and capacity",
    'Where are the EMS coverage holes right now?',
    'Which transports can be converted to telehealth?',
    'Show me the telehealth demand against room capacity',
    'Which elevated-risk patients are awaiting transport?',
    'How has transport demand changed since the Battle Mountain closure?',
    "Cache today's plan offline for the field",
    'Generate an operations summary for the administrator',
  ],
  goldenPathChip: {
    greeting: 'Walk me through the transport queue',
    turn_1_queue: 'Can telehealth replace any of these trips?',
    turn_2_telehealth: "Generate today's operations plan",
    turn_3_plan: 'Generate an operations summary for the administrator',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_queue: 'ask_turn_1',
    signal_telehealth_capacity: 'ask_turn_1',
    signal_ems: 'ask_turn_1',
    turn_2_telehealth: 'ask_turn_2',
    turn_3_plan: 'ask_turn_3',
  },
  stats: [
    { id: 'coverage', label: 'Service Area Coverage', value: '10,200 sq mi', trend: 'Geospatial + EMS Dispatch', positive: true, icon: Map, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: null },
    { id: 'requests_today', label: 'Transport Requests Today', value: '47', trend: 'EMS Dispatch + NEMT Logs', positive: false, icon: Truck, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: "Show me today's transport queue and capacity" },
    { id: 'over_capacity', label: 'Queue Over Capacity (Trips)', value: '9', trend: 'NEMT Logs + Vehicle Roster', positive: false, icon: Layers, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Walk me through the transport queue' },
    { id: 'ems_response', label: 'Avg. EMS Response Time', value: '47 min', trend: 'baseline 34 — EMS Dispatch', positive: false, icon: Ambulance, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Where are the EMS coverage holes right now?' },
    { id: 'telehealth_unslotted', label: 'Telehealth Requests Without a Slot', value: '31', trend: 'Telehealth Demand Queue', positive: false, icon: Video, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Show me the telehealth demand against room capacity' },
    { id: 'mobile_clinic', label: 'Mobile Clinic Utilization', value: '98%', trend: 'Facility Capacity', positive: false, icon: Building2, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: null },
    { id: 'awaiting_transport', label: 'Elevated-Risk Patients Awaiting Transport', value: '16', trend: 'RAIN Risk Engine + NEMT Logs', positive: false, icon: HeartPulse, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which elevated-risk patients are awaiting transport?' },
  ],
  signalToChip: {
    'SIG-RAIN-TOMLEY-001': 'Walk me through the transport queue',
    'SIG-RAIN-TOMLEY-002': 'Show me the telehealth capacity gap',
    'SIG-RAIN-TOMLEY-003': 'Where are the EMS coverage holes?',
  },
  greetingFlowKey: 'greeting',
};

const nairUI = {
  initialChips: [
    'Show me access disparities by county',
    'Where did avoidable ED utilization concentrate after the closure?',
    'Map the maternal care desert before and after Battle Mountain',
    'Which elevated-risk patients are in telehealth dead zones?',
    'Compare outcomes in affected vs. unaffected ZIP codes',
    'Model the equity impact of mobile obstetric outreach',
    'Align our outcomes to the RHTP reporting priorities',
    'Generate a population health and equity brief for NVHA',
  ],
  goldenPathChip: {
    greeting: 'Map the downstream impact of the closure',
    turn_1_cascade: 'Where should we target resources first?',
    turn_2_target: 'Generate an equity brief for NVHA',
    turn_3_brief: 'Share with Dr. Delgado-Reyes and James',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_cascade: 'ask_turn_1',
    signal_ed: 'ask_turn_1',
    signal_telehealth_equity: 'ask_turn_1',
    turn_2_target: 'ask_turn_2',
    turn_3_brief: 'ask_turn_3',
  },
  stats: [
    { id: 'population', label: 'Rural / Frontier Population Served', value: '168,000', trend: 'EDW + Eligibility', positive: true, icon: Users, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: null },
    { id: 'desert', label: 'Women of Childbearing Age >60 mi From OB', value: '58%', trend: 'was 31% — Geospatial + Registry', positive: false, icon: MapPin, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Map the maternal care desert before and after Battle Mountain' },
    { id: 'avoidable_ed_rate', label: 'Avoidable ED Visit Rate (per 1,000)', value: '284', trend: 'Claims + State HIE', positive: false, icon: Activity, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Where did avoidable ED utilization concentrate after the closure?' },
    { id: 'avoidable_ed_cost', label: 'Avoidable ED Cost (Est. Annual)', value: '$1.4M', trend: 'Claims + EDW', positive: false, icon: DollarSign, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Show me the cost of inaction' },
    { id: 'telehealth_uptake', label: 'Telehealth Uptake (Connected ZIPs)', value: '71%', trend: 'Project ECHO Nevada', positive: true, icon: Video, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'Where are the telehealth equity gaps?' },
    { id: 'dead_zones', label: 'Elevated-Risk Patients in Telehealth Dead Zones', value: '240', trend: 'Connectivity Registry + Risk Engine', positive: false, icon: WifiOff, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which elevated-risk patients are in telehealth dead zones?' },
    { id: 'transport_prevalence', label: 'SDOH Transport-Barrier Prevalence', value: '22%', trend: 'SDOH Data', positive: false, icon: Bus, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: 'Show me access disparities by county' },
  ],
  signalToChip: {
    'SIG-RAIN-NAIR-001': 'Map the downstream impact of the closure',
    'SIG-RAIN-NAIR-002': 'Show me the avoidable ED concentration',
    'SIG-RAIN-NAIR-003': 'Where are the telehealth equity gaps?',
  },
  greetingFlowKey: 'greeting',
};

const yazzieUI = {
  initialChips: [
    'Show me data quality across all connected sources',
    'Which records have unresolved provider references?',
    'Show me RPM transmission completeness by ZIP code',
    'What is our FHIR conformance rate by feed?',
    'Which downstream risk scores are affected by data-quality issues?',
    'Show me pipeline freshness and ingestion lag',
    'What degraded after the Battle Mountain closure?',
    'Generate a data-quality summary for the technical lead',
  ],
  goldenPathChip: {
    greeting: 'Walk me through the reconciliation failure',
    turn_1_reconciliation: 'Which risk scores are affected downstream?',
    turn_2_downstream: 'Generate a remediation plan',
    turn_3_remediation: 'Generate a data-quality summary for the technical lead',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_reconciliation: 'ask_turn_1',
    signal_rpm_gap: 'ask_turn_1',
    signal_fhir: 'ask_turn_1',
    turn_2_downstream: 'ask_turn_2',
    turn_3_remediation: 'ask_turn_3',
  },
  stats: [
    { id: 'sources', label: 'Connected Data Sources', value: '11', trend: 'Integration Monitor', positive: true, icon: Database, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: 'Show me data quality across all connected sources' },
    { id: 'ingested', label: 'Records Ingested (30-day)', value: '9.2M', trend: 'Ingestion Pipelines', positive: true, icon: Layers, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: null },
    { id: 'fhir_conformance', label: 'FHIR Conformance Rate', value: '94%', trend: 'Data Quality Monitor', positive: false, icon: ShieldCheck, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'What is our FHIR conformance rate by feed?' },
    { id: 'unresolved_refs', label: 'Unresolved Provider References', value: '1,240', trend: 'FHIR Practitioner Reconciliation', positive: false, icon: UserX, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which records have unresolved provider references?' },
    { id: 'rpm_completeness', label: 'RPM Transmission Completeness', value: '78%', trend: 'target 95% — RPM Feed Monitor', positive: false, icon: Wifi, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Show me RPM transmission completeness by ZIP code' },
    { id: 'pipeline_freshness', label: 'Pipeline Freshness (Avg. Lag)', value: '3.2 hrs', trend: 'Ingestion Pipelines', positive: true, icon: Clock, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: 'Show me pipeline freshness and ingestion lag' },
    { id: 'quarantine', label: 'Records in Quarantine (DQ)', value: '14,800', trend: 'Data Quality Monitor', positive: false, icon: AlertTriangle, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Show me data quality across all connected sources' },
  ],
  signalToChip: {
    'SIG-RAIN-YAZZIE-001': 'Walk me through the reconciliation failure',
    'SIG-RAIN-YAZZIE-002': 'Show me the RPM ingestion gap',
    'SIG-RAIN-YAZZIE-003': 'What is the FHIR conformance issue?',
  },
  greetingFlowKey: 'greeting',
};

// ─── PRD v0.2 wave (UC-01 smart scheduling, UC-02 population health) ────────

const brooksUI = {
  initialChips: [
    'Which booked visits carry the highest no-show risk?',
    'Show me open telehealth slots across nearby clinics',
    'Which visits can switch to telehealth?',
    "Run eligibility checks for this week's bookings",
    'Which patients have no SMS consent on file?',
    'Build reminder plans for the high-risk visits',
    'Who has not confirmed their visit yet?',
    "Show me this week's confirmations board",
  ],
  goldenPathChip: {
    greeting: 'Walk me through the no-show risk list',
    turn_1_noshow: 'Which visits can switch to telehealth?',
    turn_2_telehealth: 'Build reminder plans for the high-risk visits',
    turn_3_reminders: 'Create CHW call tasks for the non-responders',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_noshow: 'ask_turn_1',
    signal_slots: 'ask_turn_1',
    signal_eligibility: 'ask_turn_1',
    turn_2_telehealth: 'ask_turn_2',
    turn_3_reminders: 'ask_turn_3',
  },
  stats: [
    { id: 'booked_visits', label: 'Booked Visits on the Schedule', value: '200', trend: 'Scheduling System', positive: true, icon: CalendarCheck, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: "Show me this week's confirmations board" },
    { id: 'high_no_show', label: 'Visits at High No-Show Risk', value: '53', trend: 'Pattern Profiles + Reminder Engine', positive: false, icon: AlertTriangle, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which booked visits carry the highest no-show risk?' },
    { id: 'open_telehealth_slots', label: 'Open Telehealth Slots', value: '39', trend: 'Slot Inventory', positive: true, icon: Video, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'Show me open telehealth slots across nearby clinics' },
    { id: 'eligibility_active', label: 'Coverage Checks Active', value: '41', trend: 'of 200 — Eligibility Service (270/271)', positive: false, icon: ShieldCheck, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: "Run eligibility checks for this week's bookings" },
    { id: 'reminders_sent', label: 'Reminders Sent (7-day)', value: '200', trend: 'Reminder Engine — SMS + voice, EN/ES', positive: true, icon: MessageSquare, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: 'Who has not confirmed their visit yet?' },
    { id: 'sms_consent', label: 'Patients With SMS Consent', value: '97', trend: 'Contact Preferences (TCPA)', positive: false, icon: Users, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: 'Which patients have no SMS consent on file?' },
  ],
  signalToChip: {
    'SIG-RAIN-KAYLA-001': 'Walk me through the no-show risk list',
    'SIG-RAIN-KAYLA-002': 'Which visits can switch to telehealth?',
    'SIG-RAIN-KAYLA-003': 'Show me the lapsed coverage list',
  },
  greetingFlowKey: 'greeting',
};

const hollowayUI = {
  initialChips: [
    "Walk me through today's call list",
    'Which of my patients are highest risk?',
    'Who has not replied to their reminders?',
    "Which high-risk patients can't be reached by SMS?",
    'Which patients screened positive for a social need?',
    'Plan my field visits for the week',
    'What did outreach close this month?',
    'Log an outreach outcome',
  ],
  goldenPathChip: {
    greeting: "Walk me through today's call list",
    turn_1_calllist: 'Plan my field visits for the week',
    turn_2_fieldplan: 'Generate the day sheet for tomorrow',
    turn_3_daysheet: 'Log an outreach outcome',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_calllist: 'ask_turn_1',
    signal_nonresponse: 'ask_turn_1',
    signal_unreachable: 'ask_turn_1',
    turn_2_fieldplan: 'ask_turn_2',
    turn_3_daysheet: 'ask_turn_3',
  },
  stats: [
    { id: 'open_tasks', label: 'Open Outreach Tasks', value: '80', trend: 'Outreach Tasks — risk-ranked', positive: false, icon: ClipboardList, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: "Walk me through today's call list" },
    { id: 'high_risk', label: 'High-Risk Patients in the Area', value: '60', trend: 'Risk Engine', positive: false, icon: HeartPulse, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which of my patients are highest risk?' },
    { id: 'pending_replies', label: 'Reminders Awaiting a Reply', value: '39', trend: 'Reminder Engine', positive: false, icon: MessageSquare, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Who has not replied to their reminders?' },
    { id: 'sdoh_screened', label: 'SDOH Screenings on File', value: '200', trend: 'Social-Need Screening', positive: true, icon: Users, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: 'Which patients screened positive for a social need?' },
    { id: 'tasks_closed', label: 'Outreach Tasks Closed', value: '51', trend: 'Outreach Tasks', positive: true, icon: CalendarCheck, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'What did outreach close this month?' },
    { id: 'no_sms', label: 'Patients Without SMS Consent', value: '103', trend: 'Contact Preferences — voice/CHW only', positive: false, icon: WifiOff, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: "Which high-risk patients can't be reached by SMS?" },
  ],
  signalToChip: {
    'SIG-RAIN-DENISE-001': "Walk me through today's call list",
    'SIG-RAIN-DENISE-002': 'Who has not replied to their reminders?',
    'SIG-RAIN-DENISE-003': "Which high-risk patients can't be reached by SMS?",
  },
  greetingFlowKey: 'greeting',
};

const okaforUI = {
  initialChips: [
    "Walk me through this week's schedule",
    'Which of my patients are rising risk?',
    'Show me the pre-visit summary for my next patient',
    'Who has a medication adherence gap before their visit?',
    'How much of my schedule is telehealth?',
    'Show me the latest remote monitoring readings',
    'Which visits still need a confirmation?',
    'Order a follow-up for a patient',
  ],
  goldenPathChip: {
    greeting: "Walk me through this week's schedule",
    turn_1_schedule: 'Which of my patients are rising risk?',
    turn_2_risk: 'Generate pre-visit summaries for tomorrow',
    turn_3_previsit: 'Order a follow-up for a patient',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_schedule: 'ask_turn_1',
    signal_adherence: 'ask_turn_1',
    turn_2_risk: 'ask_turn_2',
    turn_3_previsit: 'ask_turn_3',
  },
  stats: [
    { id: 'panel_size', label: 'Patients on the Panel', value: '200', trend: 'Patient Registry', positive: true, icon: Users, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: null },
    { id: 'visits_week', label: 'Visits on the Schedule', value: '200', trend: 'Scheduling System', positive: true, icon: CalendarCheck, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: "Walk me through this week's schedule" },
    { id: 'telehealth_share', label: 'Telehealth Share of Visits', value: '54%', trend: 'Encounters', positive: true, icon: Video, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'How much of my schedule is telehealth?' },
    { id: 'high_risk_panel', label: 'High-Risk Patients on Panel', value: '60', trend: 'Risk Engine', positive: false, icon: HeartPulse, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which of my patients are rising risk?' },
    { id: 'low_adherence', label: 'Medications Under 80% Adherence', value: '161', trend: 'Medication History', positive: false, icon: Pill, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Who has a medication adherence gap before their visit?' },
    { id: 'rpm_readings', label: 'RPM Readings (7-day)', value: '200', trend: 'Remote Monitoring', positive: true, icon: Activity, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: 'Show me the latest remote monitoring readings' },
  ],
  signalToChip: {
    'SIG-RAIN-SAMUEL-001': "Walk me through this week's schedule",
    'SIG-RAIN-SAMUEL-002': 'Which of my patients are rising risk?',
    'SIG-RAIN-SAMUEL-003': 'Who has a medication adherence gap before their visit?',
  },
  greetingFlowKey: 'greeting',
};

const hargroveUI = {
  initialChips: [
    'Walk me through the clinic risk mix',
    'Which care gaps are still open?',
    'How are we trending on care-gap closure?',
    'Where is ED utilization concentrating?',
    'What is our telehealth share trend?',
    'What is our social-need screening coverage?',
    'Compare our measures against county benchmarks',
    'Generate the quality report for the board',
  ],
  goldenPathChip: {
    greeting: 'Walk me through the clinic risk mix',
    turn_1_riskmix: 'Which care gaps are still open?',
    turn_2_gaps: 'Generate the quality report for the board',
    turn_3_report: 'Assign the open gaps to the outreach team',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_riskmix: 'ask_turn_1',
    signal_closure: 'ask_turn_1',
    signal_ed: 'ask_turn_1',
    turn_2_gaps: 'ask_turn_2',
    turn_3_report: 'ask_turn_3',
  },
  stats: [
    { id: 'high_risk', label: 'High-Risk Patients (Clinic)', value: '60', trend: 'Risk Engine — of 200 attributed', positive: false, icon: HeartPulse, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Walk me through the clinic risk mix' },
    { id: 'open_gaps', label: 'Open Care-Gap Tasks', value: '80', trend: 'Outreach Tasks', positive: false, icon: ClipboardList, iconColor: 'text-amber-600', iconBg: 'bg-amber-500/10', chipText: 'Which care gaps are still open?' },
    { id: 'gaps_closed', label: 'Care-Gap Tasks Closed', value: '51', trend: 'Outreach Tasks', positive: true, icon: CalendarCheck, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'How are we trending on care-gap closure?' },
    { id: 'ed_claims', label: 'ED-Flagged Claims (Window)', value: '96', trend: 'Claims', positive: false, icon: Ambulance, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Where is ED utilization concentrating?' },
    { id: 'telehealth_share', label: 'Telehealth Share of Visits', value: '54%', trend: 'Encounters', positive: true, icon: Video, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'What is our telehealth share trend?' },
    { id: 'sdoh_coverage', label: 'SDOH Screenings on File', value: '200', trend: 'Social-Need Screening', positive: true, icon: Users, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: 'What is our social-need screening coverage?' },
  ],
  signalToChip: {
    'SIG-RAIN-LINDA-001': 'Walk me through the clinic risk mix',
    'SIG-RAIN-LINDA-002': 'How are we trending on care-gap closure?',
    'SIG-RAIN-LINDA-003': 'Where is ED utilization concentrating?',
  },
  greetingFlowKey: 'greeting',
};

const bellUI = {
  initialChips: [
    'Which counties concentrate the most care gaps?',
    'Where do broadband dead zones limit telehealth?',
    'Which clinics diverge from their county ED baseline?',
    'Compare counties against public benchmarks',
    'How many clinic sites are telehealth-capable?',
    'What public datasets back the county view?',
    'Show me program reach and outcomes by clinic',
    'Generate the CMS reporting package',
  ],
  goldenPathChip: {
    greeting: 'Which counties concentrate the most care gaps?',
    turn_1_counties: 'Compare counties against public benchmarks',
    turn_2_benchmark: 'Generate the CMS reporting package',
    turn_3_cms: 'Share the package with the clinic directors',
  },
  flowKeyToCapabilityTrigger: {
    greeting: 'home_load',
    turn_1_counties: 'ask_turn_1',
    signal_broadband: 'ask_turn_1',
    signal_ed_divergence: 'ask_turn_1',
    turn_2_benchmark: 'ask_turn_2',
    turn_3_cms: 'ask_turn_3',
  },
  stats: [
    { id: 'counties', label: 'Counties in the Program View', value: '165', trend: 'County Metrics + CDC PLACES', positive: true, icon: Map, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: 'Which counties concentrate the most care gaps?' },
    { id: 'metric_records', label: 'County Metric Records Loaded', value: '200', trend: 'Public Data — labelled synthetic/public', positive: true, icon: Database, iconColor: 'text-blue-600', iconBg: 'bg-blue-500/10', chipText: 'What public datasets back the county view?' },
    { id: 'unserved_broadband', label: 'Broadband-Unserved Areas', value: '96', trend: 'FCC Broadband Coverage', positive: false, icon: WifiOff, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Where do broadband dead zones limit telehealth?' },
    { id: 'clinic_sites', label: 'Connected Clinic Sites', value: '200', trend: 'Clinic Site Registry', positive: true, icon: Building2, iconColor: 'text-violet-600', iconBg: 'bg-violet-500/10', chipText: 'How many clinic sites are telehealth-capable?' },
    { id: 'telehealth_sites', label: 'Telehealth-Capable Sites', value: '95', trend: 'Clinic Site Registry', positive: true, icon: Video, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-500/10', chipText: 'How many clinic sites are telehealth-capable?' },
    { id: 'ed_claims', label: 'ED-Flagged Claims (Program)', value: '96', trend: 'Claims', positive: false, icon: Ambulance, iconColor: 'text-red-600', iconBg: 'bg-red-500/10', chipText: 'Which clinics diverge from their county ED baseline?' },
  ],
  signalToChip: {
    'SIG-RAIN-MARCUS-001': 'Which counties concentrate the most care gaps?',
    'SIG-RAIN-MARCUS-002': 'Where do broadband dead zones limit telehealth?',
    'SIG-RAIN-MARCUS-003': 'Which clinics diverge from their county ED baseline?',
  },
  greetingFlowKey: 'greeting',
};

export const rainUIConfigs = {
  rain_delgado: delgadoUI,
  rain_whitehorse: whitehorseUI,
  rain_tomley: tomleyUI,
  rain_nair: nairUI,
  rain_yazzie: yazzieUI,
  rain_brooks: brooksUI,
  rain_holloway: hollowayUI,
  rain_okafor: okaforUI,
  rain_hargrove: hargroveUI,
  rain_bell: bellUI,
};

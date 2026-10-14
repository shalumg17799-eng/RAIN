import {
  Baby, HeartPulse, CalendarCheck, MapPin, Bus, Ambulance, Video,
  Users, AlertTriangle, Droplet, Pill, Wifi,
  Map, Truck, Layers, Building2,
  DollarSign, Activity, WifiOff,
  Database, ShieldCheck, UserX, Clock,
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

export const rainUIConfigs = {
  rain_delgado: delgadoUI,
  rain_whitehorse: whitehorseUI,
  rain_tomley: tomleyUI,
  rain_nair: nairUI,
  rain_yazzie: yazzieUI,
};

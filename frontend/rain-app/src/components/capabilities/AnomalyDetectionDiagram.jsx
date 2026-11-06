import { UpArrow } from './FlowArrow';

/**
 * Capability deep-dive diagram: AnomalyDetection. What it says for a tenant comes in as
 * `content` (the manifest's `capabilityDiagrams.anomaly`); without it the diagram
 * shows the generic platform story under the client's short name.
 */
// `clientName` is the client's short name, from the modal that draws the diagram.
export default function AnomalyDetectionDiagram({ content, clientName } = {}) {
  const clientShort = (clientName || 'USSFCU').toUpperCase();

  const fs = {
    eyebrow:  'clamp(9px,  min(1.5vh, 1.2vw),  16px)',
    title:    'clamp(22px, min(4.2vh, 3.2vw), 42px)',
    subtitle: 'clamp(11px, min(1.9vh, 1.5vw), 19px)',
    body:     'clamp(11px, min(1.8vh, 1.4vw), 18px)',
    label:    'clamp(9px,  min(1.5vh, 1.15vw), 15px)',
    labelSm:  'clamp(8px,  min(1.3vh, 1vw),   14px)',
    cardTitle:'clamp(10px, min(1.6vh, 1.25vw), 17px)',
    cardDesc: 'clamp(9px,  min(1.4vh, 1.1vw),  15px)',
    pill:     'clamp(8px,  min(1.25vh, 1vw),   13px)',
    small:    'clamp(9px,  min(1.3vh, 1vw),    14px)',
  };

  const clientConfig = content ?? {
    bodyText: 'Detects unusual patterns across member transactions, contact center volume, and workflow exceptions in real time, and surfaces them as prioritized, actionable signals.',
    monitorAgents: [
      { name: 'Transaction Monitor', desc: 'Watches payment and loan activity' },
      { name: 'Volume Monitor', desc: 'Contact center and channel spikes' },
      { name: 'Exception Monitor', desc: 'UiPath workflow failures' },
      { name: 'Pattern Correlator', desc: 'Links anomalies across systems' },
      { name: 'Compliance Scanner', desc: 'BSA/AML pattern detection' },
    ],
    sourcesLabel: `${clientShort} SIGNAL SOURCES`,
    primarySources: ['Data Cloud', 'Financial Services Cloud', 'Service Cloud', 'Marketing Cloud'],
    secondarySources: ['Genesys Cloud', 'Snowflake', 'UiPath', 'ICE/LOS'],
    deployedAt: 'Radiant Solutions Lab',
    deployedDesc: 'Across multiple engagements',
    gapText: 'Risk signals are buried in platform-specific dashboards. Cross-system anomalies go unseen.',
    withText: 'Real-time, cross-platform pattern detection with prioritized, auditable alerts.',
  };

  return (
    <div
      className="w-full h-full flex flex-col"
      style={{ fontFamily: 'Inter, Helvetica, Arial, sans-serif', background: 'var(--color-surface)', padding: '2.4vh 2vw 2vh' }}
    >
      {/* ── TOP: Capability Identity ── */}
      <div className="flex-shrink-0" style={{ marginBottom: '0.6vh' }}>
        <p style={{ fontSize: fs.eyebrow, color: 'var(--color-critical)', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', margin: '0 0 0.4vh 0' }}>
          RADIANT AI CAPABILITY
        </p>
        <h2 style={{ fontSize: fs.title, color: 'var(--color-brand)', fontWeight: 800, margin: '0 0 0.2vh 0', lineHeight: 1.15 }}>
          Anomaly Detection
        </h2>
        <p style={{ fontSize: fs.subtitle, color: 'var(--color-text-muted)', fontWeight: 500, margin: '0 0 0.3vh 0' }}>
          Powered by Predictive AI + Agentic Data Platform + Agentic AI
        </p>
        <p style={{ fontSize: fs.body, color: 'var(--color-text)', fontWeight: 400, margin: 0, lineHeight: 1.5 }}>
          {clientConfig.bodyText}
        </p>
      </div>

      <div style={{ borderBottom: '1px solid var(--color-border)', marginTop: '0.6vh', marginBottom: '1.2vh', flexShrink: 0 }} />

      <p className="flex-shrink-0" style={{ fontSize: fs.labelSm, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase', margin: '0 0 0.5vh 0' }}>
        UNDERLYING ARCHITECTURE
      </p>

      {/* ── ARCHITECTURE DIAGRAM ── */}
      <div className="flex-1 min-h-0 flex flex-col">

        {/* Row 1: Predictive AI + Responsible AI */}
        <div className="flex" style={{ flex: '3 1 0', minHeight: 0, gap: 'min(1vw, 10px)' }}>
          <div
            className="flex-1 flex flex-col"
            style={{ background: 'color-mix(in srgb, var(--color-brand) 7%, transparent)', border: '1.5px solid var(--color-brand)', borderRadius: '8px', padding: 'min(1.2vh, 10px) min(1.2%, 12px)' }}
          >
            <div className="flex items-baseline flex-shrink-0" style={{ marginBottom: 'min(0.8vh, 8px)', gap: 'min(1vw, 12px)' }}>
              <span style={{ fontSize: fs.label, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>PREDICTIVE AI</span>
              <span style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 400 }}>Anomaly scoring, noise reduction, and priority ranking</span>
            </div>
            <div className="flex flex-1 min-h-0" style={{ gap: 'min(0.6vw, 8px)' }}>
              {/* Optional per-client override (the Comptroller's personas set it); absent, the default below renders as before. */}
              {(clientConfig.predictiveAI ?? [
                { name: 'Anomaly Scoring', desc: 'Severity, confidence, and business impact per signal' },
                { name: 'Alert Noise Reduction', desc: 'ML filtering separates true positives from false alarms' },
                { name: 'Risk Prioritization', desc: 'Ranks by member impact, regulatory exposure, urgency' },
              ]).map((item) => (
                <div
                  key={item.name}
                  className="flex-1 flex flex-col justify-center"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-brand)', borderRadius: '6px', padding: 'min(1.2vh, 10px) min(3%, 14px)' }}
                >
                  <p style={{ fontSize: fs.cardTitle, color: 'var(--color-brand)', fontWeight: 700, margin: '0 0 min(0.4vh, 4px) 0' }}>{item.name}</p>
                  <p style={{ fontSize: fs.cardDesc, color: 'var(--color-text-muted)', margin: 0, lineHeight: 1.45 }}>{item.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Responsible AI sidebar */}
          <div
            className="flex flex-col"
            style={{ width: 'min(24%, 220px)', flexShrink: 0, background: 'var(--color-surface)', border: '1.5px solid #00897B', borderRadius: '8px', padding: 'min(1.2vh, 10px) min(1.5%, 14px)' }}
          >
            <p className="flex-shrink-0" style={{ fontSize: fs.label, color: '#00897B', fontWeight: 700, letterSpacing: '1.5px', margin: '0 0 min(1.2vh, 10px) 0' }}>RESPONSIBLE AI</p>
            <div className="flex-1 flex flex-col justify-around">
              {(clientConfig.responsibleAI ?? ['BSA/AML Compliance Alignment', 'NCUA Exam Readiness Posture', 'Full Signal Audit Trail', 'Explainable Anomaly Reasoning']).map((item) => (
                <p key={item} style={{ fontSize: fs.cardDesc, color: 'var(--color-text)', fontWeight: 600, margin: 0, lineHeight: 1.35 }}>{item}</p>
              ))}
            </div>
          </div>
        </div>

        <UpArrow />

        {/* Row 2: Agentic Data Platform + Agentic AI */}
        <div
          className="flex flex-col"
          style={{ flex: '2.8 1 0', minHeight: 0, background: 'color-mix(in srgb, var(--color-brand) 4%, transparent)', border: '1.5px solid var(--color-brand)', borderRadius: '8px', padding: 'min(1vh, 8px) min(1.2%, 12px)' }}
        >
          <div className="flex items-baseline flex-shrink-0" style={{ marginBottom: 'min(0.6vh, 6px)', gap: 'min(1vw, 12px)' }}>
            <span style={{ fontSize: fs.label, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>AGENTIC DATA PLATFORM + AGENTIC AI</span>
            <span style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 400 }}>Real-time monitoring agents across all connected systems</span>
          </div>
          <div className="flex flex-1 min-h-0" style={{ gap: 'min(0.5vw, 7px)' }}>
            {clientConfig.monitorAgents.map((agent) => (
              <div
                key={agent.name}
                className="flex-1 flex flex-col justify-center"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-brand)', borderRadius: '6px', padding: 'min(1vh, 8px) min(2.5%, 12px)' }}
              >
                <p style={{ fontSize: fs.cardTitle, color: 'var(--color-brand)', fontWeight: 700, margin: '0 0 min(0.3vh, 3px) 0' }}>{agent.name}</p>
                <p style={{ fontSize: fs.cardDesc, color: 'var(--color-text-muted)', margin: 0, lineHeight: 1.4 }}>{agent.desc}</p>
              </div>
            ))}
          </div>
        </div>

        <UpArrow />

        {/* Row 3: Client Signal Sources */}
        <div
          className="flex items-center flex-nowrap"
          style={{ flex: '1.2 1 0', minHeight: 0, background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: '6px', padding: '0 min(1.5%, 14px)', gap: 'min(1.2vw, 16px)' }}
        >
          <p className="flex-shrink-0" style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 700, letterSpacing: '1px', margin: 0, whiteSpace: 'nowrap' }}>
            {clientConfig.sourcesLabel}
          </p>
          <div className="flex items-center flex-1 flex-nowrap" style={{ gap: 'min(0.4vw, 5px)', overflow: 'hidden' }}>
            {clientConfig.primarySources.map((src) => (
              <span
                key={src}
                className="flex-shrink-0"
                style={{ background: 'var(--color-brand)', color: 'var(--color-text-inverse)', fontSize: fs.pill, fontWeight: 600, padding: 'min(0.4vh, 4px) min(0.7vw, 10px)', borderRadius: '4px', whiteSpace: 'nowrap' }}
              >
                {src}
              </span>
            ))}
            {clientConfig.secondarySources.map((src) => (
              <span
                key={src}
                className="flex-shrink-0"
                style={{ background: '#00897B', color: 'var(--color-text-inverse)', fontSize: fs.pill, fontWeight: 600, padding: 'min(0.4vh, 4px) min(0.7vw, 10px)', borderRadius: '4px', whiteSpace: 'nowrap' }}
              >
                {src}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── BOTTOM: Gap + Proof ── */}
      <div className="flex-shrink-0" style={{ marginTop: '1vh' }}>
        <div style={{ borderBottom: '1px solid var(--color-border)', marginBottom: '1vh' }} />
        <div className="flex" style={{ gap: 'min(1vw, 10px)' }}>
          <div
            className="flex-1 flex flex-col justify-center"
            style={{ background: 'var(--color-warning-50)', border: '1px solid var(--color-warning-500)', borderRadius: '6px', padding: 'min(0.8vh, 8px) min(1.5%, 14px)' }}
          >
            <p style={{ fontSize: fs.small, color: 'var(--color-text)', margin: '0 0 min(0.2vh, 2px) 0', lineHeight: 1.5 }}>
              <span style={{ fontWeight: 700 }}>The gap today: </span>
              <span>{clientConfig.gapText}</span>
            </p>
            <p style={{ fontSize: fs.small, color: 'var(--color-text)', margin: 0, lineHeight: 1.5 }}>
              <span style={{ fontWeight: 700 }}>With Anomaly Detection: </span>
              <span>{clientConfig.withText}</span>
            </p>
          </div>

          <div
            className="flex flex-col justify-center"
            style={{ width: 'min(24%, 220px)', flexShrink: 0, background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: '6px', padding: 'min(0.8vh, 8px) min(1.5%, 14px)' }}
          >
            <p style={{ fontSize: fs.labelSm, color: 'var(--color-critical)', fontWeight: 700, letterSpacing: '1px', margin: '0 0 min(0.3vh, 3px) 0' }}>Developed By</p>
            <p style={{ margin: '0 0 min(0.2vh, 2px) 0' }}>
              <span style={{ fontSize: fs.subtitle, color: 'var(--color-brand)', fontWeight: 800 }}>{clientConfig.deployedAt}</span>
            </p>
            <p style={{ fontSize: fs.small, color: 'var(--color-text-muted)', fontWeight: 400, margin: 0, lineHeight: 1.35 }}>
              {clientConfig.deployedDesc}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

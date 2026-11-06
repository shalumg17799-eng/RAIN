import { UpArrow } from './FlowArrow';

/**
 * Capability deep-dive diagram: BehavioralSegmentation. What it says for a tenant comes in as
 * `content` (the manifest's `capabilityDiagrams.friction`); without it the diagram
 * shows the generic platform story under the client's short name.
 */
// `clientName` is the client's short name, from the modal that draws the diagram.
export default function BehavioralSegmentationDiagram({ content, clientName } = {}) {
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
    bodyText: 'The AI identifies which members are at risk, behaving differently, or showing early signals of friction or churn, without manual tagging or report-building.',
    adpSubtitle: 'Unified member profiles across Salesforce and non-Salesforce systems',
    ontologyDesc: "'Member' means one thing",
    enrichmentDesc: 'Adds behavioral context',
    gapText: 'Segments are manually built in Marketing Cloud. No cross-platform behavioral detection.',
    withText: 'AI continuously surfaces where friction is forming and which members are affected.',
    sourcesLabel: `${clientShort} DATA SOURCES`,
    primarySources: ['Data Cloud', 'Financial Services Cloud', 'Marketing Cloud', 'Service Cloud'],
    secondarySources: ['Genesys Cloud', 'Snowflake', 'Blend', 'ICE/LOS'],
    deployedAt: 'Radiant Solutions Lab',
    deployedDesc: 'Across multiple engagements',
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
          Friction Observability
        </h2>
        <p style={{ fontSize: fs.subtitle, color: 'var(--color-text-muted)', fontWeight: 500, margin: '0 0 0.3vh 0' }}>
          Powered by Intelligent CX + Agentic Data Platform + KAG
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

        {/* Row 1: Intelligent CX + Responsible AI */}
        <div className="flex" style={{ flex: '3 1 0', minHeight: 0, gap: 'min(1vw, 10px)' }}>
          <div
            className="flex-1 flex flex-col"
            style={{ background: 'color-mix(in srgb, var(--color-brand) 7%, transparent)', border: '1.5px solid var(--color-brand)', borderRadius: '8px', padding: 'min(1.2vh, 10px) min(1.2%, 12px)' }}
          >
            <div className="flex items-baseline flex-shrink-0" style={{ marginBottom: 'min(0.8vh, 8px)', gap: 'min(1vw, 12px)' }}>
              {/* Optional per-client overrides (the Comptroller's personas set them); absent, the defaults render as before. */}
              <span style={{ fontSize: fs.label, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>{clientConfig.topLabel ?? 'INTELLIGENT CX'}</span>
              <span style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 400 }}>{clientConfig.topSubtitle ?? 'KAG-powered segmentation across VOC, behavior, and operational data'}</span>
            </div>
            <div className="flex flex-1 min-h-0" style={{ gap: 'min(0.6vw, 8px)' }}>
              {(clientConfig.topCards ?? [
                { name: 'Pattern Detection', desc: 'Identifies emerging behavioral clusters across all sources' },
                { name: 'Segment Profiling', desc: 'Auto-generates segment attributes, size, and risk' },
                { name: 'Signal Mapping', desc: 'Links segments to friction, churn, and NPS drivers' },
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
              {(clientConfig.responsibleAI ?? ['Bias Detection in Segments', 'Explainable Segment Definitions', 'Fair Lending Compliance', 'NCUA/ECOA Alignment']).map((item) => (
                <p key={item} style={{ fontSize: fs.cardDesc, color: 'var(--color-text)', fontWeight: 600, margin: 0, lineHeight: 1.35 }}>{item}</p>
              ))}
            </div>
          </div>
        </div>

        <UpArrow />

        {/* Row 2: Agentic Data Platform */}
        <div
          className="flex flex-col"
          style={{ flex: '2.8 1 0', minHeight: 0, background: 'color-mix(in srgb, var(--color-brand) 4%, transparent)', border: '1.5px solid var(--color-brand)', borderRadius: '8px', padding: 'min(1vh, 8px) min(1.2%, 12px)' }}
        >
          <div className="flex items-baseline flex-shrink-0" style={{ marginBottom: 'min(0.6vh, 6px)', gap: 'min(1vw, 12px)' }}>
            <span style={{ fontSize: fs.label, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>AGENTIC DATA PLATFORM</span>
            <span style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 400 }}>{clientConfig.adpSubtitle}</span>
          </div>
          <div className="flex flex-1 min-h-0" style={{ gap: 'min(0.5vw, 7px)' }}>
            {[
              { name: 'Inspector Agent', desc: 'Profiles data quality' },
              { name: 'Cleaning Agent', desc: 'Resolves identity conflicts' },
              { name: 'Ontology Agent', desc: clientConfig.ontologyDesc },
              { name: 'Enrichment Agent', desc: clientConfig.enrichmentDesc },
              { name: 'Cypher Agent', desc: 'Relationship graph' },
            ].map((agent) => (
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

        {/* Row 3: Client Data Sources */}
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
              <span style={{ fontWeight: 700 }}>With Friction Observability: </span>
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

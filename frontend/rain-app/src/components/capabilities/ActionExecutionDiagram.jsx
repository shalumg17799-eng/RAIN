import { useBranding } from '../../context/BrandingContext';

export default function ActionExecutionDiagram() {
  const { client } = useBranding();
  const clientShort = (client?.shortName || 'RAIN').toUpperCase();

  /* Arrow points UPWARD — data flows up from orchestration to ConverseAI */
  const UpArrow = () => (
    <div className="flex justify-center flex-shrink-0" style={{ height: 'min(2.2vh, 20px)' }}>
      <svg width="14" height="100%" viewBox="0 0 14 24" fill="none" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
        <polygon points="7,0 2,8 12,8" fill="#003087" />
        <line x1="7" y1="7" x2="7" y2="24" stroke="#003087" strokeWidth="1.8" strokeDasharray="4 3" />
      </svg>
    </div>
  );

  /* Arrow points DOWNWARD — actions flow down from orchestration to execution targets */
  const DownArrow = () => (
    <div className="flex justify-center flex-shrink-0" style={{ height: 'min(2.2vh, 20px)' }}>
      <svg width="14" height="100%" viewBox="0 0 14 24" fill="none" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
        <line x1="7" y1="0" x2="7" y2="17" stroke="#003087" strokeWidth="1.8" strokeDasharray="4 3" />
        <polygon points="7,24 2,16 12,16" fill="#003087" />
      </svg>
    </div>
  );

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

  const clientConfig = {
    bodyText: 'Move from insight to action inside the same conversation: generate outreach lists, care-coordination plans, transport schedules, telehealth referrals, and stakeholder reports — all confirmed by you before execution.',
    targetsLabel: `${clientShort} EXECUTION TARGETS`,
    primaryTargets: ['Agentforce', 'Marketing Cloud', 'Service Cloud', 'MuleSoft'],
    secondaryTargets: ['Genesys Cloud', 'UiPath', 'JIRA', 'Slack', 'Email'],
    gapText: 'Each rural Nevada health system reports within its own data. When a maternal risk signal in the EHR correlates with a transport shortage, a chronic-care continuity loss, a telehealth dead zone, or a data-quality break, no native tool connects those signals across systems.',
    withText: 'Cross-system intelligence that reads across clinical, telehealth, RPM, claims, transportation, public health, and SDOH data to surface correlated insights and recommended actions before you ask.',
    deployedAt: 'Verizon',
    deployedDesc: 'Multi-agent orchestration across network ops',
    sourcesLabel: 'RAIN DATA SOURCES',
    primarySources: ['Clinical EHR', 'Maternal Registry', 'RPM Platform', 'Claims & Encounters'],
    secondarySources: ['Telehealth (ECHO NV)', 'EMS / NEMT', 'SDOH Data', 'State HIE'],
  };

  return (
    <div
      className="w-full h-full flex flex-col"
      style={{ fontFamily: 'Inter, Helvetica, Arial, sans-serif', background: '#FFFFFF', padding: '2.4vh 2vw 2vh' }}
    >
      {/* ── TOP: Capability Identity ── */}
      <div className="flex-shrink-0" style={{ marginBottom: '0.6vh' }}>
        <p style={{ fontSize: fs.eyebrow, color: '#CC0000', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', margin: '0 0 0.4vh 0' }}>
          RADIANT AI CAPABILITY
        </p>
        <h2 style={{ fontSize: fs.title, color: '#003087', fontWeight: 800, margin: '0 0 0.2vh 0', lineHeight: 1.15 }}>
          Automated Action
        </h2>
        <p style={{ fontSize: fs.subtitle, color: '#666666', fontWeight: 500, margin: '0 0 0.3vh 0' }}>
          Powered by ConverseAI + Agentic AI + Multi-Agent Orchestration
        </p>
        <p style={{ fontSize: fs.body, color: '#333333', fontWeight: 400, margin: 0, lineHeight: 1.5 }}>
          {clientConfig.bodyText}
        </p>
      </div>

      <div style={{ borderBottom: '1px solid #E0E0E0', marginTop: '0.6vh', marginBottom: '1.2vh', flexShrink: 0 }} />

      <p className="flex-shrink-0" style={{ fontSize: fs.labelSm, color: '#003087', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase', margin: '0 0 0.5vh 0' }}>
        UNDERLYING ARCHITECTURE
      </p>

      {/* ── ARCHITECTURE DIAGRAM ── */}
      <div className="flex-1 min-h-0 flex flex-col">

        {/* Layer 3 (top): ConverseAI + Agentic AI + Responsible AI sidebar */}
        <div className="flex" style={{ flex: '3 1 0', minHeight: 0, gap: 'min(1vw, 10px)' }}>
          <div
            className="flex-1 flex flex-col"
            style={{ background: 'rgba(0, 48, 135, 0.07)', border: '1.5px solid #003087', borderRadius: '8px', padding: 'min(1.2vh, 10px) min(1.2%, 12px)' }}
          >
            <div className="flex items-baseline flex-shrink-0" style={{ marginBottom: 'min(0.8vh, 8px)', gap: 'min(1vw, 12px)' }}>
              <span style={{ fontSize: fs.label, color: '#003087', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>CONVERSEAI + AGENTIC AI</span>
              <span style={{ fontSize: fs.labelSm, color: '#666666', fontWeight: 400 }}>Conversational action layer with human-in-the-loop confirmation</span>
            </div>
            <div className="flex flex-1 min-h-0" style={{ gap: 'min(0.6vw, 8px)' }}>
              {[
                { name: 'Action Planning', desc: 'AI recommends actions based on conversation context' },
                { name: 'Confirm Before Execute', desc: 'User approves every action before dispatch to systems' },
                { name: 'Execution Feedback', desc: 'Reports what was done, what to do next' },
              ].map((item) => (
                <div
                  key={item.name}
                  className="flex-1 flex flex-col justify-center"
                  style={{ background: '#FFFFFF', border: '1px solid #003087', borderRadius: '6px', padding: 'min(1.2vh, 10px) min(3%, 14px)' }}
                >
                  <p style={{ fontSize: fs.cardTitle, color: '#003087', fontWeight: 700, margin: '0 0 min(0.4vh, 4px) 0' }}>{item.name}</p>
                  <p style={{ fontSize: fs.cardDesc, color: '#666666', margin: 0, lineHeight: 1.45 }}>{item.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Responsible AI sidebar */}
          <div
            className="flex flex-col"
            style={{ width: 'min(24%, 220px)', flexShrink: 0, background: '#FFFFFF', border: '1.5px solid #00897B', borderRadius: '8px', padding: 'min(1.2vh, 10px) min(1.5%, 14px)' }}
          >
            <p className="flex-shrink-0" style={{ fontSize: fs.label, color: '#00897B', fontWeight: 700, letterSpacing: '1.5px', margin: '0 0 min(1.2vh, 10px) 0' }}>RESPONSIBLE AI</p>
            <div className="flex-1 flex flex-col justify-around">
              {['Human-in-the-Loop Confirmation', 'Full Action Audit Trail', 'Role-Based Execution Permissions', 'Rollback Capability'].map((item) => (
                <p key={item} style={{ fontSize: fs.cardDesc, color: '#333333', fontWeight: 600, margin: 0, lineHeight: 1.35 }}>{item}</p>
              ))}
            </div>
          </div>
        </div>

        {/* Arrow: Layer 2 → Layer 3 (UP) */}
        <UpArrow />

        {/* Layer 2: Multi-Agent Orchestration */}
        <div
          className="flex flex-col"
          style={{ flex: '2.8 1 0', minHeight: 0, background: 'rgba(0, 48, 135, 0.04)', border: '1.5px solid #003087', borderRadius: '8px', padding: 'min(1vh, 8px) min(1.2%, 12px)' }}
        >
          <div className="flex items-baseline flex-shrink-0" style={{ marginBottom: 'min(0.6vh, 6px)', gap: 'min(1vw, 12px)' }}>
            <span style={{ fontSize: fs.label, color: '#003087', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>MULTI-AGENT ORCHESTRATION</span>
            <span style={{ fontSize: fs.labelSm, color: '#666666', fontWeight: 400 }}>Persona-based micro agents dispatched to execute across systems</span>
          </div>
          <div className="flex flex-1 min-h-0" style={{ gap: 'min(0.5vw, 7px)' }}>
            {[
              { name: 'State Management', desc: 'Tracks multi-step workflows' },
              { name: 'Knowledge Graph', desc: 'Context for action decisions' },
              { name: 'Model Context Protocol', desc: 'Cross-system API dispatch' },
              { name: 'Error Recovery', desc: 'Graceful fallback on failure' },
              { name: 'Audit Trail', desc: 'Every action logged' },
            ].map((agent) => (
              <div
                key={agent.name}
                className="flex-1 flex flex-col justify-center"
                style={{ background: '#FFFFFF', border: '1px solid #003087', borderRadius: '6px', padding: 'min(1vh, 8px) min(2.5%, 12px)' }}
              >
                <p style={{ fontSize: fs.cardTitle, color: '#003087', fontWeight: 700, margin: '0 0 min(0.3vh, 3px) 0' }}>{agent.name}</p>
                <p style={{ fontSize: fs.cardDesc, color: '#666666', margin: 0, lineHeight: 1.4 }}>{agent.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Arrow: Layer 2 → Layer 1 (DOWN) — actions flow down to execution targets */}
        <DownArrow />

        {/* Layer 1 (bottom): Client Execution Targets */}
        <div
          className="flex items-center flex-nowrap"
          style={{ flex: '1.2 1 0', minHeight: 0, background: '#F4F5F7', border: '1px solid #E0E0E0', borderRadius: '6px', padding: '0 min(1.5%, 14px)', gap: 'min(1.2vw, 16px)' }}
        >
          <p className="flex-shrink-0" style={{ fontSize: fs.labelSm, color: '#666666', fontWeight: 700, letterSpacing: '1px', margin: 0, whiteSpace: 'nowrap' }}>
            {clientConfig.targetsLabel}
          </p>
          <div className="flex items-center flex-1 flex-nowrap" style={{ gap: 'min(0.4vw, 5px)', overflow: 'hidden' }}>
            {clientConfig.primaryTargets.map((src) => (
              <span
                key={src}
                className="flex-shrink-0"
                style={{ background: '#003087', color: '#FFF', fontSize: fs.pill, fontWeight: 600, padding: 'min(0.4vh, 4px) min(0.7vw, 10px)', borderRadius: '4px', whiteSpace: 'nowrap' }}
              >
                {src}
              </span>
            ))}
            {clientConfig.secondaryTargets.map((src) => (
              <span
                key={src}
                className="flex-shrink-0"
                style={{ background: '#00897B', color: '#FFF', fontSize: fs.pill, fontWeight: 600, padding: 'min(0.4vh, 4px) min(0.7vw, 10px)', borderRadius: '4px', whiteSpace: 'nowrap' }}
              >
                {src}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── BOTTOM: Gap + Proof ── */}
      <div className="flex-shrink-0" style={{ marginTop: '1vh' }}>
        <div style={{ borderBottom: '1px solid #E0E0E0', marginBottom: '1vh' }} />
        <div className="flex" style={{ gap: 'min(1vw, 10px)' }}>
          <div
            className="flex-1 flex flex-col justify-center"
            style={{ background: '#FFF8E1', border: '1px solid #F59E0B', borderRadius: '6px', padding: 'min(0.8vh, 8px) min(1.5%, 14px)' }}
          >
            <p style={{ fontSize: fs.small, color: '#333333', margin: '0 0 min(0.2vh, 2px) 0', lineHeight: 1.5 }}>
              <span style={{ fontWeight: 700 }}>The gap today: </span>
              <span>{clientConfig.gapText}</span>
            </p>
            <p style={{ fontSize: fs.small, color: '#333333', margin: 0, lineHeight: 1.5 }}>
              <span style={{ fontWeight: 700 }}>With Automated Action: </span>
              <span>{clientConfig.withText}</span>
            </p>
          </div>

          <div
            className="flex flex-col justify-center"
            style={{ width: 'min(24%, 220px)', flexShrink: 0, background: '#F4F5F7', border: '1px solid #E0E0E0', borderRadius: '6px', padding: 'min(0.8vh, 8px) min(1.5%, 14px)' }}
          >
            <p style={{ fontSize: fs.labelSm, color: '#CC0000', fontWeight: 700, letterSpacing: '1px', margin: '0 0 min(0.3vh, 3px) 0' }}>DEPLOYED AT</p>
            <p style={{ margin: '0 0 min(0.2vh, 2px) 0' }}>
              <span style={{ fontSize: fs.subtitle, color: '#003087', fontWeight: 800 }}>{clientConfig.deployedAt}</span>
            </p>
            <p style={{ fontSize: fs.small, color: '#666666', fontWeight: 400, margin: 0, lineHeight: 1.35 }}>
              {clientConfig.deployedDesc}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

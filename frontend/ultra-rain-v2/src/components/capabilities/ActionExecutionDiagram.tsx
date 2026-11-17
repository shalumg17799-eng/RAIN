import { UpArrow, DownArrow } from './FlowArrow';

/** A tenant's copy for this diagram (the manifest's `capabilityDiagrams.action`). */
export type ActionExecutionContent = {
  bodyText: string;
  targetsLabel: string;
  primaryTargets: string[];
  secondaryTargets: string[];
  deployedAt: string;
  deployedDesc: string;
  gapText: string;
  withText: string;
};

export interface ActionExecutionDiagramProps {
  /** Absent, the diagram shows the generic platform story. */
  content?: ActionExecutionContent;
  /** The client's short name. */
  clientName?: string;
}

/**
 * Capability deep-dive diagram: ActionExecution. What it says for a tenant comes in as
 * `content` (the manifest's `capabilityDiagrams.action`); without it the diagram
 * shows the generic platform story under the client's short name.
 */
// `clientName` is the client's short name, from the modal that draws the diagram.
export default function ActionExecutionDiagram({ content, clientName }: ActionExecutionDiagramProps = {}) {
  const clientShort = (clientName || 'Client').toUpperCase();

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

  const clientConfig: ActionExecutionContent = content ?? {
    bodyText: 'Move from insight to action inside the same conversation: create tickets, draft outreach, trigger Agentforce workflows, all confirmed by the user before execution.',
    targetsLabel: `${clientShort} EXECUTION TARGETS`,
    primaryTargets: ['Agentforce', 'Marketing Cloud', 'Service Cloud', 'MuleSoft'],
    secondaryTargets: ['Genesys Cloud', 'UiPath', 'JIRA', 'Slack', 'Email'],
    gapText: 'Insight lives in one system, action happens in another. Manual handoff between both.',
    withText: 'From conversation to JIRA ticket, Slack message, or Agentforce workflow in one step.',
    deployedAt: 'Radiant Solutions Lab',
    deployedDesc: 'Across multiple engagements',
  };

  return (
    <div
      className="w-full h-full flex flex-col [font-family:Inter,Helvetica,Arial,sans-serif] bg-surface p-[2.4vh_2vw_2vh]"
    >
      {/* ── TOP: Capability Identity ── */}
      <div className="flex-shrink-0 mb-[0.6vh]">
        <p style={{ fontSize: fs.eyebrow, color: 'var(--color-critical)', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', margin: '0 0 0.4vh 0' }}>
          RADIANT AI CAPABILITY
        </p>
        <h2 style={{ fontSize: fs.title, color: 'var(--color-brand)', fontWeight: 800, margin: '0 0 0.2vh 0', lineHeight: 1.15 }}>
          Automated Action
        </h2>
        <p style={{ fontSize: fs.subtitle, color: 'var(--color-text-muted)', fontWeight: 500, margin: '0 0 0.3vh 0' }}>
          Powered by ConverseAI + Agentic AI + Multi-Agent Orchestration
        </p>
        <p style={{ fontSize: fs.body, color: 'var(--color-text)', fontWeight: 400, margin: 0, lineHeight: 1.5 }}>
          {clientConfig.bodyText}
        </p>
      </div>

      <div className="border-b border-border mt-[0.6vh] mb-[1.2vh] shrink-0" />

      <p className="flex-shrink-0" style={{ fontSize: fs.labelSm, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase', margin: '0 0 0.5vh 0' }}>
        UNDERLYING ARCHITECTURE
      </p>

      {/* ── ARCHITECTURE DIAGRAM ── */}
      <div className="flex-1 min-h-0 flex flex-col">

        {/* Layer 3 (top): ConverseAI + Agentic AI + Responsible AI sidebar */}
        <div className="flex flex-[3_1_0] min-h-0 gap-[min(1vw,10px)]">
          <div
            className="flex-1 flex flex-col bg-[color-mix(in_srgb,var(--color-brand)_7%,transparent)] border-[1.5px] border-brand rounded-[8px] p-[min(1.2vh,10px)_min(1.2%,12px)]"
          >
            <div className="flex items-baseline flex-shrink-0 mb-[min(0.8vh,8px)] gap-[min(1vw,12px)]">
              <span style={{ fontSize: fs.label, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>CONVERSEAI + AGENTIC AI</span>
              <span style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 400 }}>Conversational action layer with human-in-the-loop confirmation</span>
            </div>
            <div className="flex flex-1 min-h-0 gap-[min(0.6vw,8px)]">
              {[
                { name: 'Action Planning', desc: 'AI recommends actions based on conversation context' },
                { name: 'Confirm Before Execute', desc: 'User approves every action before dispatch to systems' },
                { name: 'Execution Feedback', desc: 'Reports what was done, what to do next' },
              ].map((item) => (
                <div
                  key={item.name}
                  className="flex-1 flex flex-col justify-center bg-surface border border-brand rounded-[6px] p-[min(1.2vh,10px)_min(3%,14px)]"
                >
                  <p style={{ fontSize: fs.cardTitle, color: 'var(--color-brand)', fontWeight: 700, margin: '0 0 min(0.4vh, 4px) 0' }}>{item.name}</p>
                  <p style={{ fontSize: fs.cardDesc, color: 'var(--color-text-muted)', margin: 0, lineHeight: 1.45 }}>{item.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Responsible AI sidebar */}
          <div
            className="flex flex-col w-[min(24%,220px)] shrink-0 bg-surface border-[1.5px] border-verified rounded-[8px] p-[min(1.2vh,10px)_min(1.5%,14px)]"
          >
            <p className="flex-shrink-0" style={{ fontSize: fs.label, color: 'var(--color-verified)', fontWeight: 700, letterSpacing: '1.5px', margin: '0 0 min(1.2vh, 10px) 0' }}>RESPONSIBLE AI</p>
            <div className="flex-1 flex flex-col justify-around">
              {['Human-in-the-Loop Confirmation', 'Full Action Audit Trail', 'Role-Based Execution Permissions', 'Rollback Capability'].map((item) => (
                <p key={item} style={{ fontSize: fs.cardDesc, color: 'var(--color-text)', fontWeight: 600, margin: 0, lineHeight: 1.35 }}>{item}</p>
              ))}
            </div>
          </div>
        </div>

        {/* Arrow: Layer 2 → Layer 3 (UP) */}
        <UpArrow />

        {/* Layer 2: Multi-Agent Orchestration */}
        <div
          className="flex flex-col flex-[2.8_1_0] min-h-0 bg-[color-mix(in_srgb,var(--color-brand)_4%,transparent)] border-[1.5px] border-brand rounded-[8px] p-[min(1vh,8px)_min(1.2%,12px)]"
        >
          <div className="flex items-baseline flex-shrink-0 mb-[min(0.6vh,6px)] gap-[min(1vw,12px)]">
            <span style={{ fontSize: fs.label, color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '1.5px', whiteSpace: 'nowrap' }}>MULTI-AGENT ORCHESTRATION</span>
            <span style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 400 }}>Persona-based micro agents dispatched to execute across systems</span>
          </div>
          <div className="flex flex-1 min-h-0 gap-[min(0.5vw,7px)]">
            {[
              { name: 'State Management', desc: 'Tracks multi-step workflows' },
              { name: 'Knowledge Graph', desc: 'Context for action decisions' },
              { name: 'Model Context Protocol', desc: 'Cross-system API dispatch' },
              { name: 'Error Recovery', desc: 'Graceful fallback on failure' },
              { name: 'Audit Trail', desc: 'Every action logged' },
            ].map((agent) => (
              <div
                key={agent.name}
                className="flex-1 flex flex-col justify-center bg-surface border border-brand rounded-[6px] p-[min(1vh,8px)_min(2.5%,12px)]"
              >
                <p style={{ fontSize: fs.cardTitle, color: 'var(--color-brand)', fontWeight: 700, margin: '0 0 min(0.3vh, 3px) 0' }}>{agent.name}</p>
                <p style={{ fontSize: fs.cardDesc, color: 'var(--color-text-muted)', margin: 0, lineHeight: 1.4 }}>{agent.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Arrow: Layer 2 → Layer 1 (DOWN) — actions flow down to execution targets */}
        <DownArrow />

        {/* Layer 1 (bottom): Client Execution Targets */}
        <div
          className="flex items-center flex-nowrap flex-[1.2_1_0] min-h-0 bg-bg border border-border rounded-[6px] p-[0_min(1.5%,14px)] gap-[min(1.2vw,16px)]"
        >
          <p className="flex-shrink-0" style={{ fontSize: fs.labelSm, color: 'var(--color-text-muted)', fontWeight: 700, letterSpacing: '1px', margin: 0, whiteSpace: 'nowrap' }}>
            {clientConfig.targetsLabel}
          </p>
          <div className="flex items-center flex-1 flex-nowrap gap-[min(0.4vw,5px)] overflow-hidden">
            {clientConfig.primaryTargets.map((src) => (
              <span
                key={src}
                className="flex-shrink-0"
                style={{ background: 'var(--color-brand)', color: 'var(--color-text-inverse)', fontSize: fs.pill, fontWeight: 600, padding: 'min(0.4vh, 4px) min(0.7vw, 10px)', borderRadius: '4px', whiteSpace: 'nowrap' }}
              >
                {src}
              </span>
            ))}
            {clientConfig.secondaryTargets.map((src) => (
              <span
                key={src}
                className="flex-shrink-0"
                style={{ background: 'var(--color-verified)', color: 'var(--color-text-inverse)', fontSize: fs.pill, fontWeight: 600, padding: 'min(0.4vh, 4px) min(0.7vw, 10px)', borderRadius: '4px', whiteSpace: 'nowrap' }}
              >
                {src}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── BOTTOM: Gap + Proof ── */}
      <div className="flex-shrink-0 mt-[1vh]">
        <div className="border-b border-border mb-[1vh]" />
        <div className="flex gap-[min(1vw,10px)]">
          <div
            className="flex-1 flex flex-col justify-center bg-warning-50 border border-warning-500 rounded-[6px] p-[min(0.8vh,8px)_min(1.5%,14px)]"
          >
            <p style={{ fontSize: fs.small, color: 'var(--color-text)', margin: '0 0 min(0.2vh, 2px) 0', lineHeight: 1.5 }}>
              <span className="font-bold">The gap today: </span>
              <span>{clientConfig.gapText}</span>
            </p>
            <p style={{ fontSize: fs.small, color: 'var(--color-text)', margin: 0, lineHeight: 1.5 }}>
              <span className="font-bold">With Automated Action: </span>
              <span>{clientConfig.withText}</span>
            </p>
          </div>

          <div
            className="flex flex-col justify-center w-[min(24%,220px)] shrink-0 bg-bg border border-border rounded-[6px] p-[min(0.8vh,8px)_min(1.5%,14px)]"
          >
            <p style={{ fontSize: fs.labelSm, color: 'var(--color-critical)', fontWeight: 700, letterSpacing: '1px', margin: '0 0 min(0.3vh, 3px) 0' }}>Developed By</p>
            <p className="m-[0_0_min(0.2vh,2px)_0]">
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

import { motion } from 'framer-motion';
import { Bot } from 'lucide-react';
import { usePersona } from '../../context/PersonaContext';
import SourceBadge from './SourceBadge';
import CapabilityBadge from './CapabilityBadge';

export default function ChatMessage({ message, inlineComponents, capability, onCapabilityClick }) {
  const persona = usePersona();
  const isUser = message.role === 'user';
  const confidence = !isUser ? message.confidence : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`flex items-start gap-3 ${isUser ? 'justify-end' : ''}`}
    >
      {/* AI avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-[#003087]/[0.12] flex items-center justify-center flex-shrink-0 mt-0.5">
          <Bot className="w-4 h-4 text-[#003087]/70" />
        </div>
      )}

      <div className={`max-w-[85%] ${isUser ? 'order-first' : ''}`}>
        {/* Message bubble */}
        <div
          className={`rounded-2xl px-5 py-3.5 text-sm leading-relaxed ${
            isUser
              ? 'bg-gradient-to-br from-[#003087] to-[#0045b0] text-white rounded-tr-md shadow-[0_2px_8px_rgba(0,48,135,0.2)]'
              : 'bg-white text-gray-800 rounded-tl-md border border-gray-200/70'
          }`}
          style={!isUser ? { boxShadow: '0 1px 6px rgba(0,0,0,0.06)' } : {}}
        >
          {message.text.split('\n').map((line, i) => {
            if (!line.trim()) return <div key={i} className="h-2.5" />;

            // Style lines that start with [SourceName]
            const bracketMatch = line.match(/^\[(.+?)\]\s*(.*)$/);
            if (bracketMatch && !isUser) {
              return (
                <p key={i} className="mb-1.5">
                  <span className="font-semibold text-[#003087]">[{bracketMatch[1]}]</span>{' '}
                  <span className="text-gray-700">{bracketMatch[2]}</span>
                </p>
              );
            }

            // Style numbered list items
            const numberedMatch = line.match(/^\[(\d+)\]\s*(.*)$/);
            if (numberedMatch && !isUser) {
              return (
                <p key={i} className="mb-1.5">
                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-[#003087]/10 text-[#003087] text-[10px] font-bold mr-1.5">{numberedMatch[1]}</span>
                  <span className="text-gray-700">{numberedMatch[2]}</span>
                </p>
              );
            }

            // Style dash-prefixed items
            const dashMatch = line.match(/^—\s*(.*)$/);
            if (dashMatch && !isUser) {
              return (
                <p key={i} className="mb-1 pl-3 relative text-gray-700">
                  <span className="absolute left-0 top-0 text-[#003087]/30">—</span>
                  {dashMatch[1]}
                </p>
              );
            }

            return <p key={i} className="mb-1.5 last:mb-0">{line}</p>;
          })}
        </div>

        {/* Capability tag row (clickable → architecture deep-dive) */}
        {!isUser && capability && onCapabilityClick && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <CapabilityBadge capability={capability} onClick={onCapabilityClick} />
          </div>
        )}

        {/* Inline components */}
        {inlineComponents && inlineComponents.length > 0 && (
          <div className="mt-3 space-y-3">
            {inlineComponents.map((comp, idx) => (
              <div key={idx}>{comp}</div>
            ))}
          </div>
        )}

        {/* Source badges */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2.5 pl-0.5">
            <div className="flex flex-wrap gap-1.5">
              {message.sources.map((source, idx) => (
                <SourceBadge key={idx} source={source} />
              ))}
            </div>
          </div>
        )}
        {/* Governed-agent trace: the pipeline stages that ran for this answer */}
        {!isUser && message.agentTrace && message.agentTrace.length > 0 && (
          <details className="mt-2 pl-0.5">
            <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wider text-[#003087]/50 hover:text-[#003087]/80">
              Agent steps ({message.agentTrace.filter((e) => e.type === 'stage_finished').length} stages)
            </summary>
            <div className="mt-1.5 rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2 font-mono text-[10px] leading-relaxed text-gray-600">
              {message.agentTrace.map((e, i) => {
                const branch = e.branch ? `[${e.branch}] ` : '';
                if (e.type === 'graph_definition') return <div key={i} className="text-[#003087]">## {e.agent_name} v{e.agent_version}: {e.steps.join(' → ')}</div>;
                if (e.type === 'supervisor_decision') return <div key={i} className="text-violet-700">?? picked {e.skill} for {e.stage} ({e.reason}{e.considered && e.considered.length > 1 ? `; considered ${e.considered.join(', ')}` : ''})</div>;
                if (e.type === 'stage_started') return <div key={i}>&gt;&gt; {branch}{e.step_id} - {e.skill}</div>;
                if (e.type === 'stage_finished') {
                  const tok = e.tokens ? (e.tokens.prompt_tokens || 0) + (e.tokens.completion_tokens || 0) : 0;
                  return <div key={i}>&lt;&lt; {branch}{e.step_id} -&gt; {String(e.label)} ({e.duration_ms} ms{tok ? `, ${tok} tok` : ''})</div>;
                }
                if (e.type === 'agent_iteration') return <div key={i} className="text-gray-400">&nbsp;&nbsp;.. iteration {e.iteration}</div>;
                if (e.type === 'tool_call') return <div key={i} className="text-gray-400">&nbsp;&nbsp;.. tool {e.tool} {e.status}</div>;
                if (e.type === 'progress') return <div key={i} className="text-gray-400">&nbsp;&nbsp;.. {e.note}{e.count != null ? `=${e.count}` : ''}</div>;
                if (e.type === 'refine') return <div key={i} className="text-amber-600">~~ loop-back #{e.attempt} ({String(e.label)})</div>;
                if (e.type === 'hitl_waiting') return <div key={i} className="text-amber-600">?! human review requested ({e.reason})</div>;
                if (e.type === 'hitl_decided') return <div key={i} className="text-amber-700">?! review {String(e.label)}</div>;
                if (e.type === 'run_finished') return <div key={i} className="text-[#003087]">== {e.outcome} in {e.duration_ms} ms</div>;
                return null;
              })}
            </div>
          </details>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center flex-shrink-0 mt-0.5 border border-gray-200/60">
          <span className="text-gray-600 text-[10px] font-bold">{persona.initials}</span>
        </div>
      )}
    </motion.div>
  );
}

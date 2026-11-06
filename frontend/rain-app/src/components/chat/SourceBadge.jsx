const sourceColors = {
  'UiPath':                             { dot: 'bg-warning-400', text: 'text-text-muted' },
  'Salesforce Data Cloud':              { dot: 'bg-info-400',   text: 'text-text-muted' },
  'Salesforce Einstein':                { dot: 'bg-indigo-400', text: 'text-text-muted' },
  'Salesforce AgentForce':              { dot: 'bg-purple-400', text: 'text-text-muted' },
  'Salesforce AgentForce & Einstein':   { dot: 'bg-purple-400', text: 'text-text-muted' },
  'Genesys Cloud':                      { dot: 'bg-success-400',text: 'text-text-muted' },
  'USSFCU Member CRM':                  { dot: 'bg-cyan-400',   text: 'text-text-muted' },
  'PenFed Member CRM':                  { dot: 'bg-cyan-400',   text: 'text-text-muted' },
  'Web & Mobile Behavioral Analytics':  { dot: 'bg-warning-400',  text: 'text-text-muted' },
  'Voice of Member / NPS':              { dot: 'bg-teal-400',   text: 'text-text-muted' },
  'Fraud & Risk Signal Feed':           { dot: 'bg-critical-400',    text: 'text-text-muted' },
  'All connected sources':              { dot: 'bg-text-subtle',   text: 'text-text-muted' },
};

const defaultColor = { dot: 'bg-text-subtle', text: 'text-text-muted' };

export default function SourceBadge({ source }) {
  const colors = sourceColors[source] || defaultColor;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[10px] font-medium ${colors.text} bg-surface-2 border border-border-subtle/60`}>
      <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
      {source}
    </span>
  );
}

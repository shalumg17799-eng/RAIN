interface SourceColor {
  dot: string;
  text: string;
}

const sourceColors: Record<string, SourceColor | undefined> = {
  'UiPath':                             { dot: 'bg-warning-400', text: 'text-text-muted' },
  'Salesforce Data Cloud':              { dot: 'bg-info-400',   text: 'text-text-muted' },
  'Salesforce Einstein':                { dot: 'bg-category4-400', text: 'text-text-muted' },
  'Salesforce AgentForce':              { dot: 'bg-category5-400', text: 'text-text-muted' },
  'Salesforce AgentForce & Einstein':   { dot: 'bg-category5-400', text: 'text-text-muted' },
  'Genesys Cloud':                      { dot: 'bg-success-400',text: 'text-text-muted' },
  'Web & Mobile Behavioral Analytics':  { dot: 'bg-warning-400',  text: 'text-text-muted' },
  'Voice of Member / NPS':              { dot: 'bg-category3-400',   text: 'text-text-muted' },
  'Fraud & Risk Signal Feed':           { dot: 'bg-critical-400',    text: 'text-text-muted' },
  'All connected sources':              { dot: 'bg-text-subtle',   text: 'text-text-muted' },
};

const defaultColor = { dot: 'bg-text-subtle', text: 'text-text-muted' };
/** Any client's member CRM ("<Client> Member CRM"), matched by kind so no client is named here. */
const memberCrmColor = { dot: 'bg-category2-400', text: 'text-text-muted' };

export interface SourceBadgeProps {
  source?: string;
}

export default function SourceBadge({ source }: SourceBadgeProps) {
  const colors = (source ? sourceColors[source] : undefined) || (source?.endsWith(' Member CRM') ? memberCrmColor : defaultColor);

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[10px] font-medium ${colors.text} bg-surface-2 border border-border-subtle/60`}>
      <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
      {source}
    </span>
  );
}

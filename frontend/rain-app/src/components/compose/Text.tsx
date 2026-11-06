/** Tier 3 text and callout blocks. Plain words; colour comes from status tokens. */
import { AlertTriangle, CheckCircle2, Info, OctagonAlert, CircleMinus } from 'lucide-react';
import { toStatus, type Status } from '@core/contract/status';

export interface TextProps {
  text: string;
  tone?: 'default' | 'muted';
  size?: 'sm' | 'md';
}

export function Text({ text, tone = 'default', size = 'sm' }: TextProps) {
  return (
    <p className={`${size === 'md' ? 'text-sm' : 'text-[13px]'} leading-relaxed ${tone === 'muted' ? 'text-text-muted' : 'text-text'}`}>
      {text}
    </p>
  );
}

const CALLOUT: Record<Status, { box: string; icon: typeof Info; text: string }> = {
  good: { box: 'border-success/30 bg-success-subtle', icon: CheckCircle2, text: 'text-success' },
  warning: { box: 'border-warning/30 bg-warning-subtle', icon: AlertTriangle, text: 'text-warning' },
  critical: { box: 'border-critical/30 bg-critical-subtle', icon: OctagonAlert, text: 'text-critical' },
  info: { box: 'border-info/30 bg-info-subtle', icon: Info, text: 'text-info' },
  neutral: { box: 'border-border bg-surface-2', icon: CircleMinus, text: 'text-text-muted' },
};

export interface CalloutProps {
  title: string;
  body?: string;
  status?: string;
}

export function Callout({ title, body, status = 'info' }: CalloutProps) {
  const c = CALLOUT[toStatus(status, 'info')];
  const Icon = c.icon;
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 ${c.box}`}>
      <Icon className={`mt-0.5 h-4 w-4 flex-shrink-0 ${c.text}`} aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-[13px] font-semibold text-text">{title}</p>
        {body && <p className="mt-0.5 text-xs leading-relaxed text-text-muted">{body}</p>}
      </div>
    </div>
  );
}

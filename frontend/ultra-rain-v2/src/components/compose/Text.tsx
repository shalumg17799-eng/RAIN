/** Tier 3 text and callout blocks. Plain words; colour comes from status tokens. */
import { AlertTriangle, ArrowRight, CheckCircle2, Info, OctagonAlert, CircleMinus } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { toStatus, type Status } from '@core/contract/status';

export interface TextProps {
  text: string;
  tone?: 'default' | 'muted';
  size?: 'sm' | 'md';
  /** Makes the text a link: an in-app route or a public https address. */
  href?: string;
}

/** An in-app route as a router link, anything else as a new-tab link. */
function Linked({ href, className, children }: { href: string; className: string; children: ReactNode }) {
  return href.startsWith('/') ? (
    <Link to={href} className={className}>{children}</Link>
  ) : (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>{children}</a>
  );
}

export function Text({ text, tone = 'default', size = 'sm', href }: TextProps) {
  return (
    <p className={`${size === 'md' ? 'text-sm' : 'text-[13px]'} leading-relaxed ${tone === 'muted' ? 'text-text-muted' : 'text-text'}`}>
      {href ? <Linked href={href} className="text-brand underline-offset-2 hover:underline">{text}</Linked> : text}
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
  /** A link button under the body. */
  action?: { label: string; href: string };
}

export function Callout({ title, body, status = 'info', action }: CalloutProps) {
  const c = CALLOUT[toStatus(status, 'info')];
  const Icon = c.icon;
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 ${c.box}`}>
      <Icon className={`mt-0.5 h-4 w-4 flex-shrink-0 ${c.text}`} aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-[13px] font-semibold text-text">{title}</p>
        {body && <p className="mt-0.5 text-xs leading-relaxed text-text-muted">{body}</p>}
        {action && (
          <Linked href={action.href} className="mt-2 inline-flex items-center gap-1 rounded-lg border border-brand/30 bg-brand/[0.05] px-2.5 py-1 text-[11.5px] font-semibold text-brand hover:bg-brand/10">
            {action.label}
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Linked>
        )}
      </div>
    </div>
  );
}

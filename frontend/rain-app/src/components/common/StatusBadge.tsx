import { toKitStatus } from '@core/contract/status';
// The KPI kit's badge (word + icon + token colour, WCAG 1.4.1) is the one
// badge; this wrapper only lets it accept any status spelling.
import { StatusBadge as KitStatusBadge } from '../kpi/Badges';

export interface StatusBadgeProps {
  /** A standard status, any legacy spelling (`ok`, `amber`, `pass`…), or a 0–100 health score. */
  status: string | number;
  /** Text to show; defaults to the value given. */
  label?: string;
  size?: 'sm' | 'lg';
  className?: string;
}

/** StatusBadge — the one way a state is drawn (standard rule 7). */
export default function StatusBadge({ status, label, size = 'sm', className = '' }: StatusBadgeProps) {
  const text = label ?? String(status);
  return <KitStatusBadge status={toKitStatus(status)} label={text} size={size} className={className} />;
}

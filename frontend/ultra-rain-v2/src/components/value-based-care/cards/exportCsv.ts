import { COUNTIES, STATE } from '@/data/rain/_shared/constants';

/** The RHTP county rows as CSV; counts under the privacy floor are left blank. */
export function countyCsv(): string {
  const head = ['County', 'Members in view', 'BP control %', 'Avoidable ED per 1,000', 'Primary care visit change since January %', 'Low-value care $', 'Heart failure members'];
  const rows = COUNTIES.map((c) => [c.name, c.members, c.bpControlPct, c.edPer1000, c.pcVisitChangePct, c.lowValue, c.heartFailure < STATE.suppressUnder ? '' : c.heartFailure]);
  return [head, ...rows].map((r) => r.map((v) => `"${String(v)}"`).join(',')).join('\n');
}

export function downloadCountyCsv() {
  const blob = new Blob([countyCsv()], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'rhtp-progress-by-county.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}


function GaugeChart({ score, maxScore, status }) {
  const pct = (score / maxScore) * 100;
  const color = status === 'amber' ? 'var(--color-warning-500)' : status === 'green' ? 'var(--color-success)' : 'var(--color-critical)';

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-32 h-16 overflow-hidden">
        <svg viewBox="0 0 120 60" className="w-full h-full">
          {/* Background arc */}
          <path d="M 10 55 A 50 50 0 0 1 110 55" fill="none" stroke="var(--color-border)" strokeWidth="8" strokeLinecap="round" />
          {/* Filled arc */}
          <path
            d="M 10 55 A 50 50 0 0 1 110 55"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${pct * 1.57} 157`}
          />
        </svg>
        <div className="absolute inset-0 flex items-end justify-center pb-0">
          <span className="text-2xl font-bold text-text">{score}</span>
          <span className="text-xs text-text-subtle ml-0.5 mb-1">/{maxScore}</span>
        </div>
      </div>
    </div>
  );
}

/** Props: { riskExtras } */
export function CreditRiskCard({ riskExtras }) {
  const data = riskExtras.creditRiskPosture;
  return (
    <div className="bg-surface rounded-xl border border-border-subtle p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text">{data.title}</h3>
        <span className="px-2 py-0.5 rounded-full bg-success-50 text-success-800 text-[10px] font-semibold">
          {data.overallScore}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="text-center p-2 rounded-lg bg-surface-2">
          <p className="text-lg font-bold text-text">{(data.delinquencyRate30Day * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-text-muted">30-Day Delinquency</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-surface-2">
          <p className="text-lg font-bold text-text">{(data.delinquencyRate60Day * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-text-muted">60-Day Delinquency</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-surface-2">
          <p className="text-lg font-bold text-text">{(data.delinquencyRate90Day * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-text-muted">90-Day Delinquency</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-surface-2">
          <p className="text-lg font-bold text-text">{(data.chargeOffRate * 100).toFixed(2)}%</p>
          <p className="text-[10px] text-text-muted">Charge-Off Rate</p>
        </div>
      </div>
      <p className="text-[11px] text-text-subtle mt-3 text-center">{data.comparedToIndustry}</p>
    </div>
  );
}

/** Props: { riskExtras } */
export function RegulatoryReadinessCard({ riskExtras }) {
  const data = riskExtras.regulatoryReadiness;
  return (
    <div className="bg-surface rounded-xl border border-border-subtle p-5">
      <h3 className="text-sm font-semibold text-text mb-4">{data.title}</h3>
      <GaugeChart score={data.score} maxScore={data.maxScore} status={data.status} />
      <div className="mt-4 grid grid-cols-2 gap-3 text-center">
        <div className="p-2 rounded-lg bg-surface-2">
          <p className="text-lg font-bold text-warning-600">{data.openFindings}</p>
          <p className="text-[10px] text-text-muted">Open Findings</p>
        </div>
        <div className="p-2 rounded-lg bg-surface-2">
          <p className="text-lg font-bold text-success-600">{data.closedFindings}</p>
          <p className="text-[10px] text-text-muted">Closed Findings</p>
        </div>
      </div>
      <p className="text-[11px] text-text-subtle mt-3 text-center">
        Next exam window: {data.nextExamWindow}
      </p>
    </div>
  );
}

/** Props: { riskSignals } */
export function AMLClustersCard({ riskSignals }) {
  const data = riskSignals.aml_clusters;
  return (
    <div className="bg-surface rounded-xl border border-border-subtle p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-text">BSA/AML Clusters</h3>
          <p className="text-xs text-text-subtle mt-0.5">{data.count} suspicious activity clusters</p>
        </div>
        <span className="px-2 py-1 rounded-full bg-critical-50 text-critical-800 text-[10px] font-semibold uppercase">
          {data.severity}
        </span>
      </div>
      <div className="space-y-3">
        {data.clusters.map((c) => (
          <div key={c.cluster_id} className="p-3 rounded-lg bg-critical-50/50 border border-critical-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono text-text-subtle">{c.cluster_id}</span>
              <span className="text-[10px] font-bold text-critical-600">Risk: {c.risk_score}</span>
            </div>
            <p className="text-xs text-text font-medium mb-1">{c.pattern}</p>
            <div className="flex items-center justify-between text-[10px] text-text-muted">
              <span>{c.total_amount} | {c.accounts_involved} accounts</span>
              <span className={`font-medium ${c.sar_filed ? 'text-critical-500' : 'text-warning-500'}`}>
                {c.sar_filed ? 'SAR Filed' : 'Preliminary'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

import { motion } from 'framer-motion';
import { Database, Brain, Headphones, Cog, Users, Monitor, MessageCircle, Shield, TrendingUp, Cpu, Star, AlertTriangle, Route, FileText, ShieldCheck } from 'lucide-react';

/**
 * The Data Sources page body: a heading, the persona's posture panel (what is
 * real, what is illustrative), and a card per source. The persona's sources
 * come from its manifest (`dataSources`) and its panel from
 * `pages.dataSourcesPanel` — the screen names no tenant.
 *
 * Props: { sources, panel?: ReactNode, heading?, subtitle? }
 */
const iconMap = {
  database: Database,
  brain: Brain,
  headphones: Headphones,
  cog: Cog,
  users: Users,
  monitor: Monitor,
  'message-circle': MessageCircle,
  shield: Shield,
  // Additional icons used by the PenFed capmarkets data sources.
  'trending-up': TrendingUp,
  cpu: Cpu,
  star: Star,
  'alert-triangle': AlertTriangle,
  // Additional icons used by the ESFCU CEO data sources.
  route: Route,
  'file-text': FileText,
  'shield-check': ShieldCheck,
};

/**
 * How long before the dataset's newest sync a source last synced. Measured
 * against the data's own "as of", not the wall clock: the fixtures carry fixed
 * dates, and reading them against today printed "5148h ago" and grew daily.
 * A source with no usable time shows a dash.
 */
function formatSyncTime(isoString, asOf) {
  const t = isoString ? new Date(isoString).getTime() : NaN;
  if (Number.isNaN(t) || asOf == null) return '—';
  const diffMins = Math.max(0, Math.floor((asOf - t) / 60000));
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  return `${Math.floor(diffMins / 60)}h ago`;
}

function formatRecordCount(count) {
  if (count == null) return '—';
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(0)}K`;
  return count.toString();
}

export default function DataSourcesPage({
  sources,
  panel = null,
  heading = 'Connected Data Sources',
  subtitle = `${sources.length} integrations powering the AI intelligence layer`,
}) {
  const dataSources = sources;
  // The dataset's own "as of": its newest sync time.
  const syncTimes = sources.map((ds) => new Date(ds.lastSync).getTime()).filter((t) => !Number.isNaN(t));
  const asOf = syncTimes.length ? Math.max(...syncTimes) : null;
  return (
    <div className="flex-1 py-8 px-4 sm:px-6 lg:px-8 overflow-y-auto scrollbar-sleek">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-text mb-1">{heading}</h2>
        <p className="text-sm text-text-subtle">{subtitle}</p>
      </div>

      {panel}

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-5">
        {dataSources.map((ds, idx) => {
          const Icon = iconMap[ds.icon] || Database;
          return (
            <motion.div
              key={ds.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: idx * 0.06 }}
              className="bg-surface rounded-xl border border-border-subtle p-5 hover:shadow-md hover:border-border transition-all"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-brand/5 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-brand" />
                </div>
                <span className={`flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider ${
                  ds.status === 'connected' ? 'text-success-700' : 'text-warning-700'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${
                    ds.status === 'connected' ? 'bg-success-600' : 'bg-warning-500'
                  }`} />
                  {/* `statusLabel` lets a registry name its own states (SCLAC:
                      Exists, Partial, Not collected, Unknown). Absent elsewhere. */}
                  {ds.statusLabel ?? (ds.status === 'connected' ? 'Connected' : 'Partial')}
                </span>
              </div>

              {/* Name + Description */}
              <h3 className="text-sm font-semibold text-text mb-1.5 leading-tight">{ds.name}</h3>
              {ds.vendorAgnostic && (
                <span className="inline-block mb-1.5 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide text-text-muted">
                  Vendor-agnostic
                </span>
              )}
              <p className="text-xs text-text-muted leading-relaxed mb-4">{ds.description}</p>

              {/* Metrics */}
              <div className="flex items-center justify-between pt-3 border-t border-border-subtle">
                <div className="text-[10px] text-text-subtle">
                  <span className="font-medium text-text-muted">{formatRecordCount(ds.recordCount)}</span> records
                </div>
                <div className="text-[10px] text-text-subtle">
                  {/* Prefer an authored freshness string when the fixture supplies
                      one — a scripted demo shouldn't drift as the wall clock moves. */}
                  Last sync: <span className="font-medium text-text-muted">{ds.freshness || formatSyncTime(ds.lastSync, asOf)}</span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

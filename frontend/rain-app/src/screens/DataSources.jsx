import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Database, Brain, Headphones, Cog, Users, Monitor, MessageCircle, Shield, TrendingUp, Cpu, Star, AlertTriangle, HeartPulse, Activity } from 'lucide-react';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

const iconMap = {
  database: Database,
  brain: Brain,
  headphones: Headphones,
  cog: Cog,
  users: Users,
  monitor: Monitor,
  'message-circle': MessageCircle,
  shield: Shield,
  'trending-up': TrendingUp,
  cpu: Cpu,
  star: Star,
  'alert-triangle': AlertTriangle,
  // Additional icons used by the RAIN rural-health data sources.
  'heart-pulse': HeartPulse,
  activity: Activity,
};

function formatSyncTime(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  return `${diffHours}h ago`;
}

function formatRecordCount(count) {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(0)}K`;
  return count.toString();
}

export default function DataSources() {
  // All RAIN personas share the same 11 rural Nevada health system
  // integrations -- one fetch, independent of which persona is active.
  const [dataSources, setDataSources] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/ultra/rain/dataSources`)
      .then((r) => r.json())
      .then(setDataSources)
      .catch(() => setDataSources([]));
  }, []);

  return (
    <div className="flex-1 py-8 px-4 sm:px-8 overflow-y-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Connected Data Sources</h2>
        <p className="text-sm text-gray-400">{dataSources.length} integrations powering the AI intelligence layer</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-5">
        {dataSources.map((ds, idx) => {
          const Icon = iconMap[ds.icon] || Database;
          return (
            <motion.div
              key={ds.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: idx * 0.06 }}
              className="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-md hover:border-gray-200 transition-all"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-[#003087]/5 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-[#003087]" />
                </div>
                <span className={`flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider ${
                  ds.status === 'connected' ? 'text-[#00897B]' : 'text-[#F59E0B]'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${
                    ds.status === 'connected' ? 'bg-[#00897B]' : 'bg-[#F59E0B]'
                  }`} />
                  {ds.status === 'connected' ? 'Connected' : 'Partial'}
                </span>
              </div>

              {/* Name + Description */}
              <h3 className="text-sm font-semibold text-gray-800 mb-1.5 leading-tight">{ds.name}</h3>
              <p className="text-xs text-gray-500 leading-relaxed mb-4">{ds.description}</p>

              {/* Metrics */}
              <div className="flex items-center justify-between pt-3 border-t border-gray-50">
                <div className="text-[10px] text-gray-400">
                  {ds.volumeLabel
                    ? <span className="font-medium text-gray-500">{ds.volumeLabel}</span>
                    : <><span className="font-medium text-gray-500">{formatRecordCount(ds.recordCount)}</span> records</>}
                </div>
                <div className="text-[10px] text-gray-400">
                  Last sync: <span className="font-medium text-gray-500">{formatSyncTime(ds.lastSync)}</span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

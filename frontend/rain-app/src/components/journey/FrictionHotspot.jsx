import { motion } from 'framer-motion';
import { AlertTriangle, AlertCircle } from 'lucide-react';
import SourceBadge from '../chat/SourceBadge';

const severityConfig = {
  critical: { icon: AlertTriangle, color: 'text-critical-500', border: 'border-critical-200', bg: 'bg-critical-50/50', dot: 'bg-critical-500' },
  warning: { icon: AlertCircle, color: 'text-warning-500', border: 'border-warning-200', bg: 'bg-warning-50/50', dot: 'bg-warning-500' },
};

export default function FrictionHotspot({ hotspot, index }) {
  const config = severityConfig[hotspot.severity] || severityConfig.warning;
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className={`rounded-xl border ${config.border} ${config.bg} p-5`}
    >
      <div className="flex items-start gap-3">
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`w-2.5 h-2.5 rounded-full ${config.dot}`} />
          <Icon className={`w-4 h-4 ${config.color}`} />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-text mb-1.5">{hotspot.title}</h4>
          <p className="text-xs text-text-muted leading-relaxed mb-3">{hotspot.description}</p>
          <div className="flex flex-wrap gap-1.5">
            {hotspot.sources.map((source, idx) => (
              <SourceBadge key={idx} source={source} />
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

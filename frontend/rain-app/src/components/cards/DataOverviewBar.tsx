import { AnimatePresence, motion } from 'framer-motion';
import { ICONS } from '@core/contract/icons';
import { tileIcon } from '@core/contract/tone';
import type { ComponentType } from 'react';
import type { StatTile } from '@core/types';

type IconLike = ComponentType<{ className?: string }>;

interface StatCardProps {
  stat: StatTile;
  index: number;
  onClick?: (chip: string) => void;
}

function StatCard({ stat, index, onClick }: StatCardProps) {
  // An icon registry id (the contract form) or, from older manifests, the component itself.
  const Icon = (typeof stat.icon === 'string' ? ICONS[stat.icon] : stat.icon) as IconLike;
  const isClickable = !!stat.chipText;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.05, ease: 'easeOut' }}
      onClick={isClickable ? () => onClick?.(stat.chipText as string) : undefined}
      className={`flex-1 min-w-[150px] rounded-lg px-2.5 py-2 bg-surface border border-border-subtle/80 ${
        isClickable
          ? 'cursor-pointer hover:border-brand/15 hover:shadow-[0_2px_8px_color-mix(in_srgb,var(--color-brand)_6%,transparent)] transition-all duration-200'
          : ''
      }`}
      style={{ boxShadow: '0 1px 2px rgba(0,0,0,0.03)' }}
    >
      <div className="flex items-center gap-2 min-w-0">
        {/* Icon — fixed size, never shrinks */}
        <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${tileIcon(stat).bg}`}>
          <Icon className={`w-3 h-3 ${tileIcon(stat).color}`} />
        </div>

        {/* Text block — stacked vertically, each line truncates independently */}
        <div className="min-w-0 flex-1 flex flex-col gap-[2px]">
          <span className="text-[13px] font-bold text-text leading-none truncate">
            {stat.value}
          </span>
          <span className="text-[9px] text-text-subtle font-medium leading-none truncate">
            {stat.label}
          </span>
          {/* tone 'neutral': a descriptive line (SCLAC's data labels), neither good nor bad news. */}
          <span className={`text-[8.5px] font-semibold leading-none truncate ${
            stat.tone === 'neutral' ? 'text-text-muted' : stat.positive ? 'text-success-600' : 'text-warning-600'
          }`}>
            {stat.trend}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

export interface DataOverviewBarProps {
  visible?: boolean;
  /** Called with a tile's chip when a clickable tile is pressed. */
  onStatClick?: (chip: string) => void;
  stats?: StatTile[];
}

export default function DataOverviewBar({ visible, onStatClick, stats }: DataOverviewBarProps) {
  if (!stats || stats.length === 0) return null;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, height: 'auto' }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0, marginBottom: 0, overflow: 'hidden' }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
          className="mb-3"
        >
          <div className="flex flex-wrap gap-2">
            {stats.map((stat, idx) => (
              <StatCard
                key={stat.id}
                stat={stat}
                index={idx}
                onClick={onStatClick}
              />
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const PAGE_SIZE = 4;

function StatCard({ stat, index, onClick }) {
  const Icon = stat.icon;
  const isClickable = !!stat.chipText;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.05, ease: 'easeOut' }}
      onClick={isClickable ? () => onClick(stat.chipText) : undefined}
      className={`min-w-0 rounded-lg px-2.5 py-2 bg-white border border-gray-100/80 ${
        isClickable
          ? 'cursor-pointer hover:border-[#003087]/15 hover:shadow-[0_2px_8px_rgba(0,48,135,0.06)] transition-all duration-200'
          : ''
      }`}
      style={{ boxShadow: '0 1px 2px rgba(0,0,0,0.03)' }}
    >
      <div className="flex items-center gap-2 min-w-0">
        {/* Icon — fixed size, never shrinks */}
        <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${stat.iconBg}`}>
          <Icon className={`w-3 h-3 ${stat.iconColor}`} />
        </div>

        {/* Text block — stacked vertically, each line truncates independently */}
        <div className="min-w-0 flex-1 flex flex-col gap-[2px]">
          <span className="text-[13px] font-bold text-gray-900 leading-none truncate">
            {stat.value}
          </span>
          <span className="text-[9px] text-gray-400 font-medium leading-none truncate">
            {stat.label}
          </span>
          <span className={`text-[8.5px] font-semibold leading-none truncate ${
            stat.positive ? 'text-emerald-600' : 'text-amber-600'
          }`}>
            {stat.trend}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

export default function DataOverviewBar({ visible, onStatClick, stats }) {
  const [page, setPage] = useState(0);
  const total = stats?.length || 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  if (!stats || total === 0) return null;

  const paginated = pageCount > 1;
  // Clamp defensively in case the stat set shrank (persona switch resets via the
  // `key` prop on this component, so page normally starts at 0).
  const safePage = Math.min(page, pageCount - 1);
  const start = safePage * PAGE_SIZE;
  const pageStats = paginated ? stats.slice(start, start + PAGE_SIZE) : stats;

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
          {/* 4-up grid (desktop) when paginated so tile width stays consistent across
              pages; collapses to a 2-up grid on mobile so tiles stay readable at 390px. */}
          <div className={paginated ? 'grid grid-cols-2 lg:grid-cols-4 gap-2' : 'grid grid-cols-2 lg:flex gap-2'}>
            {pageStats.map((stat, idx) => (
              <StatCard
                key={stat.id}
                stat={stat}
                index={idx}
                onClick={onStatClick}
              />
            ))}
          </div>

          {paginated && (
            <div className="flex items-center justify-center gap-3 mt-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(0, Math.min(p, pageCount - 1) - 1))}
                disabled={safePage === 0}
                aria-label="Previous KPIs"
                className="w-6 h-6 rounded-full flex items-center justify-center border border-gray-200 text-gray-500 hover:text-[#003087] hover:border-[#003087]/30 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>

              <div className="flex items-center gap-1.5">
                {Array.from({ length: pageCount }).map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setPage(i)}
                    aria-label={`KPI page ${i + 1}`}
                    className={`h-1.5 rounded-full transition-all ${
                      i === safePage ? 'w-4 bg-[#003087]' : 'w-1.5 bg-gray-300 hover:bg-gray-400'
                    }`}
                  />
                ))}
                <span className="ml-1.5 text-[10px] font-semibold text-gray-400 tabular-nums">
                  {safePage + 1} / {pageCount}
                </span>
              </div>

              <button
                type="button"
                onClick={() => setPage((p) => Math.min(pageCount - 1, Math.min(p, pageCount - 1) + 1))}
                disabled={safePage === pageCount - 1}
                aria-label="Next KPIs"
                className="w-6 h-6 rounded-full flex items-center justify-center border border-gray-200 text-gray-500 hover:text-[#003087] hover:border-[#003087]/30 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

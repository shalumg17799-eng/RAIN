import { motion } from 'framer-motion';
import { usePersonaPage } from '@core/runtime/usePersonaPage';

/**
 * /my-reports — where a saved report goes.
 *
 * A persona that saves reports declares its page as `pages.myReports` (the
 * DoIT Author and Administrator, the AMISA Director). Only personas that list
 * `myReports` in `features.navSlots` reach it from the sidebar; anyone else who
 * types the URL gets an explicit empty state rather than a blank page.
 */
export default function MyReports() {
  const { ready, Page } = usePersonaPage('myReports');
  if (!ready) return null;
  if (Page) return <Page />;

  return (
    <div className="flex-1 overflow-y-auto scrollbar-sleek px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h2 className="mb-1 text-lg font-semibold text-text">My Reports</h2>
        <p className="text-sm text-text-subtle">Reports you have saved.</p>
      </div>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
        <div className="rounded-2xl border border-dashed border-border bg-surface p-8 text-center">
          <p className="text-[13.5px] font-semibold text-text">Nothing saved here</p>
          <p className="mt-1 text-[12.5px] text-text-muted">
            This persona does not save reports.
          </p>
        </div>
      </motion.div>
    </div>
  );
}

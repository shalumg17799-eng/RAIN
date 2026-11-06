// @ultra-shell: the app shell. Rule 5 lets the shell read context.
import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import PageErrorBoundary from '../common/PageErrorBoundary';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './Sidebar';
import TopHeader from './TopHeader';
import { IntradayProvider, useIntraday } from '@/context/IntradayContext';
import useBriefingBaseline from '@/hooks/useBriefingBaseline';
import { useActiveManifest } from '@core/runtime/useActiveManifest';
import StickyIntelligenceWidget from '../intelligence/StickyIntelligenceWidget';
import { CriticalAlertProvider, useCriticalAlert } from '@/context/CriticalAlertContext';
import { ConversationSessionProvider } from '@/context/ConversationSessionContext';

// Inner shell — runs *inside* IntradayProvider so it can mount hooks/components
// that consume the intraday context (baseline loader, sticky widget).
function ShellInner() {
  const location = useLocation();
  const manifest = useActiveManifest();
  const { baseline, widgetExpanded, briefingActive } = useIntraday();
  useBriefingBaseline();

  // Mobile off-canvas sidebar. Closes automatically on route change.
  const [navOpen, setNavOpen] = useState(false);
  const [navPath, setNavPath] = useState(location.pathname);
  if (location.pathname !== navPath) {
    setNavPath(location.pathname);
    setNavOpen(false);
  }

  // Mirror StickyIntelligenceWidget's gating so <main> reserves space for the
  // exact widget state on screen. The widget itself is desktop-only (lg+), so
  // the reserved margin is `lg:` — on mobile the main column is full-width.
  // Only personas whose manifest declares a `briefing` own the widget.
  const personaAllowed = !!manifest?.briefing;
  const widgetVisible = personaAllowed && !!baseline;
  const widgetIsRail = widgetVisible && (!widgetExpanded || briefingActive);
  const widgetIsExpanded = widgetVisible && !widgetIsRail;
  const mainMargin = widgetIsExpanded
    ? 'lg:mr-[360px]'
    : widgetIsRail
    ? 'lg:mr-11'
    : '';

  // The HSE GM's incident drawer is a column, not an overlay: when it is open
  // the app gives up width for it rather than being pushed down or covered by
  // it. That is what lets the alert arrive open, stay open across navigation,
  // and never cost the conversation its scroll position.
  //
  // Reserved on the whole right-hand column rather than on `<main>` alone,
  // because the drawer is full height — it spans the header and the alert strip
  // too. Margin on `<main>` only, and the drawer covers the persona switcher,
  // the notification bell, and the strip's own "Back to conversation" button:
  // the one control that exists to undo a trip the incident sent her on.
  //
  // Only on `lg` and up — below that the drawer takes the screen as a sheet, so
  // there is nothing to reserve. Inert for every persona but the HSE GM, whose
  // alert is the only one that ever reports `active`.
  const { active: alertActive, open: alertOpen } = useCriticalAlert();
  const alertDrawerOpen = alertActive && alertOpen;

  // A persona's floating route assistant (manifest `shell.routeAssistant`; the
  // NFCU platform admin's, on its four non-Ask pages). When it's up, reserve
  // bottom space so the fixed bar never covers page content — same principle
  // as the widget margin above.
  const routeAssistant = manifest?.shell?.routeAssistant;
  const assistantVisible = !!routeAssistant && routeAssistant.routes.includes(location.pathname);
  const RouteAssistant = routeAssistant?.component;
  const AlertBand = manifest?.shell?.alertBand;
  const AlertDrawer = manifest?.shell?.alertDrawer;

  return (
    <div className="h-[100dvh] bg-bg flex overflow-hidden">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div
        className={`flex-1 flex flex-col min-w-0 relative transition-[margin] duration-200 ease-out ${
          alertDrawerOpen ? 'lg:mr-[440px]' : ''
        }`}
      >
        <TopHeader onMenuClick={() => setNavOpen(true)} />
        {/* One line, never more: the incident detail lives in the drawer
            below, so this strip only ever costs the page its own height. It
            renders on every route because the incident outlives navigation.
            Inert for every other persona. */}
        {AlertBand && <AlertBand />}
        <main
          className={`flex-1 overflow-y-auto transition-[margin] duration-200 ease-out ${mainMargin}`}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className={`flex flex-col h-full ${assistantVisible ? 'pb-32' : ''}`}
            >
              <PageErrorBoundary resetKey={location.pathname} label="page">
                <Outlet />
              </PageErrorBoundary>
            </motion.div>
          </AnimatePresence>
        </main>
        <StickyIntelligenceWidget />
        {/* Fixed to the viewport, so it spans the full height beside the page
            rather than living inside the scrolling column. */}
        {AlertDrawer && <AlertDrawer />}
        {assistantVisible && (
          <RouteAssistant key={location.pathname} route={location.pathname} />
        )}
      </div>
    </div>
  );
}

export default function AppShell() {
  return (
    <IntradayProvider>
      <CriticalAlertProvider>
        {/* Above the routes, so a persona's thread outlives the `/ask` route
            element it is rendered by. Inert for every persona that has not set
            `features.persistConversation`. */}
        <ConversationSessionProvider>
          <ShellInner />
        </ConversationSessionProvider>
      </CriticalAlertProvider>
    </IntradayProvider>
  );
}

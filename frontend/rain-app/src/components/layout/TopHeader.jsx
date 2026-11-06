// @ultra-shell: the shell header (persona switcher, page title). Rule 5 lets the shell read context.
import { useState, useCallback, useRef, useEffect, useSyncExternalStore } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Play, ChevronDown, LogOut, Menu } from 'lucide-react';
import { RUN_GUIDED_DEMO } from '@/demo.config';
import DemoRunner from '@/demo/DemoRunner';
import DemoOverlay from '@/demo/DemoOverlay';
import { usePersona, usePersonaList } from '@/context/PersonaContext';
import { useClient } from '@/context/ClientContext';
import { useSession } from '@/context/SessionContext';
import { useBranding } from '@/context/BrandingContext';
import { loginPathForClientId } from '@/config/access';
import { useActiveManifest } from '@core/runtime/useActiveManifest';
import NotificationBell from './NotificationBell';
import { useCriticalAlert } from '@/context/CriticalAlertContext';
import { useActivePersona } from '@core/runtime/useActivePersona';

const EMPTY = [];
const NO_SUBSCRIBE = () => () => {};
const NO_ITEMS = () => EMPTY;

export default function TopHeader({ onMenuClick }) {
  const persona = usePersona();
  // A persona's own header control (manifest `shell.headerExtra`, e.g. Newfold's brand filter).
  const HeaderExtra = useActiveManifest()?.shell?.headerExtra;
  // The HSE GM's live safety alert gets a second home in the bell, so it is
  // reachable after she collapses the band. Empty for every other persona.
  const { notifications: criticalAlertNotifications } = useCriticalAlert();
  const personaList = usePersonaList();
  const { clearClient } = useClient();
  const { signOut } = useSession();
  const { client, clientId } = useBranding();
  const { manifest: activeManifest } = useActivePersona(clientId, persona?.id);
  // Items a persona's store adds while it is in use (manifest `notificationSource`); none for everyone else.
  const source = activeManifest?.notificationSource;
  const liveNotifications = useSyncExternalStore(source?.subscribe ?? NO_SUBSCRIBE, source?.getSnapshot ?? NO_ITEMS, source?.getSnapshot ?? NO_ITEMS);
  const location = useLocation();
  const navigate = useNavigate();
  // Page titles use the same labels as the sidebar: defaults, then the client's
  // navLabels, then the active persona manifest's own relabels.
  const labels = {
    ...{ journey: 'Member Journey', risk: 'Risk Signals' },
    ...client?.navLabels,
    ...activeManifest?.navLabels,
  };
  const pageTitles = {
    '/': labels.ask || 'Ask the AI',
    '/ask': labels.ask || 'Ask the AI',
    '/journey': labels.journey,
    '/risk': labels.risk,
    '/governance': labels.governance || client?.navLabels?.governance || 'Model Governance',
    '/agent-observability': labels.agentObservability || 'Agent Observability',
    '/catalog': 'Component catalog',
    '/agent-inventory': labels.agentInventory || 'Agent Inventory',
    // Oil & Gas / HSE routes — labels come from the client's navLabels.
    '/live-site': labels.liveSite || 'Live Site Picture',
    '/permits': labels.permits || 'Permit and Job Detail',
    '/muster': labels.muster || 'Muster Status',
    // Telecom / AI Billing Workbench routes — labels come from navLabels.
    '/patterns': labels.patterns || 'Patterns',
    '/dashboard': labels.dashboard || 'Dashboard',
    '/history': labels.history || 'Resolution History',
    '/admin': labels.adminConsole || 'Platform Administration',
    // ESFCU risk/fraud route.
    '/fraud-operations': labels.fraudOperations || 'Fraud Operations',
    // SLED / VOCE — where a saved report lives.
    '/my-reports': labels.myReports || 'My Reports',
    // SLED / Comptroller of Maryland pages.
    '/plan': labels.audiencePlan || 'Audience Plan',
    '/package': labels.packageReview || 'Package',
    '/approve': labels.approvalBoard || 'Approval Board',
    '/publish': labels.channelSchedule || 'Channel Schedule',
    '/measure': labels.results || 'Results',
    // SLED / Comptroller of Maryland v3 pages.
    '/exec': labels.execView || 'Executive View',
    '/fraud': labels.fraudWorkspace || 'Fraud Workspace',
    '/warehouse': labels.warehouseHealth || 'Data Health and Lineage',
    '/cases': labels.caseFiles || 'Cases',
    '/data-foundation': labels.dataFoundation || 'Architecture',
    // SLED / Superior Court of Los Angeles County pages.
    '/cx-program': labels.cxProgram || 'CX Program',
    '/scorecard': labels.scorecard || 'Strategic Plan Scorecard',
    '/feedback-loop': labels.feedbackLoop || 'Feedback Loop',
    '/architecture': labels.architecture || 'Architecture',
    '/kri-panel': labels.kriPanel || 'KRI panel',
    '/divisions': labels.divisionSpaces || 'Division spaces',
    '/courthouses': labels.courthouseComparison || 'Courthouse comparison',
    '/transformation': labels.transformation || 'Strategy and Transformation',
    // Telecom / Lyte Corporate Intelligence pages.
    '/churn': labels.churnRetention || 'Churn and Retention',
    '/competitive': labels.competitiveDynamics || 'Competitive Dynamics',
    '/expansion': labels.marketExpansion || 'Market and Expansion',
    '/onboarding': labels.acquisitionOnboarding || 'Data Foundation',
    '/platform': labels.platformArchitecture || 'Architecture',
    // SLED / RAIN value-based care workbenches.
    '/value-insights': labels.valueInsights || 'Value Insights',
    '/quality-gate': labels.qualityGate || 'Quality Gate and Campaigns',
    '/low-value-care': labels.lowValueCare || 'Low-Value Care',
    '/model-governance': labels.modelGovernance || 'Model Governance',
    '/county-explorer': labels.countyExplorer || 'County Explorer',
    '/rhtp-reporting': labels.rhtpReporting || 'RHTP Reporting',
    '/worklist': labels.worklist || 'Worklist',
    '/scheduling': labels.scheduling || 'Scheduling',
    '/reminders': labels.reminders || 'Reminders',
    // USSFCU Finance (Fiona) pages.
    '/portfolio-risk': labels.portfolioRisk || 'Portfolio and Limits',
    '/scenarios': labels.scenarios || 'Scenarios and Modeling',
    '/data-sources': 'Data Sources',
  };
  // SCLAC's Measure detail is the one parameterised page (/kpi/<measure>).
  const title = pageTitles[location.pathname] || (location.pathname.startsWith('/kpi/') ? 'Measure detail' : null) || labels.ask || 'Ask the AI';
  const [demoRunning, setDemoRunning] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [dropdownOpen]);

  const handlePersonaSwitch = (personaId) => {
    setDropdownOpen(false);
    const params = new URLSearchParams(location.search);
    params.set('persona', personaId);
    navigate(`${location.pathname}?${params.toString()}`, { replace: true });
  };

  const handleStartDemo = useCallback(() => {
    setDemoRunning(true);
    DemoRunner.start();
  }, []);

  const handleStopDemo = useCallback(() => {
    setDemoRunning(false);
    DemoRunner.stop();
  }, []);

  // A real sign out: drop the session AND the selected client, landing back on
  // the login screen. Both are needed — clearing only the client would return
  // to the picker while still signed in.
  //
  // You leave by the door of the client you are IN, not the one you came in by.
  // Signing out of Aramco shows Aramco's sign-in page whether you reached it
  // through that client's own link or picked it inside Ultra — the tenant on
  // screen is the tenant you are leaving. The platform door is where the app
  // *starts*, not where a client's session ends; see `LOCKED_REDIRECT_PATH`.
  //
  // Handing the door to `signOut` rather than navigating here is deliberate:
  // clearing the session re-renders the route guard first, and whatever that
  // guard decides wins. See `exitPath` in SessionContext.
  const handleSignOut = () => {
    setDropdownOpen(false);
    clearClient();
    // Falls back to the platform door for a client with no gate of its own.
    signOut(loginPathForClientId(clientId));
  };

  return (
    <>
      <header className="h-16 bg-surface border-b border-border-subtle flex items-center justify-between px-4 sm:px-6 lg:px-8 relative z-50 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 -ml-2 rounded-xl text-text-muted hover:bg-surface-2 transition-colors flex-shrink-0"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="text-base font-bold text-text tracking-tight truncate">{title}</h1>
        </div>

        <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
          {/* Brand-context selector — Newfold Digital only (portfolio of 80+ brands) */}
          {HeaderExtra && <HeaderExtra />}

          {/* Run Guided Demo button — hidden via flag; functionality preserved for later re-enable */}
          {RUN_GUIDED_DEMO === 'yes' && !demoRunning && (
            <button
              onClick={handleStartDemo}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-brand/25 text-brand text-xs font-semibold hover:bg-brand/[0.04] hover:border-brand/40 transition-all cursor-pointer"
            >
              <Play className="w-3.5 h-3.5" />
              Run Guided Demo
            </button>
          )}

          {/* Notifications. Content is whatever the active persona manifest
              declares; a persona with nothing to say shows no badge rather than
              the hardcoded "3" this carried for every tenant. */}
          <NotificationBell items={[...criticalAlertNotifications, ...(activeManifest?.notifications ?? []), ...liveNotifications]} />

          {/* Divider */}
          <div className="w-px h-8 bg-surface-2" />

          {/* User / Persona Switcher */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              className="flex items-center gap-3 px-2 py-1.5 -mx-2 rounded-xl hover:bg-surface-2 transition-colors cursor-pointer"
            >
              <div className="w-9 h-9 rounded-xl bg-brand flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0">
                {persona.initials}
              </div>
              <div className="text-right hidden sm:block max-w-[160px]">
                <p className="text-sm font-semibold text-text leading-tight truncate">{persona.name}</p>
                <p className="text-[10px] text-text-subtle leading-tight font-medium truncate">{persona.role}</p>
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-text-subtle transition-transform flex-shrink-0 ${dropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Dropdown */}
            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-64 bg-surface rounded-xl border border-border shadow-xl z-[60] overflow-hidden">
                <div className="px-3 py-2 border-b border-border-subtle">
                  <p className="text-[10px] font-semibold text-text-subtle uppercase tracking-wider">Switch Persona</p>
                </div>
                <div className="py-1">
                  {personaList.map((p) => {
                    const isActive = p.id === persona.id;
                    return (
                      <button
                        key={p.id}
                        onClick={() => !isActive && handlePersonaSwitch(p.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors ${
                          isActive
                            ? 'bg-brand/[0.06] cursor-default'
                            : 'hover:bg-surface-2 cursor-pointer'
                        }`}
                      >
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                          isActive
                            ? 'bg-brand text-white'
                            : 'bg-surface-2 text-text-muted'
                        }`}>
                          {p.initials}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`flex flex-wrap items-center gap-1 text-xs font-semibold leading-tight ${isActive ? 'text-brand' : 'text-text'}`}>
                            {p.name}
                            {/* Some personas are real, named people (ESFCU's CEO
                                is) and some are representative stand-ins for a
                                role whose real holder is not public. Sharing one
                                dropdown, they are indistinguishable — so the
                                invented ones say so. */}
                            {p.illustrativePersona ? (
                              <span
                                className="rounded bg-surface-2 px-1 py-px text-[8px] font-bold uppercase tracking-wide text-text-subtle"
                                title="Representative persona — not a real named individual"
                              >
                                Illustrative
                              </span>
                            ) : null}
                          </p>
                          <p className="text-[10px] text-text-subtle leading-tight">{p.role}</p>
                        </div>
                        {isActive && (
                          <span className="text-[9px] font-bold text-brand bg-brand/10 px-1.5 py-0.5 rounded">ACTIVE</span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Sign Out — returns to the client picker. */}
                <div className="border-t border-border-subtle p-1.5">
                  <button
                    onClick={handleSignOut}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-critical-50 transition-colors group cursor-pointer"
                  >
                    <div className="w-8 h-8 rounded-lg bg-surface-2 group-hover:bg-critical-100 flex items-center justify-center flex-shrink-0 transition-colors">
                      <LogOut className="w-3.5 h-3.5 text-text-muted group-hover:text-critical-500 transition-colors" />
                    </div>
                    <span className="text-xs font-semibold text-text-muted group-hover:text-critical-600 transition-colors">Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <DemoOverlay
        isRunning={demoRunning}
        onStart={handleStartDemo}
        onStop={handleStopDemo}
      />
    </>
  );
}

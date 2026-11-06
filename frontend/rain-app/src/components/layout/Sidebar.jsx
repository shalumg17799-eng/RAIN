// @ultra-shell: the shell sidebar (nav from the active persona). Rule 5 lets the shell read context.
import { NavLink, useLocation } from 'react-router-dom';
import { BellRing, CalendarPlus, ClipboardList, Database, FileText, Map as MapIcon, MessageSquare, ShieldAlert, ShieldCheck, Target, TrendingUp, X } from 'lucide-react';
import { useBranding } from '@/context/BrandingContext';
import { usePersona } from '@/context/PersonaContext';
import { useActivePersona } from '@core/runtime/useActivePersona';

export default function Sidebar({ open = false, onClose }) {
  const location = useLocation();
  const { client, clientId } = useBranding();
  const persona = usePersona();
  // Nav is data-driven by the active persona's manifest (nav relabels +
  // focused-nav flag), falling back to the client's default labels. No tenant or
  // persona ids appear here — that's the North Star seam.
  const { manifest } = useActivePersona(clientId, persona?.id);

  const labels = {
    ...{ journey: 'Member Journey', risk: 'Risk Signals' },
    ...client?.navLabels,
    ...manifest?.navLabels,
  };
  const navSlots = manifest?.features?.navSlots;

  // Every nav slot the app can render, keyed by NavKey. `navSlots` (an explicit
  // ordered allow-list on the persona) selects and orders a subset of these.
  const NAV_SLOTS = {
    // A client with its own landing page sends `/` there, so its Ask link must
    // go to /ask directly. Everyone else keeps `/`.
    ask: { to: client.homePath ? '/ask' : '/', icon: MessageSquare, label: labels.ask ?? 'Ask the AI' },
    // SLED / RAIN value-based care workbenches.
    valueInsights: { to: '/value-insights', icon: TrendingUp, label: labels.valueInsights ?? 'Value Insights' },
    qualityGate: { to: '/quality-gate', icon: Target, label: labels.qualityGate ?? 'Quality Gate and Campaigns' },
    lowValueCare: { to: '/low-value-care', icon: ShieldAlert, label: labels.lowValueCare ?? 'Low-Value Care' },
    modelGovernance: { to: '/model-governance', icon: ShieldCheck, label: labels.modelGovernance ?? 'Model Governance' },
    countyExplorer: { to: '/county-explorer', icon: MapIcon, label: labels.countyExplorer ?? 'County Explorer' },
    rhtpReporting: { to: '/rhtp-reporting', icon: FileText, label: labels.rhtpReporting ?? 'RHTP Reporting' },
    worklist: { to: '/worklist', icon: ClipboardList, label: labels.worklist ?? 'Worklist' },
    scheduling: { to: '/scheduling', icon: CalendarPlus, label: labels.scheduling ?? 'Scheduling' },
    reminders: { to: '/reminders', icon: BellRing, label: labels.reminders ?? 'Reminders' },
    dataSources: { to: '/data-sources', icon: Database, label: 'Data Sources' },
  };

  const navItems = Array.isArray(navSlots)
    ? navSlots.map((k) => NAV_SLOTS[k]).filter(Boolean)
    : [NAV_SLOTS.ask, NAV_SLOTS.dataSources];

  return (
    <>
      {/* Mobile backdrop — above the header (z-50) so the drawer overlays it */}
      {open && (
        <div
          className="fixed inset-0 z-[55] bg-black/40 backdrop-blur-[1px] lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed lg:static inset-y-0 left-0 z-[60] lg:z-30 w-[264px] flex-shrink-0 bg-surface border-r border-border-subtle flex flex-col h-[100dvh] transition-transform duration-300 ease-out lg:translate-x-0 ${
          open ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:shadow-none'
        }`}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-border-subtle/80">
          <div className="flex items-center gap-2.5 min-w-0">
            <img src={client.logo} alt={client.name} className="w-11 h-11 flex-shrink-0 object-contain" />
            <div className="flex flex-col min-w-0" style={{ gap: 0 }}>
              {client.nameLines.map((line, i) => (
                <span key={i} className="text-brand font-bold text-[11px] tracking-tight truncate" style={{ lineHeight: '1.2' }}>{line}</span>
              ))}
              <span className="text-[8.5px] font-semibold text-text-subtle uppercase tracking-widest truncate" style={{ lineHeight: '1.2', marginTop: '1px' }}>{client.tagline}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 -mr-1 rounded-lg text-text-subtle hover:bg-surface-2 hover:text-text-muted transition-colors"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

      {/* Navigation */}
      <nav className="flex-1 py-5 px-3 overflow-y-auto scrollbar-sleek">
        <p className="text-[9px] font-bold text-text-subtle uppercase tracking-widest px-3 mb-3">Navigation</p>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.to) || (!!item.alsoActive && location.pathname.startsWith(item.alsoActive));
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-brand text-white shadow-[0_2px_8px_color-mix(in_srgb,var(--color-brand)_25%,transparent)]'
                      : 'text-text-muted hover:bg-surface-2 hover:text-text'
                  }`}
                >
                  <Icon className="w-[18px] h-[18px]" />
                  {item.label}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

        {/* Footer — Radiant by default. A client whose demo leads with its own
            product brand supplies `footerMark` and that takes this slot. */}
        <div className="px-5 py-4 border-t border-border-subtle/80">
          {client.footerMark ? (
            <div className="flex flex-col gap-1 min-w-0">
              {client.footerMark.label && (
                <span className="text-[9.5px] text-text-subtle">{client.footerMark.label}</span>
              )}
              {/* h-8: these lockups are stacked (mark above wordmark), so they
                  need more height than a horizontal mark to stay legible. */}
              <img
                src={client.footerMark.logo}
                alt={client.footerMark.alt}
                className="h-8 w-auto object-contain self-start"
              />
            </div>
          ) : (
            <p className="text-[10px] text-text-subtle">
              Powered by <span className="font-semibold text-text-muted">Radiant Digital</span>
            </p>
          )}
        </div>
      </aside>
    </>
  );
}

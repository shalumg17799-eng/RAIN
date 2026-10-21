import { NavLink, useLocation } from 'react-router-dom';
import { MessageSquare, Route, ShieldAlert, Database, FileText } from 'lucide-react';
import { useBranding } from '../../context/BrandingContext';

// Nav labels come from the RAIN manifest (Rural Health Intelligence +
// Care & Risk Signals).
function resolveNavLabels(client) {
  return client?.navLabels ?? { journey: 'Member Journey', risk: 'Risk Signals' };
}

export default function Sidebar({ open = false, onClose = () => {} }) {
  const location = useLocation();
  const { client } = useBranding();
  const labels = resolveNavLabels(client);

  const navItems = [
    { to: '/', icon: MessageSquare, label: 'Ask the AI' },
    { to: '/journey', icon: Route, label: labels.journey },
    { to: '/risk', icon: ShieldAlert, label: labels.risk },
    { to: '/data-sources', icon: Database, label: 'Data Sources' },
    { to: '/prd', icon: FileText, label: 'PRD Studio' },
  ];

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-[60] w-[260px] flex-shrink-0 bg-white border-r border-gray-100 flex flex-col transition-transform duration-200 ease-out lg:static lg:z-30 lg:translate-x-0 ${
        open ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
      }`}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-gray-100/80">
        <div className="flex items-center gap-2.5">
          <img src={client.logo} alt={client.name} className="h-11 w-auto max-w-[72px] flex-shrink-0 object-contain" />
          <div className="flex flex-col" style={{ gap: 0 }}>
            {client.nameLines.map((line, i) => (
              <span key={i} className="text-[#003087] font-bold text-[11px] tracking-tight" style={{ lineHeight: '1.2' }}>{line}</span>
            ))}
            <span className="text-[8.5px] font-semibold text-gray-400 uppercase tracking-widest" style={{ lineHeight: '1.2', marginTop: '1px' }}>{client.tagline}</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-5 px-3 overflow-y-auto scrollbar-sleek">
        <p className="text-[9px] font-bold text-gray-400 uppercase tracking-widest px-3 mb-3">Navigation</p>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.to);
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  onClick={onClose}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-[#003087] text-white shadow-[0_2px_8px_rgba(0,48,135,0.25)]'
                      : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
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

      {/* Footer */}
      <div className="px-5 py-4 border-t border-gray-100/80">
        <p className="text-[10px] text-gray-400">
          Powered by <span className="font-semibold text-gray-500">Radiant Digital</span>
        </p>
      </div>
    </aside>
  );
}

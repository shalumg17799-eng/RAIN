import { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, ChevronDown, LogOut, Menu } from 'lucide-react';
import { usePersona, usePersonaList } from '../../context/PersonaContext';
import { useAuth } from '../../context/AuthContext';
import { useBranding } from '../../context/BrandingContext';

export default function TopHeader({ onMenuClick = () => {} }) {
  const persona = usePersona();
  const personaList = usePersonaList();
  const { logout } = useAuth();
  const { client } = useBranding();
  const location = useLocation();
  const navigate = useNavigate();
  // Nav labels come from the RAIN manifest.
  const labels = client?.navLabels ?? { journey: 'Member Journey', risk: 'Risk Signals' };
  const pageTitles = {
    '/': 'Ask the AI',
    '/ask': 'Ask the AI',
    '/prd': 'PRD Studio',
    '/journey': labels.journey,
    '/risk': labels.risk,
    '/data-sources': 'Data Sources',
  };
  const title = pageTitles[location.pathname] || 'Ask the AI';
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

  const handleLogout = () => {
    setDropdownOpen(false);
    logout();
  };

  return (
    <>
      <header className="h-16 bg-white border-b border-gray-100 flex items-center justify-between px-4 lg:px-8 relative z-50">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 -ml-2 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer"
            aria-label="Open navigation"
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <h1 className="text-base font-bold text-gray-900 tracking-tight truncate">{title}</h1>
        </div>

        <div className="flex items-center gap-3 lg:gap-4">
          {/* Notification Bell */}
          <button className="relative p-2 rounded-xl hover:bg-gray-50 transition-colors">
            <Bell className="w-5 h-5 text-gray-400" />
            <span className="absolute -top-0.5 -right-0.5 w-4.5 h-4.5 bg-red-500 text-white text-[9px] font-bold flex items-center justify-center rounded-full min-w-[18px] min-h-[18px]">
              3
            </span>
          </button>

          {/* Divider */}
          <div className="w-px h-8 bg-gray-100" />

          {/* User / Persona Switcher */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              className="flex items-center gap-3 px-2 py-1.5 -mx-2 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer"
            >
              <div className="w-9 h-9 rounded-xl bg-[#003087] flex items-center justify-center text-white text-[11px] font-bold">
                {persona.initials}
              </div>
              <div className="text-right hidden sm:block max-w-[200px]">
                <p className="text-sm font-semibold text-gray-800 leading-tight truncate">{persona.name}</p>
                <p className="text-[10px] text-gray-400 leading-tight font-medium truncate">{persona.role}</p>
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Dropdown */}
            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-64 bg-white rounded-xl border border-gray-200 shadow-xl z-[60] overflow-hidden">
                <div className="px-3 py-2 border-b border-gray-100">
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Switch Persona</p>
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
                            ? 'bg-[#003087]/[0.06] cursor-default'
                            : 'hover:bg-gray-50 cursor-pointer'
                        }`}
                      >
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                          isActive
                            ? 'bg-[#003087] text-white'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          {p.initials}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs font-semibold leading-tight ${isActive ? 'text-[#003087]' : 'text-gray-800'}`}>
                            {p.name}
                          </p>
                          <p className="text-[10px] text-gray-400 leading-tight">{p.role}</p>
                        </div>
                        {isActive && (
                          <span className="text-[9px] font-bold text-[#003087] bg-[#003087]/10 px-1.5 py-0.5 rounded">ACTIVE</span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Sign Out */}
                <div className="border-t border-gray-100 p-1.5">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-red-50 transition-colors group cursor-pointer"
                  >
                    <div className="w-8 h-8 rounded-lg bg-gray-100 group-hover:bg-red-100 flex items-center justify-center flex-shrink-0 transition-colors">
                      <LogOut className="w-3.5 h-3.5 text-gray-500 group-hover:text-red-500 transition-colors" />
                    </div>
                    <span className="text-xs font-semibold text-gray-600 group-hover:text-red-600 transition-colors">Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>
    </>
  );
}

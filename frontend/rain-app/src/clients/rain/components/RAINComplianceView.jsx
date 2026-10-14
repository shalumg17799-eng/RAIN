import { useEffect, useState } from 'react';
import {
  Baby, HeartPulse, CalendarCheck, MapPin, Bus, Ambulance, Video,
  Users, AlertTriangle, Droplet, Pill, Wifi,
  Map, Truck, Layers, Building2,
  DollarSign, Activity, WifiOff,
  Database, ShieldCheck, UserX, Clock,
} from 'lucide-react';
import SignalCard from '@/components/cards/SignalCard';
import { personaUIConfigs } from '@/clients/personaConfigs';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

// Ultra's persona ids -> the backend's shorter persona ids.
const PERSONA_ID_MAP = {
  rain_delgado: 'maria',
  rain_whitehorse: 'sarah',
  rain_tomley: 'james',
  rain_nair: 'priya',
  rain_yazzie: 'david',
};

// KPI icon name (string, from the backend) -> the real lucide-react
// component. Same pattern DataSources.jsx already uses for its icons --
// a component reference can't be sent over JSON, so the backend sends the
// name and this maps it back.
export const KPI_ICON_MAP = {
  Baby, HeartPulse, CalendarCheck, MapPin, Bus, Ambulance, Video,
  Users, AlertTriangle, Droplet, Pill, Wifi,
  Map, Truck, Layers, Building2,
  DollarSign, Activity, WifiOff,
  Database, ShieldCheck, UserX, Clock,
};

/**
 * RAIN "Care & Risk Signals" / "Rural Health Intelligence" dashboard panels —
 * composed from each persona's priority signals + KPIs (per the spec's page
 * descriptions). Fetches from the backend; falls back to an empty list on
 * error or for an unmapped persona id.
 */
export function RAINPriorityCards({ personaId, onSignalClick }) {
  const [signals, setSignals] = useState([]);

  useEffect(() => {
    const backendId = PERSONA_ID_MAP[personaId];
    if (!backendId) {
      setSignals([]);
      return;
    }
    fetch(`${API_BASE}/ultra/rain/${backendId}/signals`)
      .then((r) => r.json())
      .then(setSignals)
      .catch(() => setSignals([]));
  }, [personaId]);

  // Position-based lookup (1st/2nd/3rd signal), not by exact id string --
  // the live backend's signal ids (SIG-RAIN-SARAH-001) use a different
  // naming convention than Ultra's own static signalToChip map
  // (SIG-RAIN-WHITEHORSE-001), so an id-string match always misses.
  // Verified the signal order matches the same real signal on both sides.
  const signalToChip = personaUIConfigs[personaId]?.signalToChip || {};
  const chipKeys = Object.keys(signalToChip);

  return (
    <div className="space-y-3">
      {signals.map((s, idx) => {
        const chipText = chipKeys[idx] ? signalToChip[chipKeys[idx]] : null;
        return (
          <SignalCard
            key={s.id}
            signal={s}
            onClick={chipText && onSignalClick ? () => onSignalClick(chipText) : undefined}
          />
        );
      })}
    </div>
  );
}

export function RAINKpiCards({ personaId }) {
  const [stats, setStats] = useState([]);

  useEffect(() => {
    const backendId = PERSONA_ID_MAP[personaId];
    if (!backendId) {
      setStats([]);
      return;
    }
    fetch(`${API_BASE}/ultra/rain/${backendId}/kpis`)
      .then((r) => r.json())
      .then(setStats)
      .catch(() => setStats([]));
  }, [personaId]);

  return (
    <div className="grid grid-cols-2 gap-3">
      {stats.map((stat) => {
        const Icon = KPI_ICON_MAP[stat.icon];
        return (
          <div key={stat.id} className="bg-white rounded-xl border border-gray-200 p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <div className={`w-7 h-7 rounded-lg ${stat.iconBg} flex items-center justify-center`}>
                {Icon ? <Icon className={`w-3.5 h-3.5 ${stat.iconColor}`} /> : null}
              </div>
              <p className="text-[10px] font-semibold text-gray-500 leading-tight">{stat.label}</p>
            </div>
            <p className="text-lg font-bold text-gray-900 leading-none">{stat.value}</p>
            <p className="text-[10px] text-gray-400 mt-1">{stat.trend}</p>
          </div>
        );
      })}
    </div>
  );
}

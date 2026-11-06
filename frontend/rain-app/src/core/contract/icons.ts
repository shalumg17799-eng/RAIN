/**
 * The icon registry (standard rule 6: no display details in data).
 *
 * Data names an icon by a kebab-case id (`"alert-triangle"`); the frontend
 * decides what that id looks like. This is what lets a KPI tile or a signal
 * arrive from the backend as plain JSON — a lucide component cannot be sent
 * over an API.
 *
 * `resolveIcon` accepts either an id or, for manifests not yet migrated, the
 * component itself, so both work during the transition.
 */
import type { ComponentType } from 'react';
import {
  Activity, AlertTriangle, ArrowLeftRight, Award, BadgeDollarSign, BarChart3, BedDouble, Brain, Briefcase,
  Building2, CalendarClock, CalendarDays, CheckCircle, CheckCircle2, ClipboardCheck, ClipboardList, Clock, Cpu,
  CreditCard, Database, DollarSign, Droplets, FileCheck2, FileEdit, FilePlus2, FileText, FileWarning, Filter,
  Flame, Gauge, GitCompareArrows, Hammer, Headphones, HeartPulse, Home, Info, Layers, ListChecks,
  MessageSquare, MessageSquareText, MessagesSquare, Percent, PhoneCall, PhoneOff, PiggyBank, Receipt, Scale,
  Search, ShieldAlert, ShieldCheck, ShieldOff, Sparkles, Star, Target, Timer, TrendingDown, TrendingUp,
  UserCheck, UserMinus, Users, Wallet,
} from 'lucide-react';

type IconComponent = ComponentType<Record<string, unknown>>;

export const ICONS: Record<string, IconComponent> = {
  'activity': Activity,
  'alert-triangle': AlertTriangle,
  'arrow-left-right': ArrowLeftRight,
  'award': Award,
  'badge-dollar-sign': BadgeDollarSign,
  'bar-chart': BarChart3,
  'bed': BedDouble,
  'brain': Brain,
  'briefcase': Briefcase,
  'building': Building2,
  'calendar-clock': CalendarClock,
  'calendar': CalendarDays,
  'check-circle': CheckCircle,
  'check-circle-2': CheckCircle2,
  'clipboard-check': ClipboardCheck,
  'clipboard-list': ClipboardList,
  'clock': Clock,
  'cpu': Cpu,
  'credit-card': CreditCard,
  'database': Database,
  'dollar-sign': DollarSign,
  'droplets': Droplets,
  'file-check': FileCheck2,
  'file-edit': FileEdit,
  'file-plus': FilePlus2,
  'file-text': FileText,
  'file-warning': FileWarning,
  'filter': Filter,
  'flame': Flame,
  'gauge': Gauge,
  'git-compare': GitCompareArrows,
  'hammer': Hammer,
  'headphones': Headphones,
  'heart-pulse': HeartPulse,
  'home': Home,
  'info': Info,
  'layers': Layers,
  'list-checks': ListChecks,
  'message-square': MessageSquare,
  'message-square-text': MessageSquareText,
  'messages-square': MessagesSquare,
  'percent': Percent,
  'phone-call': PhoneCall,
  'phone-off': PhoneOff,
  'piggy-bank': PiggyBank,
  'receipt': Receipt,
  'scale': Scale,
  'search': Search,
  'shield-alert': ShieldAlert,
  'shield-check': ShieldCheck,
  'shield-off': ShieldOff,
  'sparkles': Sparkles,
  'star': Star,
  'target': Target,
  'timer': Timer,
  'trending-down': TrendingDown,
  'trending-up': TrendingUp,
  'user-check': UserCheck,
  'user-minus': UserMinus,
  'users': Users,
  'wallet': Wallet,
};

export type IconId = keyof typeof ICONS;

/** An icon id, or (legacy) the component itself, → the component. Unknown ids → undefined. */
export function resolveIcon(icon: unknown): IconComponent | undefined {
  if (!icon) return undefined;
  if (typeof icon === 'string') return ICONS[icon];
  return icon as IconComponent;
}

/** The registry id of a lucide component, for exporting legacy manifests as plain data. */
export function iconIdOf(icon: unknown): string | undefined {
  if (!icon || typeof icon === 'string') return (icon as string) || undefined;
  return Object.keys(ICONS).find((id) => ICONS[id] === icon);
}

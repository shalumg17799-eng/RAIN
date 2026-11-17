/** The types of the critical-alert context (CriticalAlertContext.tsx). */
import type { ReactNode } from 'react';

/** One reading in the alert's vitals panel. */
export interface CriticalAlertReading {
  id: string;
  label: string;
  value: string;
  state: string;
  detail: string;
}

/** One step the alert offers (watch the camera, notify, dispatch, muster). */
export interface CriticalAlertAction {
  id: string;
  label: string;
  kind: string;
  primary?: boolean;
  openLabel?: string;
  needsConfirm?: boolean;
  cameraId?: string;
  wallTo?: string;
  wallLabel?: string;
  description?: string;
  confirmedNote?: string;
  advancesTo?: string;
}

/** One stage of the alert's status rail. */
export interface CriticalAlertStatus {
  id: string;
  label: string;
  detail?: string;
}

/** The alert a persona's manifest loads through `criticalAlert` (its fixture's `alert`). */
export interface CriticalAlert {
  id: string;
  kind: string;
  title: string;
  severity: string;
  detectedAt: string;
  detectedLabel: string;
  armOnFlowKey: string;
  armAfterSeconds?: number;
  summary: string;
  permit: {
    id: string;
    title: string;
    state: string;
    stateLabel: string;
    wasState: string;
    detail: string;
    validTo: string;
    workOrder: string;
  };
  worker: {
    occupantId: string;
    tagSerial: number;
    role: string;
    company: string;
    enteredAt: string;
    minutesInside: number;
  };
  location: {
    occupantId: string;
    openingId: string;
    vesselName: string;
    openingName: string;
    levelLabel: string;
    zoneId: string;
    zoneName: string;
  };
  vitals: {
    state: string;
    headline: string;
    since: string;
    readings: CriticalAlertReading[];
    caveat: string;
  };
  responder: {
    fixtureId: string;
    role: string;
    state: string;
    detail: string;
    rescueFixtureId: string;
    rescueLabel: string;
    secondEntrant: { occupantId: string; tagSerial: number; detail: string };
  };
  sources: { id: string; label: string; detail: string; freshness: string }[];
  actions: CriticalAlertAction[];
  statusFlow: CriticalAlertStatus[];
  responderAck?: { afterSeconds?: number; label: string; detail: string };
  resolve?: { label: string; confirmLabel: string; description: string; confirmedNote?: string };
  unit3Muster?: {
    musterPointId: string;
    musterPointName: string;
    scopeZoneId: string;
    note: string;
    steps: { atSeconds: number; outstanding: number }[];
  };
}

/** The shape `criticalAlert()` resolves to. */
export interface CriticalAlertFeed {
  alert?: CriticalAlert | null;
}

/** One entry on the incident timeline. */
export interface CriticalAlertTimelineEntry {
  id: string;
  label: string;
  at: string;
  detail?: string;
}

/** A row the alert adds to the header bell. */
export interface CriticalAlertNotification {
  id: string;
  title: string;
  detail: string;
  at: string;
  unread: boolean;
  tone: 'warning';
  onSelect: () => void;
}

/** The parts of the alert's state that exist whether or not it has landed. */
export interface CriticalAlertBase {
  timeline: CriticalAlertTimelineEntry[];
  confirmed: Set<string>;
  open: boolean;
  cameraPlaying: boolean;
  musterStartedAt: number | null;
  responderAcked: boolean;
  setOpen: (open: boolean) => void;
  playCamera: (actionId?: string) => void;
  confirmAction: (actionId: string) => void;
  resolve: () => void;
  reportFlow: (flowKey: string | null | undefined) => void;
  notifications: CriticalAlertNotification[];
}

/** The alert has landed for the owning persona. */
export interface CriticalAlertLive extends CriticalAlertBase {
  active: true;
  alert: CriticalAlert;
  status: string;
  statusMeta: CriticalAlertStatus;
}

/** No alert on screen: another persona, or it has not landed yet. */
export interface CriticalAlertDormant extends CriticalAlertBase {
  active: false;
  alert: null;
  status: null;
  statusMeta?: undefined;
}

/** What `useCriticalAlert()` returns; narrow on `active`. */
export type CriticalAlertValue = CriticalAlertLive | CriticalAlertDormant;

export interface CriticalAlertProviderProps {
  children?: ReactNode;
}

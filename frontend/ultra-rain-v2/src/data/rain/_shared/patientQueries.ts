/**
 * Linda's own data questions, answered live by the backend: her ten persona queries in the v0.4 pack
 * (GAR-S1..S5 on her own records in rain_v4.synthetic, GAR-P1..P5 on public data for her town and county in
 * rain_v4.public_data). The list is GET /api/v4/ui2/queries?personaId=rain_patient; a question is asked through
 * POST /api/v4/ui2/ask, which runs the query read-only and returns its rows. The backend lets a patient run only her
 * own queries: another persona's is refused, never run. Every call shows in the console (core/api/proof.ts).
 */
import { logBackendCall, logBackendFailure } from '@core/api/proof';
import { dataBase } from './backendData';
import { PATIENT_PERSONA_ID } from './constants';

export interface PatientQuery {
  id: string;
  data: 'synthetic' | 'public';
  question: string;
}

export interface PatientDataAnswer {
  /** The backend turn id: `query:GAR-P4`, or `query:refused:<id>`. */
  id: string;
  text: string;
  caption?: string;
  columns: Array<{ key: string; label: string; align?: string }>;
  rows: Array<Record<string, unknown>>;
  /** Where the rows came from (the backend's citations). */
  sources: string[];
  /** Her other questions the backend suggests next. */
  chips: string[];
}

const offline = () => import.meta.env.MODE === 'test' || typeof fetch !== 'function';

async function call(method: 'GET' | 'POST', url: string, body?: unknown): Promise<unknown | null> {
  const t0 = performance.now();
  try {
    const res = await fetch(url, {
      method,
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    logBackendCall(method, url, res, Math.round(performance.now() - t0), body);
    return res.ok ? await res.json() : null;
  } catch (err) {
    logBackendFailure(method, url, err, Math.round(performance.now() - t0), body);
    return null;
  }
}

let list: Promise<PatientQuery[]> | null = null;

/** Her ten questions (loaded once). Empty when the backend cannot be reached. */
export function patientQueries(): Promise<PatientQuery[]> {
  if (offline()) return Promise.resolve([]);
  list ??= call('GET', `${dataBase()}/queries?personaId=${encodeURIComponent(PATIENT_PERSONA_ID)}`).then(
    (r) => ((r as { queries?: PatientQuery[] } | null)?.queries ?? []),
  );
  return list;
}

const key = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

/** The text names one of her queries: its id (GAR-P4) or its question (any case or punctuation). */
export function namesPatientQuery(text: string, queries: PatientQuery[]): boolean {
  if (/\bGAR-[SP][1-5]\b/i.test(text)) return true;
  const k = key(text);
  return k.length >= 10 && queries.some((q) => {
    const kq = key(q.question);
    return k === kq || (k.length >= 16 && kq.includes(k)) || (kq.length >= 16 && k.includes(kq));
  });
}

/**
 * Ask the backend. Resolves to the answer when the backend ran one of her queries (or refused another persona's),
 * and to null when it has nothing for this text (the phone then answers with its own fallback).
 */
export async function askPatientData(text: string): Promise<PatientDataAnswer | null> {
  if (offline()) return null;
  const turn = (await call('POST', `${dataBase()}/ask`, { clientId: 'rain', personaId: PATIENT_PERSONA_ID, input: text })) as {
    id?: string; text?: string; citations?: string[]; chips?: string[];
    components?: Array<{ type: string; props: Record<string, unknown> }>;
  } | null;
  if (!turn?.id?.startsWith('query:')) return null;
  const table = turn.components?.find((c) => c.type === 'data_table')?.props;
  return {
    id: turn.id,
    text: turn.text ?? '',
    caption: table?.caption as string | undefined,
    columns: (table?.columns as PatientDataAnswer['columns']) ?? [],
    rows: (table?.rows as PatientDataAnswer['rows']) ?? [],
    sources: turn.citations ?? [],
    chips: turn.chips ?? [],
  };
}

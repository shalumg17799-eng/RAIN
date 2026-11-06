/**
 * A connected system shown in the "Data Sources" / trust surfaces. Represents
 * where a persona's insights are sourced from (CCaaS, CRM, data warehouse…).
 */
export interface DataSource {
  id: string;
  name: string;
  status?: 'connected' | 'syncing' | 'error' | string;
  description?: string;
  icon?: string;
  lastSync?: string;
  recordCount?: number;
  [key: string]: unknown;
}

/**
 * /data-sources — the persona's connected data sources.
 *
 * The sources are the persona manifest's `dataSources` (the same list the API's
 * `GET /context` returns); a tenant's posture panel — what is real, what is
 * illustrative — is the manifest's `pages.dataSourcesPanel`; a tenant that
 * needs a different page altogether declares `pages.dataSources`. No persona
 * or client is named here.
 */
import DataSourcesPage from '@/components/layout/DataSourcesPage';
import { usePersonaPage } from '@core/runtime/usePersonaPage';

export default function DataSources() {
  const { ready, Page, manifest } = usePersonaPage('dataSources');
  if (!ready) return null;
  if (Page) return <Page />;
  const Panel = manifest?.pages?.dataSourcesPanel;
  return <DataSourcesPage sources={manifest?.dataSources ?? []} panel={Panel ? <Panel /> : null} />;
}

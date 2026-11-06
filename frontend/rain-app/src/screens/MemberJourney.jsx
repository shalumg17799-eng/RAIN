/**
 * /journey — the Member Journey page.
 *
 * A persona that has its own version of this page declares it in its
 * manifest's `pages.journey` (USSFCU's CFO shows data lineage, NFCU shows its
 * workforce view, Newfold its workforce intelligence…); everyone else gets the
 * generic member journey map. No persona or client is named here.
 */
import JourneyMapPage from '@/components/journey/JourneyMapPage';
import { MEMBER_JOURNEY_CHIPS } from '@/components/journey/memberJourney';
import journeyMap from '@/data/journeyMap.json';
import { usePersonaPage } from '@core/runtime/usePersonaPage';

export default function MemberJourney() {
  const { ready, Page } = usePersonaPage('journey');
  if (!ready) return null;
  if (Page) return <Page />;
  return <JourneyMapPage map={journeyMap} chips={MEMBER_JOURNEY_CHIPS} />;
}

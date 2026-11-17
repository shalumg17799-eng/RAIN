import { Navigate } from 'react-router-dom';
import type { WorkbenchId } from '@/data/rain/_shared/contract';
import { useWorkbench } from '@/components/value-based-care/workbenches/useWorkbench';
import ValueInsights from '@/components/value-based-care/workbenches/ValueInsights';
import QualityGate from '@/components/value-based-care/workbenches/QualityGate';
import LowValueCare from '@/components/value-based-care/workbenches/LowValueCare';
import ModelGovernance from '@/components/value-based-care/workbenches/ModelGovernance';
import CountyExplorer from '@/components/value-based-care/workbenches/CountyExplorer';
import RhtpReporting from '@/components/value-based-care/workbenches/RhtpReporting';
import Worklist from '@/components/value-based-care/workbenches/Worklist';
import Scheduling from '@/components/value-based-care/workbenches/Scheduling';
import Reminders from '@/components/value-based-care/workbenches/Reminders';

/**
 * The nine RAIN workbench routes (Data Sources is the persona's
 * `pages.dataSources`). Routes are global, so a persona whose contract does
 * not list the workbench, or any other client's persona, goes back to Cockpit.
 */
const PAGES: Record<string, WorkbenchId> = {
  'value-insights': 'valueInsights',
  'quality-gate': 'qualityGate',
  'low-value-care': 'lowValueCare',
  'model-governance': 'modelGovernance',
  'county-explorer': 'countyExplorer',
  'rhtp-reporting': 'rhtpReporting',
  worklist: 'worklist',
  scheduling: 'scheduling',
  reminders: 'reminders',
};

export default function ValueBasedCarePage({ page }: { page: string }) {
  const id = PAGES[page];
  const { key, access, filter } = useWorkbench(id);
  if (!id || !key || !access) return <Navigate to="/ask" replace />;
  // Keyed by persona so a switch never carries one persona's selection into another's view.
  switch (id) {
    case 'valueInsights':
      return <ValueInsights key={key} access={access} filter={filter} stateScope={key === 'state'} />;
    case 'qualityGate':
      return <QualityGate key={key} access={access} filter={filter} />;
    case 'lowValueCare':
      return <LowValueCare key={key} access={access} filter={filter} />;
    case 'modelGovernance':
      return <ModelGovernance key={key} access={access} />;
    case 'countyExplorer':
      return <CountyExplorer key={key} access={access} />;
    case 'rhtpReporting':
      return <RhtpReporting key={key} access={access} />;
    case 'worklist':
      return <Worklist key={key} access={access} filter={filter} />;
    case 'scheduling':
      return <Scheduling key={key} access={access} filter={filter} />;
    case 'reminders':
      return <Reminders key={key} access={access} filter={filter} />;
    default:
      return <Navigate to="/ask" replace />;
  }
}

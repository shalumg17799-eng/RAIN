import { KeyPoints } from '../shell/rainKit';

/** The rest of a step's scripted answer when its first visual is a catalog type (which carries the synthetic-data note). */
export default function KeyPointsCard({ points }: { points?: string[] }) {
  if (!points?.length) return null;
  return (
    <div className="min-w-0">
      <KeyPoints points={points} />
    </div>
  );
}

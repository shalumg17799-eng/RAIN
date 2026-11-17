import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Smartphone } from 'lucide-react';

/**
 * Linda's persona lands on her phone, not on the operator Cockpit: this opens
 * `/patient` as soon as her workspace mounts (mounted through `initialExtras`,
 * like the DoIT resident's survey launcher), and stays as a button in case the
 * presenter comes back to this screen with the browser's back button.
 */
export default function OpenPatientView() {
  const navigate = useNavigate();
  const fired = useRef(false);
  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    navigate('/patient', { replace: true });
  }, [navigate]);
  return (
    <div className="flex justify-center py-4">
      <button type="button" onClick={() => navigate('/patient')} className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-[14px] font-semibold text-white">
        <Smartphone className="h-4 w-4" aria-hidden="true" /> Open Linda's phone
      </button>
    </div>
  );
}

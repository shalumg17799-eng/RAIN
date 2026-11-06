import { Component } from 'react';
import { AlertTriangle } from 'lucide-react';
import { devError } from '@core/log';

/**
 * Keeps one broken visualization from taking down the whole conversation.
 *
 * Every persona hand-binds its JSON metrics to a React component in the
 * manifest's `answers` factory, so a renamed or re-nested field is a
 * render-time TypeError rather than anything the type system catches. Without a
 * boundary that error reaches the root and React unmounts the entire tree — the
 * page goes white, nav and all. (That is exactly how Newfold's save-desk panel
 * failed: it read `saveRateProjection` off `metrics.saveDesk` instead of the
 * root of the file.)
 *
 * The fallback is deliberately small and quiet. These are live client demos, so
 * a missing chart should read as one card that didn't load, not as a stack trace
 * on screen. The real error still goes to the console for whoever is debugging.
 */
export default class VizErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    devError('[VizErrorBoundary] inline visualization failed to render', error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <div className="bg-surface rounded-xl border border-border px-4 py-3 flex items-center gap-2.5">
        <AlertTriangle className="w-4 h-4 text-text-subtle flex-shrink-0" />
        <div>
          <p className="text-xs font-semibold text-text-muted">This visualization couldn't be rendered</p>
          <p className="text-[10px] text-text-subtle mt-0.5">The rest of the response is unaffected.</p>
        </div>
      </div>
    );
  }
}

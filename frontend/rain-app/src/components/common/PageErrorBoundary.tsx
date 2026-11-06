import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { devError } from '@core/log';

/**
 * Keeps a broken page or persona from blanking the whole app.
 *
 * Without it a render error anywhere below the shell reaches the root and React
 * unmounts everything — header, sidebar and all — so a presenter is left with
 * a white screen and no way back but a reload. With it, the shell stays up, the
 * failed area says so in one calm card, and the presenter can retry or simply
 * click another nav item: `resetKey` (the route path, or the persona id) clears
 * the error whenever the user moves on.
 */
interface Props {
  /** Changing this (route path, persona id) clears a caught error. */
  resetKey: string;
  /** What failed, in the fallback's words: "page", "workspace". */
  label?: string;
  children?: ReactNode;
}

interface State {
  error: Error | null;
  key: string;
}

export default class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null, key: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    // Navigating away is the natural "try again": a new key drops the error.
    if (props.resetKey !== state.key) return { error: null, key: props.resetKey };
    return null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    devError(`[PageErrorBoundary] ${this.props.label || 'page'} failed to render`, error, info);
  }

  retry = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex-1 flex items-center justify-center p-6" role="alert">
        <div className="max-w-sm w-full bg-surface rounded-xl border border-border px-5 py-4 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-text-subtle flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text">This {this.props.label || 'page'} couldn&apos;t be displayed</p>
            <p className="text-xs text-text-muted mt-1">The rest of the app is unaffected. Try again, or choose another page.</p>
            <button
              type="button"
              onClick={this.retry}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-semibold text-text-muted hover:text-brand hover:border-brand/30 transition-colors"
            >
              <RotateCcw className="w-3 h-3" aria-hidden="true" />
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }
}

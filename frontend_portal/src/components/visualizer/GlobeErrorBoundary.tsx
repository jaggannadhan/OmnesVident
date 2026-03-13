import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; }
interface State { error: Error | null; }

/**
 * Catches any render or useFrame error inside the 3D visualizer and shows
 * a graceful fallback instead of blanking the whole page.
 */
export class GlobeErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div
          className="w-full rounded-xl border border-red-900/40 bg-base flex flex-col items-center justify-center gap-2 text-center"
          style={{ height: 480 }}
        >
          <span className="text-2xl select-none">⚠️</span>
          <p className="text-xs font-semibold text-red-400">Globe failed to load</p>
          <p className="text-[10px] font-mono text-slate-600 max-w-xs">
            {this.state.error.message}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 text-[10px] text-slate-500 hover:text-slate-300 border border-rim rounded px-2 py-1 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

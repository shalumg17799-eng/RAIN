import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Pause, Square, RotateCcw, X, Zap, SkipForward } from 'lucide-react';
import DemoRunner from './DemoRunner';
import { personaCapabilities } from './personaDemoSteps';
import { useBranding } from '../context/BrandingContext';

export default function DemoOverlay({ isRunning, onStart, onStop }) {
  const { client } = useBranding();
  const [step, setStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(DemoRunner.getTotalSteps());
  const [stepLabel, setStepLabel] = useState('');
  const [showComplete, setShowComplete] = useState(false);
  const [paused, setPaused] = useState(false);

  const personaId = window.__activePersona || 'ops';
  const capabilities = personaCapabilities[personaId] || personaCapabilities.ops;

  const handleComplete = useCallback(() => {
    setShowComplete(true);
  }, []);

  const handleStopped = useCallback(() => {
    setPaused(false);
    onStop();
  }, [onStop]);

  useEffect(() => {
    DemoRunner.subscribe({
      onStep: (s, t, label) => {
        setStep(s);
        setTotalSteps(t);
        setStepLabel(label);
      },
      onDone: handleComplete,
      onStop: handleStopped,
      onPause: (isPaused) => setPaused(isPaused),
    });
  }, [handleComplete, handleStopped]);

  const handlePauseResume = () => {
    if (paused) DemoRunner.resume();
    else DemoRunner.pause();
  };

  const handleStopClick = () => {
    DemoRunner.stop();
  };

  const handleReplay = () => {
    setShowComplete(false);
    setStep(0);
    setTotalSteps(DemoRunner.getTotalSteps());
    setStepLabel('');
    setPaused(false);
    onStart();
  };

  const handleExit = () => {
    setShowComplete(false);
    setStep(0);
    setStepLabel('');
    setPaused(false);
    onStop();
  };

  const progress = totalSteps > 0 ? (step / totalSteps) * 100 : 0;

  return (
    <>
      {/* Progress bar + controls — fixed top strip */}
      <AnimatePresence>
        {isRunning && !showComplete && (
          <motion.div
            initial={{ y: -60 }}
            animate={{ y: 0 }}
            exit={{ y: -60 }}
            transition={{ duration: 0.3 }}
            className="fixed top-0 left-0 right-0 z-[100] shadow-lg"
            style={{
              background: paused
                ? 'linear-gradient(to right, var(--color-warning-800), var(--color-warning-700))'
                : 'linear-gradient(to right, var(--color-brand), color-mix(in srgb, var(--color-brand) 75%, #fff))',
            }}
          >
            {/* Progress bar */}
            <div className="h-1 bg-white/20">
              <motion.div
                className="h-full bg-white"
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>

            <div className="flex items-center justify-between px-6 py-2.5">
              <div className="flex items-center gap-3">
                {/* Status indicator */}
                <div className="flex items-center gap-1.5">
                  {paused ? (
                    <>
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-warning-300" />
                      </span>
                      <span className="text-white/80 text-xs font-medium uppercase tracking-wider">Paused</span>
                    </>
                  ) : (
                    <>
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-success-400" />
                      </span>
                      <span className="text-white/80 text-xs font-medium uppercase tracking-wider">Demo Running</span>
                    </>
                  )}
                </div>
                <span className="text-white/40 text-xs">|</span>
                <span className="text-white text-sm font-medium">
                  Step {step}/{totalSteps}
                </span>
                <span className="text-white/60 text-sm truncate max-w-[300px]">{stepLabel}</span>
              </div>

              {/* Controls */}
              <div className="flex items-center gap-2">
                {/* Pause / Resume */}
                <button
                  onClick={handlePauseResume}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/15 hover:bg-white/25 text-white text-xs font-medium transition-colors cursor-pointer"
                  title={paused ? 'Resume (Space)' : 'Pause (Space)'}
                >
                  {paused ? (
                    <>
                      <Play className="w-3 h-3" />
                      Resume
                    </>
                  ) : (
                    <>
                      <Pause className="w-3 h-3" />
                      Pause
                    </>
                  )}
                  <span className="text-white/50 text-[10px] ml-0.5">(Space)</span>
                </button>

                {/* Stop */}
                <button
                  onClick={handleStopClick}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-critical-500/30 hover:bg-critical-500/50 text-white text-xs font-medium transition-colors cursor-pointer"
                  title="Stop Demo (Esc)"
                >
                  <Square className="w-3 h-3" />
                  Stop
                  <span className="text-white/50 text-[10px] ml-0.5">(Esc)</span>
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Paused overlay indicator */}
      <AnimatePresence>
        {isRunning && paused && !showComplete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[100]"
          >
            <div className="bg-warning-600 text-white px-6 py-3 rounded-xl shadow-2xl flex items-center gap-3">
              <Pause className="w-5 h-5" />
              <span className="text-sm font-semibold">Demo Paused</span>
              <span className="text-white/60 text-xs">Press Space to resume or Esc to stop</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Demo Complete Modal */}
      <AnimatePresence>
        {showComplete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="bg-white rounded-2xl shadow-2xl w-[440px] overflow-hidden"
            >
              {/* Success header */}
              <div className="bg-gradient-to-r from-brand to-[color-mix(in_srgb,var(--color-brand)_75%,#fff)] px-8 py-8 text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/20 flex items-center justify-center">
                  <Zap className="w-8 h-8 text-white" />
                </div>
                <h2 className="text-2xl font-bold text-white">Demo Complete</h2>
                <p className="text-white/70 text-sm mt-2">
                  All {totalSteps} steps completed — {capabilities.length} Radiant AI capabilities showcased
                </p>
              </div>

              {/* Body */}
              <div className="px-8 py-6">
                <p className="text-sm text-text-muted text-center leading-relaxed mb-4">
                  The guided demo walked through all major features of the {client?.name || 'AI'} platform —
                  from proactive signals and conversational analytics to automated actions and anomaly detection.
                </p>
                <div className="bg-surface-2 rounded-lg p-3 mb-2">
                  <p className="text-[10px] font-semibold text-text-subtle uppercase tracking-wider mb-2">Radiant AI Capabilities Demonstrated</p>
                  <div className="grid grid-cols-2 gap-1.5 text-xs text-text-muted">
                    {capabilities.map((cap) => (
                      <span key={cap}>✓ {cap}</span>
                    ))}
                  </div>
                </div>

                <div className="flex gap-3 mt-6">
                  <button
                    onClick={handleReplay}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand/90 transition-colors cursor-pointer"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Replay Demo
                  </button>
                  <button
                    onClick={handleExit}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-border text-text text-sm font-semibold hover:bg-surface-2 transition-colors cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                    Exit
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

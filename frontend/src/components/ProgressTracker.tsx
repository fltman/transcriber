import { useState, useEffect } from "react";
import type { ProgressUpdate } from "../types";

interface Props {
  progress: ProgressUpdate | null;
}

const STEPS = [
  { key: "audio", label: "Audio", icon: "M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z", threshold: 2 },
  { key: "whisper", label: "Transcription", icon: "M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z", threshold: 10 },
  { key: "llm", label: "AI Analysis", icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z", threshold: 30 },
  { key: "diarization", label: "Diarization", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z", threshold: 45 },
  { key: "alignment", label: "Alignment", icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15", threshold: 75 },
  { key: "speaker_id", label: "Identification", icon: "M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2", threshold: 90 },
  { key: "done", label: "Done", icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z", threshold: 100 },
];

export default function ProgressTracker({ progress }: Props) {
  const pct = progress?.progress ?? 0;
  const step = progress?.step || "Starting...";
  const [dots, setDots] = useState("");

  useEffect(() => {
    if (pct >= 100) return;
    const interval = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."));
    }, 500);
    return () => clearInterval(interval);
  }, [pct]);

  const activeStepIdx = STEPS.findIndex((s, i) => {
    const next = STEPS[i + 1];
    return !next || pct < next.threshold;
  });

  return (
    <div className="rounded-2xl bg-slate-900/80 border border-slate-800/50 p-6 mb-6 backdrop-blur-sm">
      {/* Current step with animated text */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-xl bg-violet-500/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-violet-400 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={STEPS[activeStepIdx]?.icon || STEPS[0].icon} />
              </svg>
            </div>
            {pct < 100 && (
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-violet-500 rounded-full animate-ping" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-white">{step}{pct < 100 ? dots : ""}</p>
            <p className="text-xs text-slate-500">{STEPS[activeStepIdx]?.label || "Processing"}</p>
          </div>
        </div>
        <span className="text-2xl font-bold font-mono text-white">{Math.round(pct)}%</span>
      </div>

      {/* Progress bar */}
      <div className="relative w-full bg-slate-800 rounded-full h-2 mb-5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out relative"
          style={{
            width: `${pct}%`,
            background: pct >= 100
              ? "linear-gradient(90deg, #10b981, #34d399)"
              : "linear-gradient(90deg, #8b5cf6, #6366f1, #8b5cf6)",
            backgroundSize: "200% 100%",
            animation: pct < 100 ? "shimmer 2s linear infinite" : "none",
          }}
        />
        <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
      </div>

      {/* Step indicators */}
      <div className="flex justify-between">
        {STEPS.map((s, i) => {
          const isDone = pct >= s.threshold;
          const isActive = i === activeStepIdx && pct < 100;
          return (
            <div key={s.key} className="flex flex-col items-center gap-1.5">
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-500 ${
                  isDone
                    ? "bg-emerald-500/20 text-emerald-400"
                    : isActive
                    ? "bg-violet-500/20 text-violet-400 ring-2 ring-violet-500/30"
                    : "bg-slate-800 text-slate-600"
                }`}
              >
                {isDone ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className={`w-4 h-4 ${isActive ? "animate-pulse" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={s.icon} />
                  </svg>
                )}
              </div>
              <span
                className={`text-[10px] font-medium transition-colors ${
                  isDone ? "text-emerald-400" : isActive ? "text-violet-400" : "text-slate-600"
                }`}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

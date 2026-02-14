interface Props {
  recordingTime: number;
  audioLevel: number;
  onStop: () => void;
}

function formatTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function LiveRecordingBar({ recordingTime, audioLevel, onStop }: Props) {
  return (
    <div className="rounded-xl bg-slate-900/80 border border-red-500/30 p-4 mb-5 backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Pulsing red dot */}
          <div className="relative">
            <span className="w-3 h-3 bg-red-500 rounded-full block" />
            <span className="absolute inset-0 w-3 h-3 bg-red-500 rounded-full animate-ping opacity-75" />
          </div>

          {/* Timer */}
          <span className="text-xl font-mono font-bold text-white">{formatTime(recordingTime)}</span>

          {/* Audio level bars */}
          <div className="flex items-center gap-0.5 h-6">
            {Array.from({ length: 16 }).map((_, i) => {
              const h = Math.max(3, Math.min(24, audioLevel * 24 * (0.5 + Math.random() * 0.5)));
              return (
                <div
                  key={i}
                  className="w-1 rounded-full bg-gradient-to-t from-red-500 to-rose-400 transition-all duration-75"
                  style={{ height: `${h}px` }}
                />
              );
            })}
          </div>

          <span className="text-sm text-red-400 font-medium">LIVE</span>
          <span className="px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded">Beta</span>
        </div>

        {/* Stop button */}
        <button
          onClick={onStop}
          className="px-5 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 hover:text-red-300 border border-red-500/30 rounded-xl font-medium transition-all flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
          Stop & Finalize
        </button>
      </div>
    </div>
  );
}

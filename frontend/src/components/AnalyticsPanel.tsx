import { useEffect, useState } from "react";
import { getSpeakerAnalytics } from "../api";

interface SpeakerAnalytics {
  name: string;
  color: string;
  speaking_time: number;
  segment_count: number;
  percentage: number;
  timeline: { start: number; end: number }[];
}

interface Analytics {
  speakers: SpeakerAnalytics[];
  total_duration: number;
  total_speaking_time: number;
  silence_percentage: number;
}

interface Props {
  meetingId: string;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

export default function AnalyticsPanel({ meetingId }: Props) {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  useEffect(() => {
    getSpeakerAnalytics(meetingId).then(setAnalytics);
  }, [meetingId]);

  if (!analytics) {
    return (
      <div className="flex justify-center py-8">
        <div className="w-5 h-5 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  const { speakers, total_duration, total_speaking_time, silence_percentage } = analytics;

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold text-slate-300">Talaranalys</h3>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-slate-800/50 rounded-lg p-2.5 text-center">
          <div className="text-lg font-bold text-white">{speakers.length}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Talare</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-2.5 text-center">
          <div className="text-lg font-bold text-white">{formatDuration(total_speaking_time)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Talad tid</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-2.5 text-center">
          <div className="text-lg font-bold text-white">{silence_percentage}%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Tystnad</div>
        </div>
      </div>

      {/* Speaking time distribution (horizontal bars) */}
      <div className="space-y-2">
        {speakers.map((spk) => (
          <div key={spk.name}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: spk.color }} />
                <span className="text-xs text-slate-300 font-medium">{spk.name}</span>
              </div>
              <span className="text-[10px] text-slate-500">
                {formatDuration(spk.speaking_time)} ({spk.percentage}%)
              </span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${spk.percentage}%`,
                  backgroundColor: spk.color,
                  opacity: 0.8,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Timeline visualization */}
      {total_duration > 0 && (
        <div>
          <div className="text-xs text-slate-500 mb-2">Tidslinje</div>
          <div className="bg-slate-800/50 rounded-lg p-2">
            {speakers.map((spk) => (
              <div key={spk.name} className="flex items-center gap-2 mb-1 last:mb-0">
                <span className="text-[10px] text-slate-500 w-16 truncate flex-shrink-0">{spk.name}</span>
                <div className="flex-1 h-3 bg-slate-900/50 rounded relative">
                  {spk.timeline.map((seg, i) => (
                    <div
                      key={i}
                      className="absolute top-0 h-full rounded-sm"
                      style={{
                        left: `${(seg.start / total_duration) * 100}%`,
                        width: `${Math.max(0.5, ((seg.end - seg.start) / total_duration) * 100)}%`,
                        backgroundColor: spk.color,
                        opacity: 0.7,
                      }}
                    />
                  ))}
                </div>
              </div>
            ))}
            {/* Time axis */}
            <div className="flex justify-between mt-1 px-[4.5rem]">
              <span className="text-[9px] text-slate-600">0:00</span>
              <span className="text-[9px] text-slate-600">{formatDuration(total_duration / 2)}</span>
              <span className="text-[9px] text-slate-600">{formatDuration(total_duration)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Segment counts */}
      <div>
        <div className="text-xs text-slate-500 mb-2">Antal inlagg</div>
        <div className="space-y-1">
          {speakers.map((spk) => (
            <div key={spk.name} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: spk.color }} />
                <span className="text-slate-400">{spk.name}</span>
              </div>
              <span className="text-slate-500">{spk.segment_count} segment</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import type { Speaker, Segment } from "../types";
import { updateSpeaker, mergeSpeakers } from "../api";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  speakers: Speaker[];
  segments: Segment[];
  onUpdate: () => void;
}

export default function SpeakerPanel({ speakers, segments, onUpdate }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [mergeMode, setMergeMode] = useState(false);
  const [mergeSource, setMergeSource] = useState<string | null>(null);

  async function saveName(id: string) {
    if (editName.trim()) {
      try {
        await updateSpeaker(id, { display_name: editName.trim() });
        onUpdate();
      } catch (err) {
        console.error("Failed to save speaker name:", err);
      }
    }
    setEditingId(null);
  }

  async function handleColorChange(id: string, color: string) {
    try {
      await updateSpeaker(id, { color });
      onUpdate();
    } catch (err) {
      console.error("Failed to update speaker color:", err);
    }
  }

  async function handleMerge(targetId: string) {
    if (!mergeSource || mergeSource === targetId) return;
    try {
      await mergeSpeakers(mergeSource, targetId);
      setMergeMode(false);
      setMergeSource(null);
      onUpdate();
    } catch (err) {
      console.error("Failed to merge speakers:", err);
    }
  }

  // Calculate speaking time percentage for bars
  const totalTime = speakers.reduce((sum, s) => sum + s.total_speaking_time, 0);

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/50 p-5 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-white text-sm">Speakers ({speakers.length})</h3>
        <button
          onClick={() => { setMergeMode(!mergeMode); setMergeSource(null); }}
          className={`text-xs px-2.5 py-1 rounded-lg transition ${
            mergeMode
              ? "bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/30"
              : "text-slate-500 hover:text-white hover:bg-slate-800"
          }`}
        >
          {mergeMode ? "Cancel" : "Merge"}
        </button>
      </div>

      {mergeMode && (
        <p className="text-xs text-amber-400/70 mb-3 px-1">
          {mergeSource ? "Select speaker to keep" : "Select speaker to remove"}
        </p>
      )}

      <div className="space-y-2">
        {speakers.map((s) => {
          const pct = totalTime > 0 ? (s.total_speaking_time / totalTime) * 100 : 0;
          return (
            <div
              key={s.id}
              className={`rounded-lg p-3 transition-all ${
                mergeMode
                  ? mergeSource === s.id
                    ? "ring-2 ring-amber-400/50 bg-amber-500/5"
                    : "hover:bg-slate-800/50 cursor-pointer"
                  : "hover:bg-slate-800/30"
              }`}
              onClick={() => {
                if (!mergeMode) return;
                if (!mergeSource) setMergeSource(s.id);
                else if (mergeSource !== s.id) handleMerge(s.id);
              }}
            >
              <div className="flex items-center gap-2.5">
                <div className="relative">
                  <input
                    type="color"
                    value={s.color}
                    onChange={(e) => handleColorChange(s.id, e.target.value)}
                    className="w-6 h-6 rounded-full cursor-pointer border-0 p-0 bg-transparent"
                    title="Change color"
                  />
                </div>

                {editingId === s.id ? (
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveName(s.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    onBlur={() => saveName(s.id)}
                    autoFocus
                    className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-2 py-0.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  />
                ) : (
                  <span
                    className="flex-1 text-sm font-medium text-slate-200 cursor-pointer hover:text-violet-300 transition truncate"
                    onClick={(e) => {
                      if (mergeMode) return;
                      e.stopPropagation();
                      setEditingId(s.id);
                      setEditName(s.display_name || s.label);
                    }}
                  >
                    {s.display_name || s.label}
                  </span>
                )}

                {s.identified_by === "intro_llm" && (
                  <span className="text-[10px] font-medium text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">AI</span>
                )}
              </div>

              {/* Speaking time bar */}
              <div className="mt-2 pl-8">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: s.color }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono w-12 text-right">
                    {formatTime(s.total_speaking_time)}
                  </span>
                </div>
                <p className="text-[10px] text-slate-600 mt-0.5">{s.segment_count} {s.segment_count === 1 ? "segment" : "segments"}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

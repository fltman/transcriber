import { useState, useRef, useEffect } from "react";
import type { Segment, Speaker } from "../types";
import { updateSegmentText } from "../api";
import { useStore } from "../store";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  segments: Segment[];
  speakers: Speaker[];
  audioRef: React.RefObject<HTMLAudioElement | null>;
  onUpdate: () => void;
}

export default function TranscriptView({ segments, speakers, audioRef, onUpdate }: Props) {
  const { currentTime } = useStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const editRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const active = segments.find((s) => currentTime >= s.start_time && currentTime < s.end_time);
    if (active) {
      const el = document.getElementById(`seg-${active.id}`);
      if (el && containerRef.current) {
        const rect = el.getBoundingClientRect();
        const containerRect = containerRef.current.getBoundingClientRect();
        if (rect.top < containerRect.top || rect.bottom > containerRect.bottom) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }
    }
  }, [currentTime]);

  function seekTo(time: number) {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      audioRef.current.play();
    }
  }

  async function saveEdit(segId: string) {
    if (editText.trim()) {
      await updateSegmentText(segId, editText.trim());
      onUpdate();
    }
    setEditingId(null);
  }

  function startEdit(seg: Segment) {
    setEditingId(seg.id);
    setEditText(seg.text);
    setTimeout(() => editRef.current?.focus(), 50);
  }

  // Group consecutive segments by speaker
  const grouped: { speaker: Speaker | null; segments: Segment[] }[] = [];
  let lastSpeakerId: string | null = null;
  for (const seg of segments) {
    if (seg.speaker_id !== lastSpeakerId) {
      const speaker = speakers.find((s) => s.id === seg.speaker_id) || null;
      grouped.push({ speaker, segments: [seg] });
      lastSpeakerId = seg.speaker_id;
    } else {
      grouped[grouped.length - 1].segments.push(seg);
    }
  }

  return (
    <div
      ref={containerRef}
      className="rounded-xl bg-slate-900/80 border border-slate-800/50 overflow-y-auto backdrop-blur-sm"
      style={{ maxHeight: "calc(100vh - 280px)" }}
    >
      {grouped.map((group, gi) => {
        const speaker = group.speaker;
        return (
          <div key={gi} className="border-b border-slate-800/30 last:border-b-0 p-5">
            {/* Speaker header */}
            <div className="flex items-center gap-2.5 mb-3">
              <span
                className="w-3 h-3 rounded-full flex-shrink-0 ring-2 ring-offset-1 ring-offset-slate-900"
                style={{
                  backgroundColor: speaker?.color || "#64748b",
                  boxShadow: `0 0 8px ${speaker?.color || "#64748b"}40`,
                }}
              />
              <span className="text-sm font-semibold text-slate-200">
                {speaker?.display_name || speaker?.label || "Unknown"}
              </span>
              <span className="text-xs text-slate-600 font-mono">
                {formatTime(group.segments[0].start_time)}
              </span>
            </div>

            {/* Segments */}
            <div className="pl-5 space-y-1">
              {group.segments.map((seg) => {
                const isActive = currentTime >= seg.start_time && currentTime < seg.end_time;
                return (
                  <div
                    key={seg.id}
                    id={`seg-${seg.id}`}
                    className={`group flex items-start gap-2 rounded-lg px-3 py-1.5 -mx-3 transition-all duration-200 ${
                      isActive
                        ? "bg-violet-500/10 border border-violet-500/20"
                        : "border border-transparent hover:bg-slate-800/30"
                    }`}
                  >
                    <button
                      onClick={() => seekTo(seg.start_time)}
                      className={`text-xs mt-0.5 flex-shrink-0 w-10 font-mono transition ${
                        isActive ? "text-violet-400" : "text-slate-600 hover:text-violet-400"
                      }`}
                    >
                      {formatTime(seg.start_time)}
                    </button>

                    {editingId === seg.id ? (
                      <div className="flex-1">
                        <textarea
                          ref={editRef}
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveEdit(seg.id); }
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white resize-none focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                          rows={2}
                        />
                        <div className="flex gap-2 mt-1.5">
                          <button onClick={() => saveEdit(seg.id)} className="text-xs text-violet-400 hover:text-violet-300">Save</button>
                          <button onClick={() => setEditingId(null)} className="text-xs text-slate-500 hover:text-slate-300">Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <p
                        className={`flex-1 text-sm cursor-pointer leading-relaxed transition ${
                          isActive ? "text-white font-medium" : "text-slate-300 hover:text-white"
                        } ${seg.is_edited ? "italic text-slate-400" : ""}`}
                        onClick={() => startEdit(seg)}
                        title="Click to edit"
                      >
                        {seg.text}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

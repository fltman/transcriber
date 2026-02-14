import { useEffect, useState } from "react";
import { listInsights, extractInsights, updateInsight, deleteInsight } from "../api";
import type { MeetingInsight } from "../api";

interface Props {
  meetingId: string;
}

const TYPE_CONFIG = {
  decision: { label: "Beslut", icon: "scale", color: "emerald" },
  action_item: { label: "Atgard", icon: "check", color: "violet" },
  open_question: { label: "Fraga", icon: "question", color: "amber" },
};

export default function InsightsPanel({ meetingId }: Props) {
  const [insights, setInsights] = useState<MeetingInsight[]>([]);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);

  useEffect(() => {
    loadInsights();
  }, [meetingId]);

  async function loadInsights() {
    setLoading(true);
    const data = await listInsights(meetingId);
    setInsights(data);
    setLoading(false);
  }

  async function handleExtract() {
    setExtracting(true);
    await extractInsights(meetingId);
    // Poll for completion
    const poll = setInterval(async () => {
      const data = await listInsights(meetingId);
      if (data.length > 0) {
        setInsights(data);
        setExtracting(false);
        clearInterval(poll);
      }
    }, 2000);
    // Safety timeout
    setTimeout(() => {
      clearInterval(poll);
      setExtracting(false);
      loadInsights();
    }, 60000);
  }

  async function handleToggleStatus(insight: MeetingInsight) {
    const newStatus = insight.status === "completed" ? "open" : "completed";
    const updated = await updateInsight(insight.id, { status: newStatus });
    setInsights(insights.map((i) => (i.id === updated.id ? updated : i)));
  }

  async function handleDelete(id: string) {
    await deleteInsight(id);
    setInsights(insights.filter((i) => i.id !== id));
  }

  function formatTime(seconds: number | null) {
    if (seconds === null || seconds === undefined) return "";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  const decisions = insights.filter((i) => i.insight_type === "decision");
  const actions = insights.filter((i) => i.insight_type === "action_item");
  const questions = insights.filter((i) => i.insight_type === "open_question");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">Insights</h3>
        <button
          onClick={handleExtract}
          disabled={extracting}
          className="text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-500 disabled:opacity-50 transition flex items-center gap-1.5"
        >
          {extracting ? (
            <>
              <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Analyserar...
            </>
          ) : insights.length > 0 ? (
            "Analysera igen"
          ) : (
            "Extrahera insights"
          )}
        </button>
      </div>

      {loading && (
        <div className="flex justify-center py-4">
          <div className="w-5 h-5 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
        </div>
      )}

      {!loading && insights.length === 0 && !extracting && (
        <p className="text-xs text-slate-600 text-center py-4">
          Klicka "Extrahera insights" for att analysera motet med AI.
        </p>
      )}

      {/* Decisions */}
      {decisions.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-xs font-medium text-emerald-400">Beslut ({decisions.length})</span>
          </div>
          <div className="space-y-1.5">
            {decisions.map((d) => (
              <InsightItem key={d.id} insight={d} onToggle={handleToggleStatus} onDelete={handleDelete} formatTime={formatTime} />
            ))}
          </div>
        </div>
      )}

      {/* Action items */}
      {actions.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-violet-500" />
            <span className="text-xs font-medium text-violet-400">Atgardspunkter ({actions.length})</span>
          </div>
          <div className="space-y-1.5">
            {actions.map((a) => (
              <InsightItem key={a.id} insight={a} onToggle={handleToggleStatus} onDelete={handleDelete} formatTime={formatTime} />
            ))}
          </div>
        </div>
      )}

      {/* Open questions */}
      {questions.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-xs font-medium text-amber-400">Oppna fragor ({questions.length})</span>
          </div>
          <div className="space-y-1.5">
            {questions.map((q) => (
              <InsightItem key={q.id} insight={q} onToggle={handleToggleStatus} onDelete={handleDelete} formatTime={formatTime} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function InsightItem({
  insight,
  onToggle,
  onDelete,
  formatTime,
}: {
  insight: MeetingInsight;
  onToggle: (i: MeetingInsight) => void;
  onDelete: (id: string) => void;
  formatTime: (s: number | null) => string;
}) {
  const isCompleted = insight.status === "completed";
  return (
    <div className={`bg-slate-800/50 rounded-lg px-3 py-2 group ${isCompleted ? "opacity-50" : ""}`}>
      <div className="flex items-start gap-2">
        <button
          onClick={() => onToggle(insight)}
          className={`mt-0.5 w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition ${
            isCompleted
              ? "bg-emerald-600 border-emerald-600"
              : "border-slate-600 hover:border-slate-400"
          }`}
        >
          {isCompleted && (
            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </button>
        <div className="flex-1 min-w-0">
          <p className={`text-sm text-slate-300 ${isCompleted ? "line-through" : ""}`}>
            {insight.content}
          </p>
          <div className="flex items-center gap-2 mt-1">
            {insight.assignee && (
              <span className="text-[10px] text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded">
                {insight.assignee}
              </span>
            )}
            {insight.source_start_time !== null && (
              <span className="text-[10px] text-slate-600">
                {formatTime(insight.source_start_time)}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={() => onDelete(insight.id)}
          className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition p-1"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

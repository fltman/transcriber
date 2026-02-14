import { useEffect, useState } from "react";
import type { ModelPreset, ModelSettings } from "../types";
import { getModelSettings, updateModelSettings } from "../api";

interface Props {
  onClose: () => void;
}

const TASK_LABELS: Record<string, { label: string; desc: string; type: "llm" | "whisper" }> = {
  actions: { label: "Actions", desc: "Custom actions on transcripts", type: "llm" },
  analysis: { label: "Analysis", desc: "Intro detection, speaker ID, finalization", type: "llm" },
  live: { label: "Live polish", desc: "Speaker naming during live sessions", type: "llm" },
  transcription: { label: "Transcription", desc: "Whisper model for batch processing", type: "whisper" },
  live_transcription: { label: "Live transcription", desc: "Whisper model for live sessions", type: "whisper" },
};

export default function SettingsDialog({ onClose }: Props) {
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    const data = await getModelSettings();
    setSettings(data);
    setAssignments(data.assignments);
  }

  async function handleSave() {
    setSaving(true);
    const data = await updateModelSettings(assignments);
    setSettings(data);
    setAssignments(data.assignments);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function presetsForType(type: "llm" | "whisper"): ModelPreset[] {
    if (!settings) return [];
    return settings.presets.filter((p) => p.type === type);
  }

  if (!settings) {
    return (
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
        <div className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl p-6 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-center py-8">
            <div className="w-5 h-5 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl p-6 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-white mb-5">Model Settings</h2>

        <div className="space-y-4">
          {Object.entries(TASK_LABELS).map(([task, info]) => {
            const options = presetsForType(info.type);
            return (
              <div key={task}>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  {info.label}
                </label>
                <p className="text-xs text-slate-500 mb-1.5">{info.desc}</p>
                <select
                  value={assignments[task] || ""}
                  onChange={(e) => setAssignments({ ...assignments, [task]: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700/50 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50 appearance-none cursor-pointer"
                >
                  {options.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.provider})
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>

        <div className="flex items-center justify-between mt-6">
          <p className="text-xs text-slate-600">
            Add models by dropping .json files in model_presets/
          </p>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition text-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2 bg-violet-600 text-white rounded-xl font-medium hover:bg-violet-500 disabled:opacity-50 transition text-sm flex items-center gap-2"
            >
              {saving ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Saving...
                </>
              ) : saved ? (
                "Saved!"
              ) : (
                "Save"
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

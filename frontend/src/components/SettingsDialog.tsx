import { useEffect, useState } from "react";
import type { ModelPreset, ModelSettings } from "../types";
import { getModelSettings, updateModelSettings, getPreferences, updatePreferences, listSpeakerProfiles, deleteSpeakerProfile } from "../api";
import type { Preferences, SpeakerProfile } from "../api";

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
  const [tab, setTab] = useState<"models" | "preferences">("models");

  // Preferences state
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [defaultVocab, setDefaultVocab] = useState("");
  const [profilesEnabled, setProfilesEnabled] = useState(true);
  const [profiles, setProfiles] = useState<SpeakerProfile[]>([]);

  useEffect(() => {
    loadSettings();
    loadPreferences();
  }, []);

  async function loadSettings() {
    const data = await getModelSettings();
    setSettings(data);
    setAssignments(data.assignments);
  }

  async function loadPreferences() {
    const p = await getPreferences();
    setPrefs(p);
    setDefaultVocab(p.default_vocabulary || "");
    setProfilesEnabled(p.speaker_profiles_enabled);
    const profileList = await listSpeakerProfiles();
    setProfiles(profileList);
  }

  async function handleSave() {
    setSaving(true);
    if (tab === "models") {
      const data = await updateModelSettings(assignments);
      setSettings(data);
      setAssignments(data.assignments);
    } else {
      await updatePreferences({
        default_vocabulary: defaultVocab,
        speaker_profiles_enabled: profilesEnabled,
      });
    }
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function handleDeleteProfile(id: string) {
    const profile = profiles.find((p) => p.id === id);
    if (!confirm(`Delete voice profile "${profile?.name}"? This cannot be undone.`)) return;
    await deleteSpeakerProfile(id);
    setProfiles(profiles.filter((p) => p.id !== id));
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
        <h2 className="text-xl font-bold text-white mb-4">Settings</h2>

        {/* Tab toggle */}
        <div className="flex bg-slate-800 rounded-xl p-1 mb-5">
          <button
            onClick={() => setTab("models")}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === "models" ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
            }`}
          >
            Models
          </button>
          <button
            onClick={() => setTab("preferences")}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === "preferences" ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
            }`}
          >
            Preferences
          </button>
        </div>

        {tab === "models" ? (
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
        ) : (
          <div className="space-y-5">
            {/* Default vocabulary */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">
                Default vocabulary
              </label>
              <p className="text-xs text-slate-500 mb-1.5">
                Domain-specific terms applied to all new transcriptions unless overridden.
              </p>
              <textarea
                value={defaultVocab}
                onChange={(e) => setDefaultVocab(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700/50 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50 resize-none"
                rows={3}
                maxLength={2000}
                placeholder="Names, technical terms, abbreviations..."
              />
            </div>

            {/* Speaker profiles toggle */}
            <div>
              <div className="flex items-center justify-between">
                <div>
                  <label className="block text-sm font-medium text-slate-300">
                    Speaker voice profiles
                  </label>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Save and match voice profiles across meetings.
                  </p>
                </div>
                <button
                  onClick={() => setProfilesEnabled(!profilesEnabled)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    profilesEnabled ? "bg-violet-600" : "bg-slate-700"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      profilesEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              {/* Saved profiles list — always visible so profiles can be deleted even when disabled */}
              {profiles.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  <p className="text-xs text-slate-500">{profiles.length} saved voice profile(s)</p>
                  {profiles.map((p) => (
                    <div key={p.id} className="flex items-center justify-between bg-slate-800/50 rounded-lg px-3 py-2">
                      <div>
                        <span className="text-sm text-slate-300">{p.name}</span>
                        <span className="text-[10px] text-slate-600 ml-2">{p.sample_count} sample(s)</span>
                      </div>
                      <button
                        onClick={() => handleDeleteProfile(p.id)}
                        className="text-slate-600 hover:text-red-400 transition p-1"
                        title="Delete profile"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between mt-6">
          <p className="text-xs text-slate-600">
            {tab === "models" ? "Add models by dropping .json files in model_presets/" : ""}
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

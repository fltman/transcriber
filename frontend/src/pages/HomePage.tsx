import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { listMeetings, createMeeting, createLiveMeeting, deleteMeeting, listActionResults, getActionResultExportUrl } from "../api";
import type { ActionResult } from "../types";
import { useStore } from "../store";
import AudioSourceSelect, { getAudioStream } from "../components/AudioSourceSelect";

const STATUS_LABELS: Record<string, { text: string; color: string; dot: string }> = {
  uploaded: { text: "Ready", color: "bg-sky-500/10 text-sky-400 ring-1 ring-sky-500/20", dot: "bg-sky-400" },
  processing: { text: "Processing...", color: "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20", dot: "bg-amber-400 animate-pulse" },
  recording: { text: "Recording", color: "bg-red-500/10 text-red-400 ring-1 ring-red-500/20", dot: "bg-red-400 animate-pulse" },
  finalizing: { text: "Finalizing...", color: "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20", dot: "bg-amber-400 animate-pulse" },
  completed: { text: "Done", color: "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20", dot: "bg-emerald-400" },
  failed: { text: "Failed", color: "bg-red-500/10 text-red-400 ring-1 ring-red-500/20", dot: "bg-red-400" },
};

function formatDuration(seconds: number | null): string {
  if (!seconds) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function HomePage() {
  const navigate = useNavigate();
  const { meetings, setMeetings } = useStore();
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [title, setTitle] = useState("");
  const [minSpeakers, setMinSpeakers] = useState("");
  const [maxSpeakers, setMaxSpeakers] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Recording state
  const [recording, setRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const [inputMode, setInputMode] = useState<"file" | "record" | "live">("file");

  // Action results expansion
  const [expandedMeetingId, setExpandedMeetingId] = useState<string | null>(null);
  const [meetingResults, setMeetingResults] = useState<Record<string, ActionResult[]>>({});
  const [loadingResults, setLoadingResults] = useState<string | null>(null);
  const [expandedResultId, setExpandedResultId] = useState<string | null>(null);

  async function toggleResults(e: React.MouseEvent, meetingId: string) {
    e.stopPropagation();
    if (expandedMeetingId === meetingId) {
      setExpandedMeetingId(null);
      setExpandedResultId(null);
      return;
    }
    setExpandedMeetingId(meetingId);
    setExpandedResultId(null);
    if (!meetingResults[meetingId]) {
      setLoadingResults(meetingId);
      const results = await listActionResults(meetingId);
      setMeetingResults((prev) => ({ ...prev, [meetingId]: results }));
      setLoadingResults(null);
    }
  }

  useEffect(() => {
    loadMeetings();
  }, []);

  async function loadMeetings() {
    const data = await listMeetings();
    setMeetings(data);
  }

  async function handleUpload() {
    const file = selectedFile;
    if (!file || !title.trim()) return;

    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", title.trim());
      if (minSpeakers) form.append("min_speakers", minSpeakers);
      if (maxSpeakers) form.append("max_speakers", maxSpeakers);

      const meeting = await createMeeting(form);
      setShowUpload(false);
      resetDialog();
      navigate(`/meetings/${meeting.id}`);
    } catch {
      // show inline error instead of alert
    } finally {
      setUploading(false);
    }
  }

  async function handleStartLive() {
    if (!title.trim()) return;
    setUploading(true);
    try {
      const meeting = await createLiveMeeting(title.trim());
      setShowUpload(false);
      resetDialog();
      navigate(`/meetings/${meeting.id}`);
    } catch {
      // error
    } finally {
      setUploading(false);
    }
  }

  function resetDialog() {
    setTitle("");
    setSelectedFile(null);
    setMinSpeakers("");
    setMaxSpeakers("");
    setRecording(false);
    setRecordingTime(0);
    setInputMode("file");
  }

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    if (!window.confirm("Delete this recording? This cannot be undone.")) return;
    await deleteMeeting(id);
    loadMeetings();
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setSelectedFile(file);
      if (!title) setTitle(file.name.replace(/\.[^/.]+$/, ""));
    }
  }

  // Audio recording
  const startRecording = useCallback(async () => {
    try {
      const deviceId = useStore.getState().selectedAudioDevice;
      const stream = await getAudioStream(deviceId);
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      // Audio level meter
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      function updateLevel() {
        analyser.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        setAudioLevel(avg / 128);
        animFrameRef.current = requestAnimationFrame(updateLevel);
      }
      updateLevel();

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const file = new File([blob], "recording.webm", { type: "audio/webm" });
        setSelectedFile(file);
        if (!title) setTitle("Recording " + new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }));
        stream.getTracks().forEach((t) => t.stop());
        audioCtx.close();
        cancelAnimationFrame(animFrameRef.current);
        setAudioLevel(0);
      };

      mediaRecorder.start(250);
      setRecording(true);
      setRecordingTime(0);

      timerRef.current = window.setInterval(() => {
        setRecordingTime((t) => t + 1);
      }, 1000);
    } catch {
      // microphone denied
    }
  }, [title]);

  function stopRecording() {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      clearInterval(timerRef.current);
    }
  }

  function formatRecTime(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      {/* Hero section */}
      <div className="mb-10">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Meetings</h1>
            <p className="text-slate-400 mt-1">Upload or record audio for automatic transcription</p>
          </div>
          <button
            onClick={() => setShowUpload(true)}
            className="px-5 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-medium hover:from-violet-500 hover:to-indigo-500 transition-all shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 active:scale-[0.98]"
          >
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New transcription
            </span>
          </button>
        </div>
      </div>

      {/* Upload / Record / Live dialog */}
      {showUpload && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => { setShowUpload(false); resetDialog(); }}>
          <div className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl p-6 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-white mb-5">New transcription</h2>

            {/* Toggle file / record / live */}
            <div className="flex bg-slate-800 rounded-xl p-1 mb-5">
              <button
                onClick={() => setInputMode("file")}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  inputMode === "file"
                    ? "bg-slate-700 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  Upload
                </span>
              </button>
              <button
                onClick={() => setInputMode("record")}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  inputMode === "record"
                    ? "bg-slate-700 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                  Record
                </span>
              </button>
              <button
                onClick={() => setInputMode("live")}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  inputMode === "live"
                    ? "bg-slate-700 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 bg-red-500 rounded-full" />
                  Live
                </span>
              </button>
            </div>

            {/* File upload area */}
            {inputMode === "file" && (
              <div
                className={`relative border-2 border-dashed rounded-xl p-8 text-center mb-5 transition-all cursor-pointer group ${
                  dragOver
                    ? "border-violet-500 bg-violet-500/10"
                    : selectedFile
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-slate-700 hover:border-slate-500 hover:bg-slate-800/50"
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept="audio/*,video/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setSelectedFile(f);
                      if (!title) setTitle(f.name.replace(/\.[^/.]+$/, ""));
                    }
                  }}
                />
                {selectedFile ? (
                  <div>
                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="text-white font-medium">{selectedFile.name}</p>
                    <p className="text-slate-500 text-sm mt-1">{(selectedFile.size / 1024 / 1024).toFixed(1)} MB</p>
                  </div>
                ) : (
                  <div>
                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-slate-800 flex items-center justify-center group-hover:bg-slate-700 transition">
                      <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                    </div>
                    <p className="text-slate-300 font-medium">Drag and drop a file here</p>
                    <p className="text-slate-500 text-sm mt-1">or click to browse</p>
                    <p className="text-slate-600 text-xs mt-2">MP3, WAV, MP4, M4A, WEBM</p>
                  </div>
                )}
              </div>
            )}

            {/* Recording area */}
            {inputMode === "record" && (
              <div className="rounded-xl bg-slate-800/50 border border-slate-700/50 p-8 text-center mb-5">
                {!recording && <AudioSourceSelect />}
                {!recording && !selectedFile && (
                  <div>
                    <button
                      onClick={startRecording}
                      className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center shadow-lg shadow-red-500/30 hover:shadow-red-500/50 hover:scale-105 transition-all active:scale-95"
                    >
                      <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                      </svg>
                    </button>
                    <p className="text-slate-400 mt-4 text-sm">Press to start recording</p>
                  </div>
                )}

                {recording && (
                  <div>
                    {/* Audio level visualization */}
                    <div className="flex items-center justify-center gap-1 h-16 mb-4">
                      {Array.from({ length: 32 }).map((_, i) => {
                        const h = Math.max(4, Math.min(64, audioLevel * 64 * (0.5 + Math.random() * 0.5)));
                        return (
                          <div
                            key={i}
                            className="w-1.5 rounded-full bg-gradient-to-t from-red-500 to-rose-400 transition-all duration-75"
                            style={{ height: `${h}px` }}
                          />
                        );
                      })}
                    </div>

                    <div className="flex items-center justify-center gap-3 mb-4">
                      <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                      <span className="text-2xl font-mono font-bold text-white">{formatRecTime(recordingTime)}</span>
                    </div>

                    <button
                      onClick={stopRecording}
                      className="px-6 py-2.5 bg-slate-700 text-white rounded-xl font-medium hover:bg-slate-600 transition"
                    >
                      <span className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <rect x="6" y="6" width="12" height="12" rx="2" />
                        </svg>
                        Stop recording
                      </span>
                    </button>
                  </div>
                )}

                {!recording && selectedFile && inputMode === "record" && (
                  <div>
                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="text-white font-medium">Recording complete</p>
                    <p className="text-slate-400 text-sm mt-1">{formatRecTime(recordingTime)}</p>
                    <button
                      onClick={() => { setSelectedFile(null); setRecordingTime(0); }}
                      className="text-sm text-slate-500 hover:text-white mt-3 transition"
                    >
                      Record again
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Live mode info */}
            {inputMode === "live" && (
              <div className="rounded-xl bg-slate-800/50 border border-red-500/20 p-8 text-center mb-5">
                <AudioSourceSelect />
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
                  <div className="relative">
                    <span className="w-4 h-4 bg-red-500 rounded-full block" />
                    <span className="absolute inset-0 w-4 h-4 bg-red-500 rounded-full animate-ping opacity-50" />
                  </div>
                </div>
                <h3 className="text-white font-semibold mb-2">Live Transcription</h3>
                <p className="text-slate-400 text-sm max-w-xs mx-auto">
                  Transcription happens in real-time as you speak. Speaker names are progressively refined in the background.
                </p>
              </div>
            )}

            {/* Title */}
            <input
              type="text"
              placeholder="Title for the transcription"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 mb-4"
            />

            {/* Optional: speaker count (not for live) */}
            {inputMode !== "live" && (
              <details className="mb-5 group">
                <summary className="text-sm text-slate-500 cursor-pointer hover:text-slate-300 transition">
                  Advanced settings
                </summary>
                <div className="flex gap-3 mt-3">
                  <input
                    type="number"
                    placeholder="Min speakers"
                    value={minSpeakers}
                    onChange={(e) => setMinSpeakers(e.target.value)}
                    className="flex-1 bg-slate-800 border border-slate-700/50 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                    min="1"
                  />
                  <input
                    type="number"
                    placeholder="Max speakers"
                    value={maxSpeakers}
                    onChange={(e) => setMaxSpeakers(e.target.value)}
                    className="flex-1 bg-slate-800 border border-slate-700/50 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                    min="1"
                  />
                </div>
              </details>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowUpload(false); resetDialog(); }}
                className="px-5 py-2.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition"
              >
                Cancel
              </button>
              {inputMode === "live" ? (
                <button
                  onClick={handleStartLive}
                  disabled={uploading || !title.trim()}
                  className="px-5 py-2.5 bg-gradient-to-r from-red-600 to-rose-600 text-white rounded-xl font-medium hover:from-red-500 hover:to-rose-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-red-500/25"
                >
                  {uploading ? (
                    <span className="flex items-center gap-2">
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Starting...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 bg-white rounded-full" />
                      Start live session
                    </span>
                  )}
                </button>
              ) : (
                <button
                  onClick={handleUpload}
                  disabled={uploading || !selectedFile || !title.trim()}
                  className="px-5 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-medium hover:from-violet-500 hover:to-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-violet-500/25"
                >
                  {uploading ? (
                    <span className="flex items-center gap-2">
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Uploading...
                    </span>
                  ) : (
                    "Start transcription"
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Meeting list */}
      {meetings.length === 0 ? (
        <div className="text-center py-24">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center">
            <svg className="w-10 h-10 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          </div>
          <h3 className="text-xl font-semibold text-slate-300">No meetings yet</h3>
          <p className="text-slate-500 mt-2 max-w-sm mx-auto">
            Upload an audio or video file, or record directly from the browser to start transcribing.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {meetings.map((m) => {
            const badge = STATUS_LABELS[m.status] || { text: m.status, color: "bg-slate-800 text-slate-400", dot: "bg-slate-500" };
            const isExpanded = expandedMeetingId === m.id;
            const results = meetingResults[m.id] || [];
            const completedResults = results.filter((r) => r.status === "completed");
            return (
              <div
                key={m.id}
                className="group bg-slate-900/50 border border-slate-800/50 rounded-xl hover:border-slate-700/50 transition-all"
              >
                <div
                  onClick={() => navigate(`/meetings/${m.id}`)}
                  className="p-5 cursor-pointer hover:bg-slate-800/50 rounded-xl transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-white group-hover:text-violet-300 transition truncate flex items-center gap-2">
                        {m.is_encrypted && (
                          <svg className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                          </svg>
                        )}
                        {m.title}
                      </h3>
                      <div className="flex items-center gap-3 mt-1.5 text-sm text-slate-500">
                        <span>{formatDate(m.created_at)}</span>
                        <span className="w-1 h-1 rounded-full bg-slate-700" />
                        <span>{formatDuration(m.duration)}</span>
                        {m.mode === "live" && (
                          <>
                            <span className="w-1 h-1 rounded-full bg-slate-700" />
                            <span className="text-red-400 text-xs font-medium">LIVE</span>
                          </>
                        )}
                        {m.speaker_count > 0 && (
                          <>
                            <span className="w-1 h-1 rounded-full bg-slate-700" />
                            <span>{m.speaker_count} speakers</span>
                          </>
                        )}
                        {m.segment_count > 0 && (
                          <>
                            <span className="w-1 h-1 rounded-full bg-slate-700" />
                            <span>{m.segment_count} segments</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 ml-4">
                      {m.status === "completed" && (
                        <button
                          onClick={(e) => toggleResults(e, m.id)}
                          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                            isExpanded
                              ? "bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/30"
                              : "text-slate-500 hover:text-violet-400 hover:bg-slate-800"
                          }`}
                          title="Show action results"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          Versions
                          <svg
                            className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                      )}
                      <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${badge.color}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                        {badge.text}
                      </span>
                      <button
                        onClick={(e) => handleDelete(e, m.id)}
                        className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all p-1"
                        title="Delete"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded action results */}
                {isExpanded && (
                  <div className="border-t border-slate-800/50 px-5 pb-4 pt-3" onClick={(e) => e.stopPropagation()}>
                    {loadingResults === m.id ? (
                      <div className="flex items-center gap-2 text-sm text-slate-500 py-2">
                        <div className="w-3.5 h-3.5 border border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
                        Loading...
                      </div>
                    ) : completedResults.length === 0 ? (
                      <p className="text-sm text-slate-600 py-2">No action results yet. Open the meeting and run an action.</p>
                    ) : (
                      <div className="space-y-2">
                        {completedResults.map((r) => {
                          const isResultExpanded = expandedResultId === r.id;
                          return (
                            <div key={r.id} className="rounded-lg bg-slate-800/40 border border-slate-700/30 overflow-hidden">
                              <button
                                onClick={() => setExpandedResultId(isResultExpanded ? null : r.id)}
                                className="w-full flex items-center justify-between px-3.5 py-2.5 text-left hover:bg-slate-800/60 transition"
                              >
                                <div className="flex items-center gap-2.5 min-w-0">
                                  <svg
                                    className={`w-3.5 h-3.5 text-slate-500 transition-transform flex-shrink-0 ${isResultExpanded ? "rotate-90" : ""}`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                  </svg>
                                  <span className="text-sm text-slate-300 font-medium truncate">{r.action_name}</span>
                                </div>
                                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                                  <span className="text-[10px] text-slate-600">
                                    {new Date(r.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                                  </span>
                                  <div className="relative group/dl" onClick={(ev) => ev.stopPropagation()}>
                                    <button className="p-1 pb-2 text-slate-600 hover:text-violet-400 transition">
                                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                                      </svg>
                                    </button>
                                    <div className="absolute right-0 top-full bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 hidden group-hover/dl:block z-10 min-w-[80px]">
                                      {["md", "docx", "pdf", "txt"].map((fmt) => (
                                        <a
                                          key={fmt}
                                          href={getActionResultExportUrl(r.id, fmt)}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="block px-3 py-1.5 text-[11px] text-slate-300 hover:bg-slate-700 hover:text-white transition"
                                        >
                                          {fmt.toUpperCase()}
                                        </a>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                              </button>
                              {isResultExpanded && r.is_encrypted && (
                                <div className="px-3.5 pb-3.5 border-t border-slate-700/30">
                                  <div className="flex items-center gap-2.5 py-4 text-amber-400/80">
                                    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                    </svg>
                                    <span className="text-sm">This version is encrypted. Unlock the meeting to view.</span>
                                  </div>
                                </div>
                              )}
                              {isResultExpanded && r.result_text && !r.is_encrypted && (
                                <div className="px-3.5 pb-3.5 border-t border-slate-700/30">
                                  <div className="flex justify-end gap-3 mt-2 mb-1">
                                    <div className="relative group/dl2" onClick={(ev) => ev.stopPropagation()}>
                                      <button className="text-[10px] text-slate-500 hover:text-violet-400 transition flex items-center gap-1 pb-1">
                                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                                        </svg>
                                        Download
                                      </button>
                                      <div className="absolute right-0 top-full bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 hidden group-hover/dl2:block z-10 min-w-[80px]">
                                        {["md", "docx", "pdf", "txt"].map((fmt) => (
                                          <a
                                            key={fmt}
                                            href={getActionResultExportUrl(r.id, fmt)}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="block px-3 py-1.5 text-[11px] text-slate-300 hover:bg-slate-700 hover:text-white transition"
                                          >
                                            {fmt.toUpperCase()}
                                          </a>
                                        ))}
                                      </div>
                                    </div>
                                    <button
                                      onClick={() => navigator.clipboard.writeText(r.result_text!)}
                                      className="text-[10px] text-slate-500 hover:text-violet-400 transition flex items-center gap-1"
                                    >
                                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                      </svg>
                                      Copy
                                    </button>
                                  </div>
                                  <div className="max-h-96 overflow-y-auto text-sm leading-relaxed">
                                    <ReactMarkdown
                                      components={{
                                        h1: ({ children }) => <h1 className="text-base font-bold text-slate-200 mt-3 mb-1.5">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-sm font-bold text-slate-200 mt-3 mb-1.5">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-sm font-semibold text-slate-300 mt-2 mb-1">{children}</h3>,
                                        p: ({ children }) => <p className="text-slate-400 mb-2">{children}</p>,
                                        strong: ({ children }) => <strong className="text-slate-200 font-semibold">{children}</strong>,
                                        em: ({ children }) => <em className="text-slate-300 italic">{children}</em>,
                                        ul: ({ children }) => <ul className="list-disc list-inside text-slate-400 mb-2 space-y-0.5">{children}</ul>,
                                        ol: ({ children }) => <ol className="list-decimal list-inside text-slate-400 mb-2 space-y-0.5">{children}</ol>,
                                        li: ({ children }) => <li className="text-slate-400">{children}</li>,
                                        hr: () => <hr className="border-slate-700/50 my-2" />,
                                        blockquote: ({ children }) => <blockquote className="border-l-2 border-violet-500/30 pl-3 my-2 text-slate-500 italic">{children}</blockquote>,
                                        code: ({ children }) => <code className="bg-slate-800 text-violet-300 px-1 py-0.5 rounded text-xs">{children}</code>,
                                      }}
                                    >
                                      {r.result_text}
                                    </ReactMarkdown>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}

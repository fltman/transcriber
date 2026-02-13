import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getMeeting, startProcessing, getJobs } from "../api";
import { useStore } from "../store";
import type { ProgressUpdate } from "../types";
import TranscriptView from "../components/TranscriptView";
import SpeakerPanel from "../components/SpeakerPanel";
import AudioPlayer from "../components/AudioPlayer";
import ProgressTracker from "../components/ProgressTracker";
import ExportDialog from "../components/ExportDialog";

export default function MeetingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentMeeting, setCurrentMeeting, progress, setProgress } = useStore();
  const [showExport, setShowExport] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (!id) return;
    loadMeeting();
    connectWebSocket();
    return () => {
      wsRef.current?.close();
      setCurrentMeeting(null);
      setProgress(null);
    };
  }, [id]);

  async function loadMeeting() {
    if (!id) return;
    const m = await getMeeting(id);
    setCurrentMeeting(m);
    if (m.status === "processing") {
      const jobs = await getJobs(id);
      const active = jobs.find((j) => j.status === "running" || j.status === "pending");
      if (active) {
        setProgress({ type: "progress", progress: active.progress, step: active.current_step || "Processing...", status: "processing" });
      }
    }
  }

  function connectWebSocket() {
    if (!id) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/meetings/${id}`);
    wsRef.current = ws;
    ws.onmessage = (event) => {
      const data: ProgressUpdate = JSON.parse(event.data);
      if (data.type === "ping") return;
      setProgress(data);
      if (data.type === "progress" && data.progress === 100) {
        setTimeout(() => loadMeeting(), 500);
      }
      if (data.type === "error") {
        setTimeout(() => loadMeeting(), 500);
      }
    };
    ws.onclose = () => {
      setTimeout(() => {
        if (document.visibilityState === "visible") connectWebSocket();
      }, 3000);
    };
  }

  async function handleProcess() {
    if (!id) return;
    await startProcessing(id);
    setProgress({ type: "progress", progress: 0, step: "Starting...", status: "processing" });
    loadMeeting();
  }

  if (!currentMeeting) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-10 h-10 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  const isProcessing = currentMeeting.status === "processing";
  const isCompleted = currentMeeting.status === "completed";
  const isUploaded = currentMeeting.status === "uploaded";
  const isFailed = currentMeeting.status === "failed";

  return (
    <main className="max-w-7xl mx-auto px-6 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate("/")}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-xl font-bold text-white">{currentMeeting.title}</h1>
            {currentMeeting.duration && (
              <p className="text-sm text-slate-500 mt-0.5">
                {Math.floor(currentMeeting.duration / 60)}:{Math.floor(currentMeeting.duration % 60).toString().padStart(2, "0")} min
                {currentMeeting.speaker_count > 0 && ` \u00B7 ${currentMeeting.speaker_count} speakers`}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isUploaded && (
            <button
              onClick={handleProcess}
              className="px-5 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-medium hover:from-violet-500 hover:to-indigo-500 transition-all shadow-lg shadow-violet-500/25"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Start transcription
              </span>
            </button>
          )}
          {isFailed && (
            <button
              onClick={handleProcess}
              className="px-5 py-2.5 bg-gradient-to-r from-amber-600 to-orange-600 text-white rounded-xl font-medium hover:from-amber-500 hover:to-orange-500 transition-all shadow-lg shadow-amber-500/25"
            >
              Retry
            </button>
          )}
          {isCompleted && (
            <button
              onClick={() => setShowExport(true)}
              className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl font-medium hover:from-emerald-500 hover:to-teal-500 transition-all shadow-lg shadow-emerald-500/25"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Export
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Progress */}
      {(isProcessing || (progress && progress.progress !== undefined && progress.progress < 100)) && (
        <ProgressTracker progress={progress} />
      )}

      {/* Failed state */}
      {isFailed && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-5 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L4.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-red-400">Processing failed</p>
              {progress?.error && <p className="text-red-400/70 text-sm mt-0.5">{progress.error}</p>}
            </div>
          </div>
        </div>
      )}

      {/* Completed: show transcript */}
      {isCompleted && currentMeeting.segments && (
        <>
          <AudioPlayer meetingId={currentMeeting.id} audioRef={audioRef} />
          <div className="flex gap-6 mt-5">
            <div className="flex-1 min-w-0">
              <TranscriptView
                segments={currentMeeting.segments}
                speakers={currentMeeting.speakers || []}
                audioRef={audioRef}
                onUpdate={loadMeeting}
              />
            </div>
            <div className="w-72 flex-shrink-0">
              <SpeakerPanel
                speakers={currentMeeting.speakers || []}
                segments={currentMeeting.segments}
                onUpdate={loadMeeting}
              />
            </div>
          </div>
        </>
      )}

      {/* Uploaded but not started */}
      {isUploaded && (
        <div className="text-center py-20">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center">
            <svg className="w-10 h-10 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-xl font-semibold text-slate-300">Ready to transcribe</h3>
          <p className="text-slate-500 mt-2">Click "Start transcription" to begin processing</p>
        </div>
      )}

      {showExport && (
        <ExportDialog meetingId={currentMeeting.id} onClose={() => setShowExport(false)} />
      )}
    </main>
  );
}

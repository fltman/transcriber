import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getMeeting, startProcessing, getJobs } from "../api";
import { useStore } from "../store";
import type { ProgressUpdate } from "../types";
import TranscriptView from "../components/TranscriptView";
import SpeakerPanel from "../components/SpeakerPanel";
import ActionsPanel from "../components/ActionsPanel";
import AudioPlayer from "../components/AudioPlayer";
import ProgressTracker from "../components/ProgressTracker";
import ExportDialog from "../components/ExportDialog";
import EncryptDialog from "../components/EncryptDialog";
import DecryptDialog from "../components/DecryptDialog";
import LiveRecordingBar from "../components/LiveRecordingBar";
import { useLiveRecording } from "../hooks/useLiveRecording";

export default function MeetingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    currentMeeting, setCurrentMeeting,
    progress, setProgress,
    liveSegments, setLiveSegments,
    liveSpeakers, setLiveSpeakers,
    polishNotification, setPolishNotification,
  } = useStore();
  const [showExport, setShowExport] = useState(false);
  const [showEncrypt, setShowEncrypt] = useState(false);
  const [showDecrypt, setShowDecrypt] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<"speakers" | "actions">("speakers");
  const [actionEvent, setActionEvent] = useState<ProgressUpdate | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const isLiveMode = currentMeeting?.mode === "live";
  const isRecording = currentMeeting?.status === "recording";

  const selectedAudioDevice = useStore((s) => s.selectedAudioDevice);

  const liveRecording = useLiveRecording({
    meetingId: id || "",
    deviceId: selectedAudioDevice,
    onFinalizeComplete: () => {
      setTimeout(() => loadMeeting(), 500);
    },
  });

  // Auto-start recording when entering a live meeting in recording state
  const hasAutoStarted = useRef(false);
  useEffect(() => {
    if (isRecording && isLiveMode && !liveRecording.isRecording && !hasAutoStarted.current) {
      hasAutoStarted.current = true;
      liveRecording.start().catch(console.error);
    }
  }, [isRecording, isLiveMode, liveRecording]);

  useEffect(() => {
    if (!id) return;
    loadMeeting();

    // Only connect progress WS for non-live upload mode
    // (live mode uses its own WS via useLiveRecording)
    return () => {
      wsRef.current?.close();
      setCurrentMeeting(null);
      setProgress(null);
      setLiveSegments([]);
      setLiveSpeakers([]);
      setPolishNotification(null);
    };
  }, [id]);

  useEffect(() => {
    if (!id || isLiveMode) return;
    connectWebSocket();
    return () => {
      wsRef.current?.close();
    };
  }, [id, isLiveMode]);

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
    if (m.status === "finalizing") {
      const jobs = await getJobs(id);
      const active = jobs.find((j) => j.status === "running" || j.status === "pending");
      if (active) {
        setProgress({ type: "progress", progress: active.progress, step: active.current_step || "Finalizing...", status: "finalizing" });
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
      if (data.type === "action_running" || data.type === "action_completed" || data.type === "action_failed") {
        setActionEvent(data);
        return;
      }
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
  const isFinalizing = currentMeeting.status === "finalizing" || liveRecording.isFinalizing;

  // Build speaker list for live mode (memoized to avoid recalculation on every render)
  const derivedLiveSpeakers = useMemo(() => {
    if (liveSpeakers.length > 0) return liveSpeakers;
    const speakerMap = new Map<string, { id: string; label: string; name: string; color: string }>();
    for (const seg of liveSegments) {
      if (seg.speaker_id && !speakerMap.has(seg.speaker_id)) {
        speakerMap.set(seg.speaker_id, {
          id: seg.speaker_id,
          label: seg.speaker_label || "",
          name: seg.speaker_name || seg.speaker_label || "Unknown",
          color: seg.speaker_color || "#6366f1",
        });
      }
    }
    return Array.from(speakerMap.values()).map((s) => ({
      id: s.id,
      meeting_id: id || "",
      label: s.label,
      display_name: s.name,
      color: s.color,
      identified_by: null,
      confidence: null,
      total_speaking_time: liveSegments
        .filter((seg) => seg.speaker_id === s.id)
        .reduce((sum, seg) => sum + (seg.end_time - seg.start_time), 0),
      segment_count: liveSegments.filter((seg) => seg.speaker_id === s.id).length,
    }));
  }, [liveSpeakers, liveSegments, id]);

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
            <p className="text-sm text-slate-500 mt-0.5">
              {currentMeeting.duration ? (
                <>
                  {Math.floor(currentMeeting.duration / 60)}:{Math.floor(currentMeeting.duration % 60).toString().padStart(2, "0")} min
                  {currentMeeting.speaker_count > 0 && ` \u00B7 ${currentMeeting.speaker_count} speakers`}
                </>
              ) : isLiveMode && isRecording ? (
                <>
                  <span className="text-red-400">Live recording</span>
                  <span className="ml-2 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded">Beta</span>
                </>
              ) : null}
            </p>
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
            <>
              {currentMeeting.is_encrypted ? (
                <button
                  onClick={() => setShowDecrypt(true)}
                  className="px-4 py-2.5 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-xl font-medium hover:bg-amber-500/30 transition-all"
                  title="Unlock meeting"
                >
                  <span className="flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    Unlock
                  </span>
                </button>
              ) : (
                <button
                  onClick={() => setShowEncrypt(true)}
                  className="px-4 py-2.5 bg-slate-800 text-slate-400 border border-slate-700/50 rounded-xl font-medium hover:text-amber-400 hover:border-amber-500/30 hover:bg-amber-500/10 transition-all"
                  title="Encrypt meeting"
                >
                  <span className="flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                    </svg>
                    Encrypt
                  </span>
                </button>
              )}
              <button
                onClick={() => setShowExport(true)}
                disabled={currentMeeting.is_encrypted}
                className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl font-medium hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/25"
              >
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export
                </span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Live recording bar */}
      {isLiveMode && liveRecording.isRecording && (
        <LiveRecordingBar
          recordingTime={liveRecording.recordingTime}
          audioLevel={liveRecording.audioLevel}
          onStop={liveRecording.stop}
        />
      )}

      {/* Polish notification toast */}
      {polishNotification && (
        <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2">
          <div className="bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 px-4 py-2.5 rounded-xl text-sm font-medium backdrop-blur-sm shadow-lg">
            {polishNotification}
          </div>
        </div>
      )}

      {/* Progress (processing or finalizing) */}
      {(isProcessing || isFinalizing) && progress && (
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

      {/* Live mode: recording/live view with real-time segments */}
      {isLiveMode && (isRecording || liveRecording.isRecording) && liveSegments.length > 0 && (
        <div className="flex gap-6">
          <div className="flex-1 min-w-0">
            <TranscriptView
              segments={liveSegments}
              speakers={derivedLiveSpeakers}
              audioRef={audioRef}
              onUpdate={loadMeeting}
              isLive
            />
          </div>
          {derivedLiveSpeakers.length > 0 && (
            <div className="w-72 flex-shrink-0">
              <SpeakerPanel
                speakers={derivedLiveSpeakers}
                segments={liveSegments}
                onUpdate={loadMeeting}
              />
            </div>
          )}
        </div>
      )}

      {/* Live mode: waiting for segments */}
      {isLiveMode && (isRecording || liveRecording.isRecording) && liveSegments.length === 0 && (
        <div className="text-center py-20">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
          </div>
          <h3 className="text-lg font-semibold text-slate-300">Listening...</h3>
          <p className="text-slate-500 mt-1 text-sm">Transcription will appear as you speak</p>
        </div>
      )}

      {/* Encrypted overlay */}
      {isCompleted && currentMeeting.is_encrypted && (
        <div className="text-center py-20">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <svg className="w-10 h-10 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h3 className="text-xl font-semibold text-slate-300">Meeting is encrypted</h3>
          <p className="text-slate-500 mt-2 max-w-sm mx-auto">
            This transcript is protected with a password. Click "Unlock" to decrypt and view.
          </p>
          <button
            onClick={() => setShowDecrypt(true)}
            className="mt-6 px-6 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-medium hover:from-violet-500 hover:to-indigo-500 transition-all shadow-lg shadow-violet-500/25"
          >
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
              </svg>
              Unlock meeting
            </span>
          </button>
        </div>
      )}

      {/* Completed: show transcript */}
      {isCompleted && currentMeeting.segments && !currentMeeting.is_encrypted && (
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
              {/* Sidebar tab toggle */}
              <div className="flex rounded-lg bg-slate-800/50 p-0.5 mb-3">
                <button
                  onClick={() => setSidebarTab("speakers")}
                  className={`flex-1 text-xs font-medium py-1.5 rounded-md transition ${
                    sidebarTab === "speakers"
                      ? "bg-slate-700 text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  Speakers
                </button>
                <button
                  onClick={() => setSidebarTab("actions")}
                  className={`flex-1 text-xs font-medium py-1.5 rounded-md transition ${
                    sidebarTab === "actions"
                      ? "bg-slate-700 text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  Actions
                </button>
              </div>
              {sidebarTab === "speakers" ? (
                <SpeakerPanel
                  speakers={currentMeeting.speakers || []}
                  segments={currentMeeting.segments}
                  onUpdate={loadMeeting}
                />
              ) : (
                <ActionsPanel
                  meetingId={currentMeeting.id}
                  onResultEvent={actionEvent}
                />
              )}
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

      {showEncrypt && (
        <EncryptDialog
          meetingId={currentMeeting.id}
          onClose={() => setShowEncrypt(false)}
          onEncrypted={loadMeeting}
        />
      )}

      {showDecrypt && (
        <DecryptDialog
          meetingId={currentMeeting.id}
          onClose={() => setShowDecrypt(false)}
          onDecrypted={loadMeeting}
        />
      )}
    </main>
  );
}

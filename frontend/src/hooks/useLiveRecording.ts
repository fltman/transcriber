import { useRef, useState, useCallback, useEffect } from "react";
import { useStore } from "../store";
import { getAudioStream } from "../components/AudioSourceSelect";
import type { ProgressUpdate } from "../types";

interface UseLiveRecordingOptions {
  meetingId: string;
  deviceId?: string;
  onFinalizeComplete?: () => void;
}

export function useLiveRecording({ meetingId, deviceId, onFinalizeComplete }: UseLiveRecordingOptions) {
  const { addLiveSegment, setLiveSegments, setLiveSpeakers, reassignSegmentSpeakers, setPolishNotification, setProgress } = useStore();

  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isFinalizing, setIsFinalizing] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<number>(0);
  const chunkIntervalRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  function cleanup() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
    }
    cancelAnimationFrame(animFrameRef.current);
    clearInterval(timerRef.current);
    clearInterval(chunkIntervalRef.current);
    if (wsRef.current) {
      wsRef.current.close();
    }
  }

  const connectWebSocket = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/live/${meetingId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data: ProgressUpdate = JSON.parse(event.data);

        switch (data.type) {
          case "live_segment":
            if (data.segment) {
              addLiveSegment(data.segment);
            }
            break;

          case "polish_started":
            setPolishNotification("Updating speaker names...");
            break;

          case "polish_complete":
            if (data.segments) setLiveSegments(data.segments);
            if (data.speakers) setLiveSpeakers(data.speakers);
            setPolishNotification("Speaker names updated");
            setTimeout(() => setPolishNotification(null), 4000);
            break;

          case "finalize_started":
            setIsFinalizing(true);
            setProgress({
              type: "progress",
              progress: 0,
              step: data.message || "Finalizing...",
              status: "finalizing",
            });
            break;

          case "finalize_complete":
            setIsFinalizing(false);
            setProgress(null);
            onFinalizeComplete?.();
            break;

          case "progress":
            setProgress(data);
            break;

          case "speaker_reassignment":
            if (data.segments) reassignSegmentSpeakers(data.segments);
            if (data.speakers) setLiveSpeakers(data.speakers);
            setPolishNotification("Speakers re-analyzed");
            setTimeout(() => setPolishNotification(null), 4000);
            break;

          case "error":
            console.error("Live WS error:", data.error);
            break;
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      // Reconnect if still recording
      if (isRecording) {
        setTimeout(() => connectWebSocket(), 2000);
      }
    };

    return ws;
  }, [meetingId, isRecording]);

  const start = useCallback(async () => {
    // Connect WebSocket first
    const ws = connectWebSocket();

    // Wait for WS to open
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error("WebSocket connection failed"));
      setTimeout(() => reject(new Error("WebSocket timeout")), 5000);
    });

    // Get audio stream (mic or system audio)
    const stream = await getAudioStream(deviceId || "default");
    streamRef.current = stream;

    // Audio level meter
    const audioCtx = new AudioContext();
    audioCtxRef.current = audioCtx;
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

    // MediaRecorder — cycle stop/start every 4s so each blob is a
    // complete, self-contained WebM file (with headers). Using the
    // timeslice parameter produces continuation blobs without EBML
    // headers that FFmpeg cannot decode.
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType: "audio/webm;codecs=opus",
    });
    mediaRecorderRef.current = mediaRecorder;

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
        e.data.arrayBuffer().then((buf) => {
          ws.send(buf);
        });
      }
    };

    mediaRecorder.start();
    setIsRecording(true);
    setRecordingTime(0);

    // Cycle stop/start every 4s to get complete WebM files
    chunkIntervalRef.current = window.setInterval(() => {
      if (mediaRecorder.state === "recording") {
        mediaRecorder.stop();   // triggers ondataavailable with complete WebM
        mediaRecorder.start();  // restart immediately
      }
    }, 4000);

    timerRef.current = window.setInterval(() => {
      setRecordingTime((t) => t + 1);
    }, 1000);
  }, [meetingId, deviceId, connectWebSocket]);

  const stop = useCallback(() => {
    // Stop chunk cycling first
    clearInterval(chunkIntervalRef.current);

    // Stop the MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }

    // Stop audio tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
    }
    cancelAnimationFrame(animFrameRef.current);
    clearInterval(timerRef.current);
    setIsRecording(false);
    setAudioLevel(0);

    // Send stop command to server
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop_recording" }));
    }

    setIsFinalizing(true);
  }, []);

  return {
    start,
    stop,
    isRecording,
    recordingTime,
    audioLevel,
    isFinalizing,
  };
}

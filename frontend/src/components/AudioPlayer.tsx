import { useEffect, useState } from "react";
import { getAudioUrl } from "../api";
import { useStore } from "../store";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  meetingId: string;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}

export default function AudioPlayer({ meetingId, audioRef }: Props) {
  const { setCurrentTime } = useStore();
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [time, setTime] = useState(0);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTimeUpdate = () => { setTime(audio.currentTime); setCurrentTime(audio.currentTime); };
    const onLoaded = () => setDuration(audio.duration);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
    };
  }, [audioRef]);

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    playing ? audio.pause() : audio.play();
  }

  function seek(e: React.ChangeEvent<HTMLInputElement>) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = parseFloat(e.target.value);
  }

  function changeSpeed() {
    const audio = audioRef.current;
    if (!audio) return;
    const speeds = [0.5, 0.75, 1, 1.25, 1.5, 2];
    const idx = speeds.indexOf(speed);
    const next = speeds[(idx + 1) % speeds.length];
    audio.playbackRate = next;
    setSpeed(next);
  }

  function skip(seconds: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, Math.min(duration, audio.currentTime + seconds));
  }

  const progressPct = duration > 0 ? (time / duration) * 100 : 0;

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/50 p-4 backdrop-blur-sm">
      <audio ref={audioRef as React.RefObject<HTMLAudioElement>} src={getAudioUrl(meetingId)} preload="metadata" />

      <div className="flex items-center gap-4">
        {/* Skip back */}
        <button onClick={() => skip(-10)} className="text-slate-500 hover:text-white transition" title="-10s">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.334 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z" />
          </svg>
        </button>

        {/* Play/pause */}
        <button
          onClick={togglePlay}
          className="w-11 h-11 flex items-center justify-center bg-gradient-to-br from-violet-500 to-indigo-600 text-white rounded-full hover:from-violet-400 hover:to-indigo-500 transition-all shadow-lg shadow-violet-500/25 active:scale-95"
        >
          {playing ? (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" /></svg>
          ) : (
            <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
          )}
        </button>

        {/* Skip forward */}
        <button onClick={() => skip(10)} className="text-slate-500 hover:text-white transition" title="+10s">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8l5.333-4zM19.933 12.8a1 1 0 000-1.6l-5.333-4A1 1 0 0013 8v8a1 1 0 001.6.8l5.333-4z" />
          </svg>
        </button>

        {/* Time */}
        <span className="text-sm text-slate-400 font-mono w-28 text-center tabular-nums">
          {formatTime(time)} / {formatTime(duration)}
        </span>

        {/* Progress bar */}
        <div className="flex-1 relative group">
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-150"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <input
            type="range"
            min="0"
            max={duration || 0}
            value={time}
            onChange={seek}
            step="0.1"
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
        </div>

        {/* Speed */}
        <button
          onClick={changeSpeed}
          className="text-xs font-mono bg-slate-800 text-slate-400 px-2.5 py-1.5 rounded-lg hover:bg-slate-700 hover:text-white transition"
        >
          {speed}x
        </button>
      </div>
    </div>
  );
}

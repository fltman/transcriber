import { useEffect, useState } from "react";
import { useStore } from "../store";

export async function getAudioStream(deviceId: string): Promise<MediaStream> {
  if (deviceId === "system") {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: { width: 1, height: 1 },
      audio: true,
    });
    // Stop the throwaway video track, keep only audio
    stream.getVideoTracks().forEach((t) => t.stop());
    if (stream.getAudioTracks().length === 0) {
      throw new Error("No audio track captured. Make sure to share a tab with audio enabled.");
    }
    return stream;
  }

  if (deviceId && deviceId !== "default") {
    return navigator.mediaDevices.getUserMedia({
      audio: { deviceId: { exact: deviceId } },
    });
  }

  return navigator.mediaDevices.getUserMedia({ audio: true });
}

export default function AudioSourceSelect() {
  const { selectedAudioDevice, setSelectedAudioDevice } = useStore();
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);

  async function enumerate() {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(all.filter((d) => d.kind === "audioinput"));
    } catch {
      // Permission denied or not available
    }
  }

  useEffect(() => {
    enumerate();
    navigator.mediaDevices.addEventListener("devicechange", enumerate);
    return () => {
      navigator.mediaDevices.removeEventListener("devicechange", enumerate);
    };
  }, []);

  return (
    <div className="mb-3">
      <label className="block text-xs text-slate-500 mb-1.5">Audio source</label>
      <select
        value={selectedAudioDevice}
        onChange={(e) => setSelectedAudioDevice(e.target.value)}
        className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 appearance-none cursor-pointer"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 0.75rem center",
          paddingRight: "2rem",
        }}
      >
        <option value="default">Default microphone</option>
        {devices
          .filter((d) => d.deviceId && d.deviceId !== "default")
          .map((d) => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label || `Microphone (${d.deviceId.slice(0, 8)}...)`}
            </option>
          ))}
        <option value="system">System audio (screen share)</option>
      </select>
    </div>
  );
}

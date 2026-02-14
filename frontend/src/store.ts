import { create } from "zustand";
import type { Meeting, Segment, Speaker, ProgressUpdate } from "./types";

interface AppState {
  meetings: Meeting[];
  setMeetings: (m: Meeting[]) => void;

  currentMeeting: Meeting | null;
  setCurrentMeeting: (m: Meeting | null) => void;

  progress: ProgressUpdate | null;
  setProgress: (p: ProgressUpdate | null) => void;

  currentTime: number;
  setCurrentTime: (t: number) => void;

  playingSegmentId: string | null;
  setPlayingSegmentId: (id: string | null) => void;

  // Live mode state
  liveSegments: Segment[];
  addLiveSegment: (s: Segment) => void;
  setLiveSegments: (s: Segment[]) => void;

  liveSpeakers: Speaker[];
  setLiveSpeakers: (s: Speaker[]) => void;

  reassignSegmentSpeakers: (updates: { id: string; speaker_id: string | null; speaker_label: string | null; speaker_name: string | null; speaker_color: string | null }[]) => void;

  polishNotification: string | null;
  setPolishNotification: (n: string | null) => void;

  selectedAudioDevice: string;
  setSelectedAudioDevice: (d: string) => void;
}

export const useStore = create<AppState>((set) => ({
  meetings: [],
  setMeetings: (meetings) => set({ meetings }),

  currentMeeting: null,
  setCurrentMeeting: (currentMeeting) => set({ currentMeeting }),

  progress: null,
  setProgress: (progress) => set({ progress }),

  currentTime: 0,
  setCurrentTime: (currentTime) => set({ currentTime }),

  playingSegmentId: null,
  setPlayingSegmentId: (playingSegmentId) => set({ playingSegmentId }),

  // Live mode
  liveSegments: [],
  addLiveSegment: (s) => set((state) => ({ liveSegments: [...state.liveSegments, s] })),
  setLiveSegments: (liveSegments) => set({ liveSegments }),

  liveSpeakers: [],
  setLiveSpeakers: (liveSpeakers) => set({ liveSpeakers }),

  reassignSegmentSpeakers: (updates) =>
    set((state) => {
      const updateMap = new Map(updates.map((u) => [u.id, u]));
      return {
        liveSegments: state.liveSegments.map((seg) => {
          const upd = updateMap.get(seg.id);
          if (upd) {
            return { ...seg, speaker_id: upd.speaker_id, speaker_label: upd.speaker_label, speaker_name: upd.speaker_name, speaker_color: upd.speaker_color };
          }
          return seg;
        }),
      };
    }),

  polishNotification: null,
  setPolishNotification: (polishNotification) => set({ polishNotification }),

  selectedAudioDevice: "default",
  setSelectedAudioDevice: (selectedAudioDevice) => set({ selectedAudioDevice }),
}));

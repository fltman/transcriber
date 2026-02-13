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
}));

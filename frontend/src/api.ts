import axios from "axios";
import type { Meeting, Segment, Speaker, Job } from "./types";

const api = axios.create({ baseURL: "/api" });

export async function listMeetings(): Promise<Meeting[]> {
  const { data } = await api.get("/meetings");
  return data;
}

export async function createMeeting(form: FormData): Promise<Meeting> {
  const { data } = await api.post("/meetings", form);
  return data;
}

export async function getMeeting(id: string): Promise<Meeting> {
  const { data } = await api.get(`/meetings/${id}`);
  return data;
}

export async function deleteMeeting(id: string): Promise<void> {
  await api.delete(`/meetings/${id}`);
}

export async function startProcessing(id: string): Promise<Job> {
  const { data } = await api.post(`/meetings/${id}/process`);
  return data;
}

export async function getJobs(meetingId: string): Promise<Job[]> {
  const { data } = await api.get(`/meetings/${meetingId}/jobs`);
  return data;
}

export async function updateSegmentText(
  id: string,
  text: string
): Promise<Segment> {
  const { data } = await api.put(`/segments/${id}`, { text });
  return data;
}

export async function updateSegmentSpeaker(
  id: string,
  speakerId: string
): Promise<Segment> {
  const { data } = await api.put(`/segments/${id}/speaker`, {
    speaker_id: speakerId,
  });
  return data;
}

export async function updateSpeaker(
  id: string,
  updates: { display_name?: string; color?: string }
): Promise<Speaker> {
  const { data } = await api.put(`/speakers/${id}`, updates);
  return data;
}

export async function mergeSpeakers(
  sourceId: string,
  targetId: string
): Promise<Speaker> {
  const { data } = await api.post("/speakers/merge", {
    source_id: sourceId,
    target_id: targetId,
  });
  return data;
}

export function getAudioUrl(meetingId: string): string {
  return `/api/meetings/${meetingId}/audio`;
}

export function getExportUrl(meetingId: string, format: string): string {
  return `/api/meetings/${meetingId}/export?format=${format}`;
}

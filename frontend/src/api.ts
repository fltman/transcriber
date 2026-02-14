import axios from "axios";
import type { Meeting, Segment, Speaker, Job, Action, ActionResult, ModelSettings } from "./types";

const api = axios.create({ baseURL: "/api" });

export async function listMeetings(): Promise<Meeting[]> {
  const { data } = await api.get("/meetings");
  return data;
}

export async function createMeeting(form: FormData): Promise<Meeting> {
  const { data } = await api.post("/meetings", form);
  return data;
}

export async function createLiveMeeting(title: string): Promise<Meeting> {
  const { data } = await api.post("/meetings/live", { title });
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

// --- Actions ---

export async function listActions(): Promise<Action[]> {
  const { data } = await api.get("/actions");
  return data;
}

export async function createAction(name: string, prompt: string): Promise<Action> {
  const { data } = await api.post("/actions", { name, prompt });
  return data;
}

export async function updateAction(id: string, updates: { name?: string; prompt?: string }): Promise<Action> {
  const { data } = await api.put(`/actions/${id}`, updates);
  return data;
}

export async function deleteAction(id: string): Promise<void> {
  await api.delete(`/actions/${id}`);
}

export async function runAction(actionId: string, meetingId: string): Promise<ActionResult> {
  const { data } = await api.post(`/actions/${actionId}/run/${meetingId}`);
  return data;
}

export async function listActionResults(meetingId: string): Promise<ActionResult[]> {
  const { data } = await api.get(`/actions/results/${meetingId}`);
  return data;
}

export async function deleteActionResult(id: string): Promise<void> {
  await api.delete(`/actions/results/${id}`);
}

// --- Model Settings ---

export async function getModelSettings(): Promise<ModelSettings> {
  const { data } = await api.get("/model-settings");
  return data;
}

export async function updateModelSettings(assignments: Record<string, string>): Promise<ModelSettings> {
  const { data } = await api.put("/model-settings", { assignments });
  return data;
}

// --- Encryption ---

export async function encryptMeeting(
  meetingId: string,
  password: string,
  includeVersions: boolean
): Promise<Meeting> {
  const { data } = await api.post(`/meetings/${meetingId}/encrypt`, {
    password,
    include_versions: includeVersions,
  });
  return data;
}

export async function decryptMeeting(
  meetingId: string,
  password: string
): Promise<Meeting> {
  const { data } = await api.post(`/meetings/${meetingId}/decrypt`, {
    password,
  });
  return data;
}

// --- Action Result Export ---

export function getActionResultExportUrl(resultId: string, format: string): string {
  return `/api/actions/results/${resultId}/export?format=${format}`;
}

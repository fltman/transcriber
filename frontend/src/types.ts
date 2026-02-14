export interface Meeting {
  id: string;
  title: string;
  status: "uploading" | "uploaded" | "processing" | "recording" | "finalizing" | "completed" | "failed";
  original_filename: string | null;
  duration: number | null;
  whisper_model: string;
  min_speakers: number | null;
  max_speakers: number | null;
  mode: "upload" | "live";
  recording_status: "recording" | "stopped" | "finalizing" | "complete" | null;
  created_at: string;
  updated_at: string;
  is_encrypted: boolean;
  speaker_count: number;
  segment_count: number;
  speakers?: Speaker[];
  segments?: Segment[];
}

export interface Speaker {
  id: string;
  meeting_id: string;
  label: string;
  display_name: string | null;
  color: string;
  identified_by: string | null;
  confidence: number | null;
  total_speaking_time: number;
  segment_count: number;
}

export interface Segment {
  id: string;
  meeting_id: string;
  speaker_id: string | null;
  speaker_label: string | null;
  speaker_name: string | null;
  speaker_color: string | null;
  start_time: number;
  end_time: number;
  text: string;
  original_text: string | null;
  order: number;
  is_edited: boolean;
}

export interface Job {
  id: string;
  meeting_id: string;
  job_type: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  current_step: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

export interface ProgressUpdate {
  type: "progress" | "error" | "ping" | "live_segment" | "polish_started" | "polish_complete" | "finalize_started" | "finalize_complete" | "speaker_reassignment" | "action_running" | "action_completed" | "action_failed";
  progress?: number;
  step?: string;
  status?: string;
  error?: string;
  message?: string;
  segment?: Segment;
  segments?: Segment[];
  speakers?: Speaker[];
  pass_number?: number;
  action_result_id?: string;
  action_id?: string;
  action_name?: string;
}

export interface Action {
  id: string;
  name: string;
  prompt: string;
  is_default: boolean;
  created_at: string;
}

export interface ActionResult {
  id: string;
  action_id: string;
  meeting_id: string;
  action_name: string;
  status: "pending" | "running" | "completed" | "failed";
  result_text: string | null;
  error: string | null;
  celery_task_id: string | null;
  is_encrypted: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface ModelPreset {
  id: string;
  name: string;
  type: "llm" | "whisper";
  provider: string;
  model?: string;
  model_path?: string;
}

export interface ModelSettings {
  presets: ModelPreset[];
  assignments: Record<string, string>;
}

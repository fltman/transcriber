export interface Meeting {
  id: string;
  title: string;
  status: "uploading" | "uploaded" | "processing" | "completed" | "failed";
  original_filename: string | null;
  duration: number | null;
  whisper_model: string;
  min_speakers: number | null;
  max_speakers: number | null;
  created_at: string;
  updated_at: string;
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
  type: "progress" | "error" | "ping";
  progress?: number;
  step?: string;
  status?: string;
  error?: string;
}

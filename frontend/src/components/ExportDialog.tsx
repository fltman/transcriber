import { getExportUrl } from "../api";

interface Props {
  meetingId: string;
  onClose: () => void;
}

const FORMATS = [
  { id: "md", label: "Markdown", desc: "Formatted text with speaker headers", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { id: "docx", label: "Word", desc: "Microsoft Word document", icon: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" },
  { id: "pdf", label: "PDF", desc: "Portable document format", icon: "M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" },
  { id: "txt", label: "Text", desc: "Plain text grouped by speaker", icon: "M4 6h16M4 12h16M4 18h7" },
  { id: "srt", label: "SRT", desc: "Subtitle format with timestamps", icon: "M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" },
  { id: "vtt", label: "WebVTT", desc: "Web video subtitles", icon: "M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" },
  { id: "json", label: "JSON", desc: "Structured data for further processing", icon: "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" },
];

export default function ExportDialog({ meetingId, onClose }: Props) {
  function handleExport(format: string) {
    window.open(getExportUrl(meetingId, format), "_blank");
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-white mb-5">Export transcription</h2>

        <div className="space-y-2">
          {FORMATS.map((f) => (
            <button
              key={f.id}
              onClick={() => handleExport(f.id)}
              className="w-full text-left p-4 rounded-xl border border-slate-800/50 hover:bg-slate-800/50 hover:border-slate-700/50 transition-all group flex items-center gap-4"
            >
              <div className="w-10 h-10 rounded-lg bg-slate-800 group-hover:bg-violet-500/20 flex items-center justify-center transition">
                <svg className="w-5 h-5 text-slate-400 group-hover:text-violet-400 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={f.icon} />
                </svg>
              </div>
              <div>
                <span className="font-semibold text-white text-sm">{f.label}</span>
                <p className="text-xs text-slate-500 mt-0.5">{f.desc}</p>
              </div>
            </button>
          ))}
        </div>

        <button
          onClick={onClose}
          className="w-full mt-5 py-2.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition"
        >
          Close
        </button>
      </div>
    </div>
  );
}

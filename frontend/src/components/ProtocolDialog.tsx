import { useState } from "react";
import Markdown from "react-markdown";
import { generateProtocol, exportProtocolDocx } from "../api";

interface Props {
  meetingId: string;
  meetingTitle: string;
  onClose: () => void;
}

export default function ProtocolDialog({ meetingId, meetingTitle, onClose }: Props) {
  const [protocolText, setProtocolText] = useState("");
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  async function handleGenerate() {
    setGenerating(true);
    setError("");
    try {
      const result = await generateProtocol(meetingId);
      setProtocolText(result.protocol_text);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Kunde inte generera protokoll");
    }
    setGenerating(false);
  }

  async function handleExportDocx() {
    setExporting(true);
    try {
      const blob = await exportProtocolDocx(meetingId, protocolText);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Protokoll - ${meetingTitle}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError("Kunde inte exportera DOCX");
    }
    setExporting(false);
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl p-6 w-full max-w-3xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white">Protokoll</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {!protocolText && !generating && (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center">
              <svg className="w-8 h-8 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-slate-300 mb-2">Generera motesprotokoll</h3>
            <p className="text-sm text-slate-500 mb-6 max-w-sm mx-auto">
              AI analyserar transkriberingen och skapar ett formellt protokoll med narvarande, dagordning, beslutspunkter och paragrafnumrering.
            </p>
            <button
              onClick={handleGenerate}
              className="px-6 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-medium hover:from-violet-500 hover:to-indigo-500 transition-all shadow-lg shadow-violet-500/25"
            >
              Generera protokoll
            </button>
          </div>
        )}

        {generating && (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-10 h-10 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mb-4" />
            <p className="text-slate-400 text-sm">Genererar protokoll med AI...</p>
            <p className="text-slate-600 text-xs mt-1">Detta kan ta upp till en minut</p>
          </div>
        )}

        {protocolText && (
          <>
            {/* Preview / Edit toggle */}
            <div className="flex bg-slate-800 rounded-lg p-0.5 mb-3 self-start">
              <button
                onClick={() => setEditing(false)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                  !editing ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
                }`}
              >
                Forhandsgranska
              </button>
              <button
                onClick={() => setEditing(true)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                  editing ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
                }`}
              >
                Redigera
              </button>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-800/30 rounded-xl p-4 mb-4 border border-slate-700/30">
              {editing ? (
                <textarea
                  value={protocolText}
                  onChange={(e) => setProtocolText(e.target.value)}
                  className="w-full h-full min-h-[400px] bg-transparent text-sm text-slate-300 font-mono resize-none focus:outline-none"
                />
              ) : (
                <div className="prose prose-invert prose-sm max-w-none prose-headings:text-slate-200 prose-p:text-slate-300 prose-strong:text-slate-200 prose-li:text-slate-300 prose-hr:border-slate-700">
                  <Markdown>{protocolText}</Markdown>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between">
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="text-sm text-slate-500 hover:text-white transition"
              >
                Generera om
              </button>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(protocolText);
                  }}
                  className="px-4 py-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition text-sm"
                >
                  Kopiera
                </button>
                <button
                  onClick={handleExportDocx}
                  disabled={exporting}
                  className="px-5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl font-medium hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 transition-all text-sm flex items-center gap-2"
                >
                  {exporting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Exporterar...
                    </>
                  ) : (
                    "Ladda ner DOCX"
                  )}
                </button>
              </div>
            </div>
          </>
        )}

        {error && (
          <p className="text-red-400 text-sm mt-2">{error}</p>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { Action, ActionResult } from "../types";
import {
  listActions,
  createAction,
  updateAction,
  deleteAction,
  runAction,
  listActionResults,
  deleteActionResult,
  getActionResultExportUrl,
} from "../api";

interface Props {
  meetingId: string;
  onResultEvent?: { action_result_id?: string; type: string } | null;
}

export default function ActionsPanel({ meetingId, onResultEvent }: Props) {
  const [actions, setActions] = useState<Action[]>([]);
  const [results, setResults] = useState<ActionResult[]>([]);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);
  const [runningActions, setRunningActions] = useState<Set<string>>(new Set());
  const [showManage, setShowManage] = useState(false);
  const [editingAction, setEditingAction] = useState<Action | null>(null);
  const [newName, setNewName] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadActions();
    loadResults();
  }, [meetingId]);

  // React to WS events
  useEffect(() => {
    if (!onResultEvent) return;
    if (
      onResultEvent.type === "action_completed" ||
      onResultEvent.type === "action_failed"
    ) {
      loadResults();
      setRunningActions((prev) => {
        const next = new Set(prev);
        next.delete(onResultEvent.action_result_id || "");
        return next;
      });
    }
    if (onResultEvent.type === "action_running" && onResultEvent.action_result_id) {
      setRunningActions((prev) => new Set(prev).add(onResultEvent.action_result_id!));
    }
  }, [onResultEvent]);

  async function loadActions() {
    const data = await listActions();
    setActions(data);
  }

  async function loadResults() {
    const data = await listActionResults(meetingId);
    setResults(data);
  }

  async function handleRun(actionId: string) {
    const result = await runAction(actionId, meetingId);
    setRunningActions((prev) => new Set(prev).add(result.id));
    setResults((prev) => [
      { ...result, action_name: actions.find((a) => a.id === actionId)?.name || "Action" },
      ...prev,
    ]);
  }

  async function handleDeleteResult(id: string) {
    await deleteActionResult(id);
    setResults((prev) => prev.filter((r) => r.id !== id));
    if (expandedResult === id) setExpandedResult(null);
  }

  async function handleCreate() {
    if (!newName.trim() || !newPrompt.trim()) return;
    await createAction(newName.trim(), newPrompt.trim());
    setNewName("");
    setNewPrompt("");
    setCreating(false);
    loadActions();
  }

  async function handleUpdate(id: string) {
    if (!editingAction) return;
    await updateAction(id, { name: editingAction.name, prompt: editingAction.prompt });
    setEditingAction(null);
    loadActions();
  }

  async function handleDelete(id: string) {
    await deleteAction(id);
    loadActions();
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text);
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case "pending":
      case "running":
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
            <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
            {status === "pending" ? "Pending" : "Running"}
          </span>
        );
      case "completed":
        return (
          <span className="text-[10px] font-medium text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
            Done
          </span>
        );
      case "failed":
        return (
          <span className="text-[10px] font-medium text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
            Failed
          </span>
        );
    }
  };

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/50 p-5 backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-white text-sm">Actions</h3>
        <button
          onClick={() => setShowManage(!showManage)}
          className={`text-xs px-2.5 py-1 rounded-lg transition ${
            showManage
              ? "bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/30"
              : "text-slate-500 hover:text-white hover:bg-slate-800"
          }`}
        >
          {showManage ? "Close" : "Manage"}
        </button>
      </div>

      {/* Action buttons */}
      {!showManage && (
        <>
          <div className="space-y-1.5 mb-4">
            {actions.map((a) => (
              <button
                key={a.id}
                onClick={() => handleRun(a.id)}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600/50 transition text-sm text-slate-300 hover:text-white flex items-center justify-between group"
              >
                <span className="truncate">{a.name}</span>
                <svg
                  className="w-3.5 h-3.5 text-slate-600 group-hover:text-violet-400 transition flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                </svg>
              </button>
            ))}
          </div>

          {/* Results */}
          {results.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Results</h4>
              <div className="space-y-1.5">
                {results.map((r) => {
                  const isExpanded = expandedResult === r.id;
                  const isLoading = r.status === "pending" || r.status === "running" || runningActions.has(r.id);
                  return (
                    <div key={r.id} className="rounded-lg bg-slate-800/30 border border-slate-700/30 overflow-hidden">
                      <div
                        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-slate-800/50 transition"
                        onClick={() => !isLoading && setExpandedResult(isExpanded ? null : r.id)}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {isLoading ? (
                            <div className="w-3.5 h-3.5 border border-violet-500/30 border-t-violet-500 rounded-full animate-spin flex-shrink-0" />
                          ) : (
                            <svg
                              className={`w-3 h-3 text-slate-500 transition flex-shrink-0 ${isExpanded ? "rotate-90" : ""}`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          )}
                          <span className="text-sm text-slate-300 truncate">{r.action_name}</span>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {statusBadge(isLoading ? "running" : r.status)}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteResult(r.id);
                            }}
                            className="text-slate-600 hover:text-red-400 transition p-0.5"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      </div>
                      {isExpanded && r.status === "completed" && r.result_text && (
                        <div className="px-3 pb-3 border-t border-slate-700/30">
                          <div className="flex justify-end gap-3 mt-2 mb-1">
                            <div className="relative group/dl">
                              <button className="text-[10px] text-slate-500 hover:text-violet-400 transition flex items-center gap-1 pb-1">
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                                </svg>
                                Download
                              </button>
                              <div className="absolute right-0 top-full bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 hidden group-hover/dl:block z-10 min-w-[100px]">
                                {["md", "docx", "pdf", "txt"].map((fmt) => (
                                  <a
                                    key={fmt}
                                    href={getActionResultExportUrl(r.id, fmt)}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="block px-3 py-1.5 text-[11px] text-slate-300 hover:bg-slate-700 hover:text-white transition"
                                  >
                                    {fmt.toUpperCase()}
                                  </a>
                                ))}
                              </div>
                            </div>
                            <button
                              onClick={() => copyToClipboard(r.result_text!)}
                              className="text-[10px] text-slate-500 hover:text-violet-400 transition flex items-center gap-1"
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                              Copy
                            </button>
                          </div>
                          <div className="max-h-80 overflow-y-auto text-xs leading-relaxed prose-sm-dark">
                            <ReactMarkdown
                              components={{
                                h1: ({ children }) => <h1 className="text-sm font-bold text-slate-200 mt-3 mb-1.5">{children}</h1>,
                                h2: ({ children }) => <h2 className="text-sm font-bold text-slate-200 mt-3 mb-1.5">{children}</h2>,
                                h3: ({ children }) => <h3 className="text-xs font-semibold text-slate-300 mt-2 mb-1">{children}</h3>,
                                p: ({ children }) => <p className="text-slate-400 mb-2">{children}</p>,
                                strong: ({ children }) => <strong className="text-slate-200 font-semibold">{children}</strong>,
                                em: ({ children }) => <em className="text-slate-300 italic">{children}</em>,
                                ul: ({ children }) => <ul className="list-disc list-inside text-slate-400 mb-2 space-y-0.5">{children}</ul>,
                                ol: ({ children }) => <ol className="list-decimal list-inside text-slate-400 mb-2 space-y-0.5">{children}</ol>,
                                li: ({ children }) => <li className="text-slate-400">{children}</li>,
                                hr: () => <hr className="border-slate-700/50 my-2" />,
                                blockquote: ({ children }) => <blockquote className="border-l-2 border-violet-500/30 pl-2 my-2 text-slate-500 italic">{children}</blockquote>,
                                code: ({ children }) => <code className="bg-slate-800 text-violet-300 px-1 py-0.5 rounded text-[11px]">{children}</code>,
                              }}
                            >
                              {r.result_text}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                      {isExpanded && r.status === "failed" && r.error && (
                        <div className="px-3 pb-3 border-t border-slate-700/30">
                          <p className="text-xs text-red-400/70 mt-2">{r.error}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Manage actions */}
      {showManage && (
        <div className="space-y-2">
          {actions.map((a) => (
            <div key={a.id} className="rounded-lg bg-slate-800/30 border border-slate-700/30 p-3">
              {editingAction?.id === a.id ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={editingAction.name}
                    onChange={(e) => setEditingAction({ ...editingAction, name: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-600 rounded-lg px-2.5 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                  />
                  <textarea
                    value={editingAction.prompt}
                    onChange={(e) => setEditingAction({ ...editingAction, prompt: e.target.value })}
                    rows={4}
                    className="w-full bg-slate-800 border border-slate-600 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-violet-500/50 resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleUpdate(a.id)}
                      className="text-xs px-3 py-1 bg-violet-600 text-white rounded-lg hover:bg-violet-500 transition"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingAction(null)}
                      className="text-xs px-3 py-1 text-slate-400 hover:text-white transition"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-200 font-medium truncate">{a.name}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5 truncate">{a.prompt.slice(0, 80)}...</p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0 ml-2">
                    <button
                      onClick={() => setEditingAction({ ...a })}
                      className="p-1.5 text-slate-500 hover:text-white hover:bg-slate-700/50 rounded-lg transition"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => handleDelete(a.id)}
                      className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Create new action */}
          {creating ? (
            <div className="rounded-lg bg-slate-800/30 border border-violet-500/30 p-3 space-y-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Action name"
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-2.5 py-1.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              />
              <textarea
                value={newPrompt}
                onChange={(e) => setNewPrompt(e.target.value)}
                placeholder="Prompt template..."
                rows={4}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-violet-500/50 resize-none"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleCreate}
                  className="text-xs px-3 py-1 bg-violet-600 text-white rounded-lg hover:bg-violet-500 transition"
                >
                  Create
                </button>
                <button
                  onClick={() => { setCreating(false); setNewName(""); setNewPrompt(""); }}
                  className="text-xs px-3 py-1 text-slate-400 hover:text-white transition"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setCreating(true)}
              className="w-full text-left px-3 py-2 rounded-lg border border-dashed border-slate-700/50 hover:border-violet-500/30 text-xs text-slate-500 hover:text-violet-400 transition"
            >
              + New action
            </button>
          )}
        </div>
      )}
    </div>
  );
}

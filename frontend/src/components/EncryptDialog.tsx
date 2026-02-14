import { useState } from "react";
import { encryptMeeting } from "../api";

interface Props {
  meetingId: string;
  onClose: () => void;
  onEncrypted: () => void;
}

export default function EncryptDialog({ meetingId, onClose, onEncrypted }: Props) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [includeVersions, setIncludeVersions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const passwordsMatch = password === confirmPassword;
  const canSubmit = password.length >= 4 && passwordsMatch && !loading;

  async function handleEncrypt() {
    if (!canSubmit) return;
    setLoading(true);
    setError("");
    try {
      await encryptMeeting(meetingId, password, includeVersions);
      onEncrypted();
      onClose();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Encryption failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Encrypt meeting</h2>
            <p className="text-sm text-slate-500">Protect this transcript with a password</p>
          </div>
        </div>

        <div className="space-y-3 mb-4">
          <input
            type="password"
            placeholder="Password (min 4 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50"
            autoFocus
          />
          <input
            type="password"
            placeholder="Confirm password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className={`w-full bg-slate-800 border rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 ${
              confirmPassword && !passwordsMatch
                ? "border-red-500/50 focus:ring-red-500/50"
                : "border-slate-700/50 focus:ring-amber-500/50 focus:border-amber-500/50"
            }`}
          />
          {confirmPassword && !passwordsMatch && (
            <p className="text-red-400 text-sm">Passwords do not match</p>
          )}
        </div>

        <label className="flex items-center gap-3 mb-5 cursor-pointer group">
          <input
            type="checkbox"
            checked={includeVersions}
            onChange={(e) => setIncludeVersions(e.target.checked)}
            className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-amber-500 focus:ring-amber-500/50"
          />
          <span className="text-sm text-slate-400 group-hover:text-slate-300 transition">
            Also encrypt action results (versions)
          </span>
        </label>

        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5 mb-4">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-5 py-2.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition"
          >
            Cancel
          </button>
          <button
            onClick={handleEncrypt}
            disabled={!canSubmit}
            className="px-5 py-2.5 bg-gradient-to-r from-amber-600 to-orange-600 text-white rounded-xl font-medium hover:from-amber-500 hover:to-orange-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-amber-500/25"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Encrypting...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                Encrypt
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

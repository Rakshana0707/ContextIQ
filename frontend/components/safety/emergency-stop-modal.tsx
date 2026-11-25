"use client";

import React, { useState } from "react";
import { AlertOctagon, ShieldAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmergencyStopModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string, scope: "USER_LEVEL" | "ADMIN_GLOBAL") => Promise<void>;
}

export const EmergencyStopModal: React.FC<EmergencyStopModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
}) => {
  const [reason, setReason] = useState("");
  const [scope, setScope] = useState<"USER_LEVEL" | "ADMIN_GLOBAL">("USER_LEVEL");
  const [confirmText, setConfirmText] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const isConfirmed = confirmText.trim().toUpperCase() === "STOP";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isConfirmed || !reason.trim()) return;

    setLoading(true);
    try {
      await onConfirm(reason.trim(), scope);
      onClose();
      setReason("");
      setConfirmText("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-lg rounded-2xl border border-red-800/80 bg-slate-950 p-6 shadow-2xl space-y-5 text-slate-100">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-950/80 border border-red-700/80 rounded-xl text-red-400">
              <AlertOctagon className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-red-100">Engage Emergency Stop</h2>
              <p className="text-xs text-red-400">
                Operational kill switch for autonomous workflow executions
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 rounded-xl bg-red-950/40 border border-red-900/60 text-xs text-red-300 space-y-2">
          <p className="font-semibold text-red-200 flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4 text-red-400" /> Immediate Consequences:
          </p>
          <ul className="list-disc list-inside space-y-1 text-slate-300">
            <li>Cancels all in-flight and scheduled workflow executions.</li>
            <li>Disables automated trigger rules to halt repeated dispatch.</li>
            <li>Rejects all background retries and marks steps as blocked.</li>
            <li>Preserves full immutable audit history for post-incident review.</li>
          </ul>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Stop Scope
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setScope("USER_LEVEL")}
                className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-colors ${
                  scope === "USER_LEVEL"
                    ? "bg-red-950/80 border-red-600 text-red-200 font-bold"
                    : "bg-slate-900 border-slate-800 text-slate-400"
                }`}
              >
                User Level (My Automations)
              </button>
              <button
                type="button"
                onClick={() => setScope("ADMIN_GLOBAL")}
                className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-colors ${
                  scope === "ADMIN_GLOBAL"
                    ? "bg-red-950/80 border-red-600 text-red-200 font-bold"
                    : "bg-slate-900 border-slate-800 text-slate-400"
                }`}
              >
                Global Kill Switch (All Users)
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Incident Reason / Explanation <span className="text-red-400">*</span>
            </label>
            <textarea
              required
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Unintended calendar meeting cancellations detected..."
              className="w-full text-xs p-2.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-red-600 font-sans"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Type <strong className="text-red-400 font-mono">STOP</strong> to confirm:
            </label>
            <input
              type="text"
              required
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="STOP"
              className="w-full text-xs p-2.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-100 font-mono focus:outline-none focus:border-red-600"
            />
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={loading}
              className="text-xs border-slate-800 text-slate-300"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!isConfirmed || !reason.trim() || loading}
              className="bg-red-700 hover:bg-red-600 text-white font-bold text-xs px-4"
            >
              {loading ? "Engaging..." : "ENGAGE EMERGENCY STOP"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

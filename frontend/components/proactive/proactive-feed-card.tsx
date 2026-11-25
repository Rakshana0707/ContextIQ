"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Brain,
  Calendar,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Coffee,
  Info,
  Shield,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ProactiveFeedItem } from "@/types/proactive";

interface ProactiveFeedCardProps {
  item: ProactiveFeedItem;
  onApprove: (id: string) => void;
  onSnooze: (id: string, minutes: number) => void;
  onDismiss: (id: string) => void;
}

export const ProactiveFeedCard: React.FC<ProactiveFeedCardProps> = ({
  item,
  onApprove,
  onSnooze,
  onDismiss,
}) => {
  const [showEvidence, setShowEvidence] = useState(false);
  const [snoozeMenuOpen, setSnoozeMenuOpen] = useState(false);

  // Detection icon mapping
  const getIcon = () => {
    switch (item.detection_type) {
      case "THRASHING_DETECTED":
        return <Zap className="w-5 h-5 text-amber-400" />;
      case "FORGETTING_RISK_SPIKE":
        return <Brain className="w-5 h-5 text-indigo-400" />;
      case "CALENDAR_OVERLOAD":
        return <Calendar className="w-5 h-5 text-rose-400" />;
      case "RECOVERY_LAG_EXCEEDED":
      case "BFI_SPIKE":
        return <Coffee className="w-5 h-5 text-emerald-400" />;
      default:
        return <Sparkles className="w-5 h-5 text-cyan-400" />;
    }
  };

  const getStatusBadge = () => {
    switch (item.status) {
      case "ACTIONED":
        return <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 bg-emerald-500/10">Actioned</Badge>;
      case "SNOOZED":
        return <Badge variant="outline" className="text-amber-400 border-amber-500/30 bg-amber-500/10">Snoozed</Badge>;
      case "DISMISSED":
        return <Badge variant="outline" className="text-zinc-500 border-zinc-700 bg-zinc-800">Dismissed</Badge>;
      default:
        return <Badge variant="outline" className="text-cyan-400 border-cyan-500/30 bg-cyan-500/10">Active</Badge>;
    }
  };

  return (
    <div className={cn(
      "border rounded-xl p-5 transition-all shadow-sm",
      item.status === "ACTIVE"
        ? "bg-zinc-900/90 border-zinc-700/80 hover:border-zinc-600"
        : "bg-zinc-900/40 border-zinc-800/60 opacity-70"
    )}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2.5 rounded-lg bg-zinc-800/80 border border-zinc-700/60 mt-0.5">
            {getIcon()}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-zinc-100 text-base">{item.title}</h3>
              {getStatusBadge()}
              <span className="text-xs text-zinc-400">
                {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5 font-mono">
              Detection: {item.detection_type}
            </p>
          </div>
        </div>

        {/* Confidence & Conformal Interval Badge */}
        <div className="text-right shrink-0">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800/80 border border-zinc-700/60 text-xs">
            <Shield className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-zinc-300 font-medium">
              {Math.round(item.confidence_score * 100)}% Conf.
            </span>
          </div>
          <p className="text-[10px] text-zinc-400 mt-1">
            {item.conformal_interval_text}
          </p>
        </div>
      </div>

      {/* Why it Matters (Explanation) */}
      <div className="mt-4 p-3 rounded-lg bg-zinc-950/60 border border-zinc-800/80 text-sm">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300 mb-1">
          <Info className="w-3.5 h-3.5 text-cyan-400" />
          Why This Matters
        </div>
        <p className="text-zinc-300 leading-relaxed text-xs">
          {item.why_it_matters}
        </p>
      </div>

      {/* Recommended Response */}
      <div className="mt-3 flex items-start gap-2 text-xs text-zinc-300">
        <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-zinc-200">Recommendation: </span>
          {item.recommended_response}
        </div>
      </div>

      {/* Conformal Uncertainty Disclaimer Note */}
      <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-zinc-400">
        <AlertTriangle className="w-3 h-3 text-zinc-400 shrink-0" />
        <span>Statistical estimate with empirical coverage guarantees (predictions reflect likelihood, not certainty).</span>
      </div>

      {/* Collapsible Evidence Section */}
      <div className="mt-3 border-t border-zinc-800/80 pt-2">
        <button
          onClick={() => setShowEvidence(!showEvidence)}
          className="flex items-center justify-between w-full text-xs text-zinc-400 hover:text-zinc-200 py-1 transition-colors"
        >
          <span>Contextual Evidence & Telemetry Signals</span>
          {showEvidence ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {showEvidence && (
          <div className="mt-2 p-2.5 rounded bg-zinc-950 font-mono text-[11px] text-zinc-400 overflow-x-auto border border-zinc-800">
            <pre>{JSON.stringify(item.evidence, null, 2)}</pre>
          </div>
        )}
      </div>

      {/* Actions Gating / Resolution Controls */}
      {item.status === "ACTIVE" && (
        <div className="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between gap-2 flex-wrap">
          <div className="text-xs text-zinc-400">
            {item.requires_approval ? "Requires explicit confirmation to execute" : "Pre-approved workflow"}
          </div>

          <div className="flex items-center gap-2">
            {/* Snooze Dropdown */}
            <div className="relative">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSnoozeMenuOpen(!snoozeMenuOpen)}
                className="h-8 text-xs border-zinc-700 bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300"
              >
                <Clock className="w-3.5 h-3.5 mr-1 text-zinc-400" />
                Snooze
              </Button>
              {snoozeMenuOpen && (
                <div className="absolute right-0 bottom-full mb-1 w-32 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl z-20 py-1 text-xs">
                  <button
                    onClick={() => { onSnooze(item.id, 30); setSnoozeMenuOpen(false); }}
                    className="w-full text-left px-3 py-1.5 hover:bg-zinc-800 text-zinc-300"
                  >
                    30 minutes
                  </button>
                  <button
                    onClick={() => { onSnooze(item.id, 60); setSnoozeMenuOpen(false); }}
                    className="w-full text-left px-3 py-1.5 hover:bg-zinc-800 text-zinc-300"
                  >
                    1 hour
                  </button>
                  <button
                    onClick={() => { onSnooze(item.id, 240); setSnoozeMenuOpen(false); }}
                    className="w-full text-left px-3 py-1.5 hover:bg-zinc-800 text-zinc-300"
                  >
                    4 hours
                  </button>
                </div>
              )}
            </div>

            {/* Dismiss */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDismiss(item.id)}
              className="h-8 text-xs border-zinc-700 bg-zinc-800/60 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
            >
              <X className="w-3.5 h-3.5 mr-1" />
              Dismiss
            </Button>

            {/* Approve / Execute Action */}
            <Button
              size="sm"
              onClick={() => onApprove(item.id)}
              className="h-8 text-xs bg-cyan-600 hover:bg-cyan-500 text-white font-medium"
            >
              <Check className="w-3.5 h-3.5 mr-1" />
              {item.suggested_action?.label || "Approve & Execute"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

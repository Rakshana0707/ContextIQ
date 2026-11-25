"use client";

import React, { useState } from "react";
import { ProactiveFeedCard } from "./proactive-feed-card";
import type { ProactiveFeedItem } from "@/types/proactive";
import {
  Sparkles,
  RefreshCw,
  Zap,
  Brain,
  Coffee,
  Calendar,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface ProactiveFeedListProps {
  items: ProactiveFeedItem[];
  loading: boolean;
  onRefresh: () => void;
  onApprove: (id: string) => void;
  onSnooze: (id: string, minutes: number) => void;
  onDismiss: (id: string) => void;
  onSimulate: (detectionType: string) => void;
}

export const ProactiveFeedList: React.FC<ProactiveFeedListProps> = ({
  items,
  loading,
  onRefresh,
  onApprove,
  onSnooze,
  onDismiss,
  onSimulate,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const filteredItems = items.filter((item) => {
    if (statusFilter === "ALL") return true;
    return item.status === statusFilter;
  });

  return (
    <div className="space-y-6">
      {/* Top Banner & Simulation Controls */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-cyan-950/40 via-zinc-900 to-zinc-900 border border-cyan-800/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <h3 className="font-semibold text-zinc-100 text-sm">
              Event-Driven Behavioral Intelligence
            </h3>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Proactive suggestions triggered by desktop telemetry, forgetting risks, and context switches. Protected by cognitive fatigue limits (max 3/day).
          </p>
        </div>

        {/* Live Simulator Triggers */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[11px] text-zinc-400 mr-1">Simulate Detection:</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSimulate("THRASHING")}
            className="h-7 text-[11px] px-2.5 bg-zinc-900/80 border-zinc-700 hover:border-amber-500/50 hover:bg-zinc-800 text-amber-300"
          >
            <Zap className="w-3 h-3 mr-1" />
            Thrashing
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSimulate("FORGETTING_RISK")}
            className="h-7 text-[11px] px-2.5 bg-zinc-900/80 border-zinc-700 hover:border-indigo-500/50 hover:bg-zinc-800 text-indigo-300"
          >
            <Brain className="w-3 h-3 mr-1" />
            Forgetting
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSimulate("CALENDAR_OVERLOAD")}
            className="h-7 text-[11px] px-2.5 bg-zinc-900/80 border-zinc-700 hover:border-rose-500/50 hover:bg-zinc-800 text-rose-300"
          >
            <Calendar className="w-3 h-3 mr-1" />
            Calendar
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSimulate("RECOVERY_LAG")}
            className="h-7 text-[11px] px-2.5 bg-zinc-900/80 border-zinc-700 hover:border-emerald-500/50 hover:bg-zinc-800 text-emerald-300"
          >
            <Coffee className="w-3 h-3 mr-1" />
            Recovery
          </Button>
        </div>
      </div>

      {/* Filter and Refresh Bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-zinc-400" />
          <span className="text-xs text-zinc-400 font-medium">Status Filter:</span>
          {(["ALL", "ACTIVE", "ACTIONED", "SNOOZED", "DISMISSED"] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setStatusFilter(filter)}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                statusFilter === filter
                  ? "bg-zinc-800 text-cyan-400 border border-zinc-700"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
              }`}
            >
              {filter}
            </button>
          ))}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={loading}
          className="h-8 text-xs border-zinc-700 bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh Feed
        </Button>
      </div>

      {/* Feed List Items */}
      {filteredItems.length === 0 ? (
        <div className="p-12 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
          <Sparkles className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <h4 className="text-sm font-semibold text-zinc-300">No Proactive Alerts</h4>
          <p className="text-xs text-zinc-500 mt-1 max-w-md mx-auto">
            {statusFilter === "ALL"
              ? "Your behavioral patterns are balanced. ContextIQ is continuously monitoring telemetry for meaningful changes."
              : `No items matching the '${statusFilter}' filter.`}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredItems.map((item) => (
            <ProactiveFeedCard
              key={item.id}
              item={item}
              onApprove={onApprove}
              onSnooze={onSnooze}
              onDismiss={onDismiss}
            />
          ))}
        </div>
      )}
    </div>
  );
};

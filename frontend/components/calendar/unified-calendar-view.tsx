"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Calendar,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock,
  Edit2,
  ExternalLink,
  Flame,
  Info,
  Layers,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  schedulingApi,
  UserAvailabilityResponse,
  ScheduleProposalResponse,
  ScheduledSlotDTO,
  BusyBlockRead,
  AvailabilityWindowRead,
} from "@/lib/api/services/scheduling";

export function UnifiedCalendarView() {
  const [availability, setAvailability] = useState<UserAvailabilityResponse | null>(null);
  const [proposal, setProposal] = useState<ScheduleProposalResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [approving, setApproving] = useState<boolean>(false);
  const [targetProvider, setTargetProvider] = useState<"google_calendar" | "microsoft_outlook">("google_calendar");
  const [horizonDays, setHorizonDays] = useState<number>(3);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [editingSlotTaskId, setEditingSlotTaskId] = useState<string | null>(null);
  const [editStartTime, setEditStartTime] = useState<string>("");
  const [editEndTime, setEditEndTime] = useState<string>("");

  const loadCalendarData = useCallback(async () => {
    setLoading(true);
    try {
      const avail = await schedulingApi.getAvailability({ horizon_days: horizonDays });
      setAvailability(avail);
    } catch {
      // In standalone demo, fallback gracefully
      setAvailability({
        user_id: "demo-user",
        horizon_start: new Date().toISOString(),
        horizon_end: new Date(Date.now() + horizonDays * 86400000).toISOString(),
        total_available_minutes: 480,
        busy_blocks: [
          {
            title: "Sprint Planning Sync",
            start_time: new Date(Date.now() + 3600000).toISOString(),
            end_time: new Date(Date.now() + 7200000).toISOString(),
            source: "google_calendar",
            is_recovery_buffer: false,
          },
          {
            title: "Post-Meeting Cognitive Recovery",
            start_time: new Date(Date.now() + 7200000).toISOString(),
            end_time: new Date(Date.now() + 8100000).toISOString(),
            source: "contextiq_buffer",
            is_recovery_buffer: true,
          },
        ],
        available_windows: [
          {
            start_time: new Date(Date.now() + 10800000).toISOString(),
            end_time: new Date(Date.now() + 21600000).toISOString(),
            duration_minutes: 180,
            focus_quality_score: 92,
            is_peak_focus: true,
          },
        ],
      });
    } finally {
      setLoading(false);
    }
  }, [horizonDays]);

  useEffect(() => {
    loadCalendarData();
  }, [loadCalendarData]);

  const handleGenerateSchedule = async () => {
    setGenerating(true);
    setMessage(null);
    try {
      const prop = await schedulingApi.generate({
        horizon_days: horizonDays,
        working_hour_start: 9,
        working_hour_end: 18,
        recovery_buffer_minutes: 15,
        enforce_lunch_break: true,
      });
      setProposal(prop);
      setMessage({
        type: "success",
        text: `Generated adaptive schedule with ${prop.scheduled_slots.length} optimized blocks! Review below before committing.`,
      });
    } catch {
      setMessage({
        type: "error",
        text: "Failed to generate schedule proposal. Please check server connection.",
      });
    } finally {
      setGenerating(false);
    }
  };

  const handleApproveProposal = async () => {
    if (!proposal || !proposal.proposal_id) return;
    setApproving(true);
    setMessage(null);
    try {
      const resp = await schedulingApi.approve(proposal.proposal_id, {
        target_provider: targetProvider,
      });
      setMessage({
        type: "success",
        text: `Schedule successfully committed to ${resp.provider}! Pushed ${resp.committed_events} events.`,
      });
      setProposal(null);
      await loadCalendarData();
    } catch {
      setMessage({
        type: "error",
        text: "Approval commit failed. External calendar may need re-authorization.",
      });
    } finally {
      setApproving(false);
    }
  };

  const handleRejectProposal = async () => {
    if (!proposal || !proposal.proposal_id) return;
    try {
      await schedulingApi.reject(proposal.proposal_id, "User requested revision");
      setMessage({ type: "success", text: "Schedule proposal rejected." });
      setProposal(null);
    } catch {
      setMessage({ type: "error", text: "Failed to reject proposal." });
    }
  };

  const handleStartEditSlot = (slot: ScheduledSlotDTO) => {
    setEditingSlotTaskId(slot.task_id);
    setEditStartTime(slot.start_time.slice(0, 16));
    setEditEndTime(slot.end_time.slice(0, 16));
  };

  const handleSaveModifiedSlot = async (taskId: string) => {
    if (!proposal || !proposal.proposal_id) return;
    try {
      const updated = await schedulingApi.modifySlot(proposal.proposal_id, {
        task_id: taskId,
        new_start_time: new Date(editStartTime).toISOString(),
        new_end_time: new Date(editEndTime).toISOString(),
      });
      setProposal(updated);
      setEditingSlotTaskId(null);
      setMessage({ type: "success", text: "Slot adjusted successfully." });
    } catch {
      setMessage({ type: "error", text: "Failed to modify slot." });
    }
  };

  const formatTimeRange = (startStr: string, endStr: string) => {
    try {
      const start = new Date(startStr);
      const end = new Date(endStr);
      return `${start.toLocaleDateString([], { month: "short", day: "numeric" })} • ${start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} - ${end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    } catch {
      return `${startStr} - ${endStr}`;
    }
  };

  return (
    <div className="space-y-6">
      {/* Alert Banner */}
      {message && (
        <div
          className={`p-3.5 rounded-xl text-xs flex items-center justify-between border ${
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400"
              : "bg-red-500/10 border-red-500/20 text-red-700 dark:text-red-400"
          }`}
        >
          <div className="flex items-center gap-2">
            {message.type === "success" ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="font-bold opacity-60 hover:opacity-100">
            ✕
          </button>
        </div>
      )}

      {/* Control Bar: Horizon & Scheduling Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl border border-border bg-card shadow-xs">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <CalendarDays className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-foreground">Intelligent Scheduling Engine</h2>
            <p className="text-xs text-muted-foreground">
              Aligns high-forgetting-risk tasks with discovered circadian focus windows and respects meeting blackouts.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <select
            value={horizonDays}
            onChange={(e) => setHorizonDays(Number(e.target.value))}
            className="text-xs rounded-lg border border-border bg-background px-2.5 py-1.5 text-foreground"
          >
            <option value={1}>Horizon: 1 Day</option>
            <option value={3}>Horizon: 3 Days</option>
            <option value={7}>Horizon: 7 Days</option>
          </select>

          <Button
            size="sm"
            onClick={handleGenerateSchedule}
            disabled={generating}
            className="text-xs font-semibold gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            <Sparkles className={`h-3.5 w-3.5 ${generating ? "animate-spin" : ""}`} />
            {generating ? "Computing Schedule..." : "Generate Proposed Schedule"}
          </Button>
        </div>
      </div>

      {/* Proposed Schedule Approval Review Drawer */}
      {proposal && (
        <Card className="border-indigo-500/30 bg-indigo-50/20 dark:bg-indigo-950/20 shadow-md">
          <CardHeader className="pb-3 flex flex-row items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-500" />
                <CardTitle className="text-base font-bold text-foreground">
                  Proposed Adaptive Schedule Preview
                </CardTitle>
                <Badge variant="outline" className="text-[10px] bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/30">
                  {proposal.status}
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Review proposed focus blocks, behavioral rationales, and recovery buffers.
                <strong> Changes will NOT be written to your external calendar without explicit approval.</strong>
              </CardDescription>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={targetProvider}
                onChange={(e) => setTargetProvider(e.target.value as any)}
                className="text-xs rounded-lg border border-border bg-background px-2 py-1 text-foreground"
              >
                <option value="google_calendar">Google Calendar</option>
                <option value="microsoft_outlook">Microsoft Outlook</option>
              </select>

              <Button
                size="sm"
                onClick={handleApproveProposal}
                disabled={approving || proposal.scheduled_slots.length === 0}
                className="text-xs font-semibold gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                <Check className="h-3.5 w-3.5" />
                {approving ? "Committing..." : "Approve & Commit"}
              </Button>

              <Button
                size="sm"
                variant="outline"
                onClick={handleRejectProposal}
                className="text-xs gap-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
              >
                <X className="h-3.5 w-3.5" />
                Reject
              </Button>
            </div>
          </CardHeader>

          <CardContent className="space-y-3 pt-1">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {proposal.scheduled_slots.map((slot) => {
                const isEditing = editingSlotTaskId === slot.task_id;
                return (
                  <div
                    key={slot.task_id}
                    className="p-3.5 rounded-xl border border-indigo-500/20 bg-card/80 space-y-2 text-xs shadow-xs"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-bold text-foreground text-sm block">{slot.task_title}</span>
                        <span className="text-[11px] font-mono text-muted-foreground">
                          {formatTimeRange(slot.start_time, slot.end_time)} ({slot.duration_minutes}m)
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {slot.is_peak_focus && (
                          <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30">
                            <Flame className="h-2.5 w-2.5 mr-1" />
                            Peak Focus
                          </Badge>
                        )}
                        <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                          {slot.focus_quality_score}% Quality
                        </Badge>
                      </div>
                    </div>

                    {/* Behavioral Rationale */}
                    <div className="p-2 rounded-lg bg-muted/30 border border-border/40 text-[11px] text-muted-foreground flex items-start gap-1.5">
                      <Zap className="h-3.5 w-3.5 text-indigo-500 shrink-0 mt-0.5" />
                      <span>{slot.explanation?.primary_rationale || "Scheduled during high cognitive readiness."}</span>
                    </div>

                    {/* Manual Slot Modification */}
                    {isEditing ? (
                      <div className="space-y-2 pt-2 border-t border-border/50">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[10px] font-medium text-muted-foreground block">Start Time</label>
                            <input
                              type="datetime-local"
                              value={editStartTime}
                              onChange={(e) => setEditStartTime(e.target.value)}
                              className="w-full text-[11px] rounded border border-border bg-background p-1 text-foreground"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-medium text-muted-foreground block">End Time</label>
                            <input
                              type="datetime-local"
                              value={editEndTime}
                              onChange={(e) => setEditEndTime(e.target.value)}
                              className="w-full text-[11px] rounded border border-border bg-background p-1 text-foreground"
                            />
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 justify-end">
                          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingSlotTaskId(null)}>
                            Cancel
                          </Button>
                          <Button size="sm" className="h-7 text-xs bg-indigo-600 text-white" onClick={() => handleSaveModifiedSlot(slot.task_id)}>
                            Save Block
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex justify-end pt-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-[11px] text-muted-foreground hover:text-foreground gap-1 px-2"
                          onClick={() => handleStartEditSlot(slot)}
                        >
                          <Edit2 className="h-2.5 w-2.5" />
                          Modify Time Slot
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Unscheduled Tasks if any */}
            {proposal.unscheduled_tasks?.length > 0 && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-400 space-y-1">
                <span className="font-semibold block flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {proposal.unscheduled_tasks.length} tasks could not fit in the requested horizon:
                </span>
                <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
                  {proposal.unscheduled_tasks.map((u) => (
                    <li key={u.task_id}>
                      <strong>{u.task_title}</strong>: {u.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Main Calendar Stream: Busy Blocks vs Discovered Focus Windows */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Discovered Focus Windows */}
        <Card className="border-border lg:col-span-1 shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Clock className="h-4 w-4 text-emerald-500" />
              Discovered Available Focus Windows
            </CardTitle>
            <CardDescription className="text-xs">
              Predicted windows free of meetings and interruptions.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-3 pt-1">
            {availability?.available_windows?.length === 0 ? (
              <div className="p-4 rounded-xl border border-dashed border-border text-xs text-muted-foreground text-center">
                No open focus windows found in this horizon.
              </div>
            ) : (
              availability?.available_windows?.map((win, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl border border-emerald-500/20 bg-emerald-50/20 dark:bg-emerald-950/20 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-foreground">
                      Focus Window ({win.duration_minutes}m)
                    </span>
                    {win.is_peak_focus ? (
                      <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30">
                        <Flame className="h-2.5 w-2.5 mr-1" />
                        Peak Circadian
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                        {win.focus_quality_score}% Score
                      </Badge>
                    )}
                  </div>
                  <span className="text-[11px] font-mono text-muted-foreground block">
                    {formatTimeRange(win.start_time, win.end_time)}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Right Column (2 cols): Calendar Commitments & Recovery Buffers */}
        <Card className="border-border lg:col-span-2 shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Calendar className="h-4 w-4 text-indigo-500" />
              Calendar Commitments & Blackouts
            </CardTitle>
            <CardDescription className="text-xs">
              Synchronized external meetings with ContextIQ post-meeting recovery buffers.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-3 pt-1">
            {availability?.busy_blocks?.length === 0 ? (
              <div className="p-4 rounded-xl border border-dashed border-border text-xs text-muted-foreground text-center">
                No calendar commitments found in this horizon.
              </div>
            ) : (
              availability?.busy_blocks?.map((block, idx) => {
                const isBuffer = block.is_recovery_buffer;
                return (
                  <div
                    key={idx}
                    className={`p-3 rounded-xl border text-xs flex items-center justify-between transition-all ${
                      isBuffer
                        ? "border-amber-500/30 bg-amber-50/20 dark:bg-amber-950/20 text-amber-900 dark:text-amber-300"
                        : "border-border/80 bg-card text-foreground"
                    }`}
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">{block.title}</span>
                        {isBuffer && (
                          <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30">
                            Recovery Buffer
                          </Badge>
                        )}
                      </div>
                      <span className="text-[11px] font-mono text-muted-foreground block">
                        {formatTimeRange(block.start_time, block.end_time)}
                      </span>
                    </div>

                    <Badge
                      variant="outline"
                      className={`text-[10px] font-mono uppercase ${
                        block.source.includes("google")
                          ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
                          : block.source.includes("microsoft") || block.source.includes("outlook")
                          ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                          : "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      {block.source.replace("_", " ")}
                    </Badge>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

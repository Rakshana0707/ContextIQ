"use client";

import React from "react";
import { Laptop, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { UnifiedTimelineView } from "@/components/activity/timeline-view";

export default function ActivityTimelinePage() {
  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <Laptop className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Cross-Device Activity Timeline
            </h1>
            <p className="text-xs text-muted-foreground">
              Unified cross-device behavioral history across Windows desktop workstations, mobile phones, and web sessions.
            </p>
          </div>
        </div>

        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Dashboard
        </Link>
      </div>

      {/* Main Unified Timeline View */}
      <UnifiedTimelineView />
    </div>
  );
}

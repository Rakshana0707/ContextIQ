"use client";

import React from "react";
import { CalendarDays, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { UnifiedCalendarView } from "@/components/calendar/unified-calendar-view";

export default function CalendarPage() {
  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <CalendarDays className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Smart Calendar & Scheduling
            </h1>
            <p className="text-xs text-muted-foreground">
              Unified view of external calendar events, circadian focus windows, and adaptive task schedules.
            </p>
          </div>
        </div>

        <Link
          href="/settings/integrations"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          Manage Calendar Integrations →
        </Link>
      </div>

      {/* Main Unified Calendar View */}
      <UnifiedCalendarView />
    </div>
  );
}

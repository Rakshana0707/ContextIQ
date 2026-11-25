"use client";

import React from "react";
import { MapPin, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { LocationIntelligenceView } from "@/components/context/location-intelligence-view";

export default function ContextLocationsPage() {
  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <MapPin className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Location Intelligence & Smart Reminders
            </h1>
            <p className="text-xs text-muted-foreground">
              Manage physical places, arrival focus windows, and departure &quot;One More Thing&quot; contextual reminders.
            </p>
          </div>
        </div>

        <Link
          href="/context"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Context &amp; Micro-Delays
        </Link>
      </div>

      {/* Main Location Intelligence View */}
      <LocationIntelligenceView />
    </div>
  );
}

"use client";

import React from "react";
import { AppShell } from "@/components/layout/app-shell";
import { KnowledgeGraphExplorer } from "@/components/graph/knowledge-graph-explorer";

export default function KnowledgeGraphPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
            Personal Productivity Knowledge Graph
            <span className="inline-flex items-center rounded-full bg-indigo-500/10 px-2 py-0.5 text-xs font-bold font-mono text-indigo-400 border border-indigo-500/20">
              Phase 8.2
            </span>
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Unified multi-relational architecture connecting tasks, projects, strategic goals, behavioral friction patterns, decisions, and outcomes with strict epistemic evidence grounding.
          </p>
        </div>

        <KnowledgeGraphExplorer />
      </div>
    </AppShell>
  );
}

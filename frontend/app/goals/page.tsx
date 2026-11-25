import { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { GoalProjectDashboard } from "@/components/goals/goal-project-dashboard";

export const metadata: Metadata = {
  title: "Goal & Project Intelligence | ContextIQ",
  description: "Strategic multi-tier goals, project health tracking, and behavioral alignment analytics.",
};

export default function GoalsPage() {
  return (
    <AppShell>
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <GoalProjectDashboard />
      </div>
    </AppShell>
  );
}

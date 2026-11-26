import { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { NaturalLanguageAnalyticsWorkspace } from "@/components/analytics/natural-language-analytics-workspace";

export const metadata: Metadata = {
  title: "Analytics Workspace | ContextIQ",
  description:
    "Natural-language productivity analytics, cross-project synthesis, and decision intelligence.",
};

export default function AnalyticsWorkspacePage() {
  return (
    <AppShell>
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <NaturalLanguageAnalyticsWorkspace />
      </div>
    </AppShell>
  );
}

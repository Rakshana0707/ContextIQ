import { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { DependencyIntelligenceDashboard } from "@/components/dependencies/dependency-intelligence-dashboard";

export const metadata: Metadata = {
  title: "Dependency Intelligence | ContextIQ",
  description: "Cross-task dependency discovery, latent blocker analysis, and cascading impact simulation.",
};

export default function DependenciesPage() {
  return (
    <AppShell>
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <DependencyIntelligenceDashboard />
      </div>
    </AppShell>
  );
}

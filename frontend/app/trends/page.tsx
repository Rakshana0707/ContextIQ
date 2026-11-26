import { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { BehavioralTrendsDashboard } from "@/components/trends/behavioral-trends-dashboard";

export const metadata: Metadata = {
  title: "Behavioral Trends | ContextIQ",
  description: "Long-term behavioral trend intelligence, focus consistency evolution, and milestone tracking.",
};

export default function TrendsPage() {
  return (
    <AppShell>
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <BehavioralTrendsDashboard />
      </div>
    </AppShell>
  );
}

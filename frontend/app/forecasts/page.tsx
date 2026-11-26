import { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { ProjectForecastDashboard } from "@/components/forecasts/project-forecast-dashboard";

export const metadata: Metadata = {
  title: "Project Progress Forecasting | ContextIQ",
  description: "Probabilistic project delivery forecasting, uncertainty modeling, and counterfactual what-if simulation.",
};

export default function ForecastsPage() {
  return (
    <AppShell>
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <ProjectForecastDashboard />
      </div>
    </AppShell>
  );
}

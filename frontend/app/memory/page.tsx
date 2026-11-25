import { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { BehavioralMemoryExplorer } from "@/components/memory/behavioral-memory-explorer";

export const metadata: Metadata = {
  title: "Behavioral Memory | ContextIQ",
  description: "Long-term behavioral memory and pattern evolution grounded in the personal digital twin profile.",
};

export default function BehavioralMemoryPage() {
  return (
    <AppShell>
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <BehavioralMemoryExplorer />
      </div>
    </AppShell>
  );
}

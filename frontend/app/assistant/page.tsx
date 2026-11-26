import { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { ConversationalAssistant } from "@/components/assistant/conversational-assistant";

export const metadata: Metadata = {
  title: "Productivity Assistant | ContextIQ",
  description: "Knowledge-grounded conversational intelligence for tasks, projects, goals, and behavioral trends.",
};

export default function AssistantPage() {
  return (
    <AppShell>
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <ConversationalAssistant />
      </div>
    </AppShell>
  );
}

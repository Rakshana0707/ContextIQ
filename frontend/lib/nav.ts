import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  ListChecks,
  Radar,
  Lightbulb,
  Sparkles,
  BrainCircuit,
  Activity,
  ShieldCheck,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const navItems: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    description: "Today's behaviour overview",
  },
  {
    href: "/tasks",
    label: "Tasks",
    icon: ListChecks,
    description: "Create, track, and resolve tasks",
  },
  {
    href: "/context",
    label: "Context & Micro-Delays",
    icon: Radar,
    description: "Focus, interruptions, and recovery lag",
  },
  {
    href: "/predictions",
    label: "Predictions",
    icon: BrainCircuit,
    description: "Forgetting risk, explained",
  },
  {
    href: "/recommendations",
    label: "Recommendations",
    icon: Sparkles,
    description: "Contextual suggestions",
  },
  {
    href: "/insights",
    label: "Behaviour Insights",
    icon: Lightbulb,
    description: "Patterns in how you work",
  },
  {
    href: "/monitoring",
    label: "ML Monitoring",
    icon: Activity,
    description: "Drift detection & continual learning",
  },
  {
    href: "/privacy",
    label: "Privacy & Telemetry",
    icon: ShieldCheck,
    description: "Consent, pause controls, and app exclusions",
  },
];

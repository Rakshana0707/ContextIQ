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
  Radio,
  UserCheck,
  Clock,
  Zap,
  GitFork,
  Scale,
  Bell,
  Calendar,
  CalendarDays,
  Laptop,
  MapPin,
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
    href: "/telemetry",
    label: "Telemetry & Agent",
    icon: Radio,
    description: "Live desktop activity, interruptions & agent status",
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
  {
    href: "/calendar",
    label: "Smart Calendar",
    icon: CalendarDays,
    description: "Ecosystem calendar & intelligent scheduling",
  },
  {
    href: "/activity",
    label: "Cross-Device Timeline",
    icon: Laptop,
    description: "Desktop & mobile timeline reconstruction",
  },
  {
    href: "/context/locations",
    label: "Location Intelligence",
    icon: MapPin,
    description: "Places, routines & arrival/departure reminders",
  },
  {
    href: "/settings/integrations",
    label: "Calendar Integrations",
    icon: Calendar,
    description: "Google Calendar & Outlook synchronization",
  },
  {
    href: "/automations",
    label: "Automation Center",
    icon: Zap,
    description: "User-defined proactive rules, triggers & governed actions",
  },
  {
    href: "/graph",
    label: "Knowledge Graph",
    icon: GitFork,
    description: "Personal productivity knowledge graph & causal evidence explorer",
  },
];

export const adaptiveNavItems: NavItem[] = [
  {
    href: "/adaptive/profile",
    label: "Digital Twin Profile",
    icon: UserCheck,
    description: "Empirical behavioral patterns & dimensions",
  },
  {
    href: "/adaptive/focus",
    label: "Focus-Window Explorer",
    icon: Clock,
    description: "Circadian suitability & high-quality focus periods",
  },
  {
    href: "/adaptive/interventions",
    label: "Intervention Center",
    icon: Zap,
    description: "Actionable recommendations & explainability evidence",
  },
  {
    href: "/adaptive/learning",
    label: "Contextual Bandit",
    icon: GitFork,
    description: "LinUCB & Thompson Sampling exploration metrics",
  },
  {
    href: "/adaptive/effectiveness",
    label: "Causal Effectiveness",
    icon: Scale,
    description: "Doubly Robust ATE & randomized holdout analytics",
  },
  {
    href: "/adaptive/notifications",
    label: "Notification Controls",
    icon: Bell,
    description: "Quiet hours, cognitive limits & fatigue metrics",
  },
];

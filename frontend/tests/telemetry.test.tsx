import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { DesktopAgentStatus } from "@/components/telemetry/desktop-agent-status";
import { TelemetryOverviewCard } from "@/components/telemetry/telemetry-overview-card";
import { InterruptionExplorer } from "@/components/telemetry/interruption-explorer";
import { TelemetryPrivacyControls } from "@/components/telemetry/telemetry-privacy-controls";
import TelemetryDashboardPage from "@/app/telemetry/page";
import { telemetryApi } from "@/lib/api/services/telemetry";
import type {
  TelemetryAgentStatus as StatusType,
  DailyTelemetryOverview,
  DetectedInterruptionItem,
} from "@/types/telemetry";

vi.mock("@/lib/api/services/telemetry", () => ({
  telemetryApi: {
    getAgentStatus: vi.fn(),
    getOverview: vi.fn(),
    getDetectedInterruptions: vi.fn(),
    getRecoveryAnalytics: vi.fn(),
    getFrictionIndex: vi.fn(),
    getInterruptionTrends: vi.fn(),
    getPersonalBaseline: vi.fn(),
    pauseAgent: vi.fn(),
    resumeAgent: vi.fn(),
    submitFeedback: vi.fn(),
  },
}));

const mockStatus: StatusType = {
  status: "online",
  last_seen: new Date().toISOString(),
  pending_events: 5,
  agent_version: "v0.2.0-win",
  is_paused: false,
  device_id: "test-pc",
};

const mockOverview: DailyTelemetryOverview = {
  total_events_today: 342,
  total_focus_minutes: 195,
  total_idle_minutes: 25,
  detected_interruptions_count: 4,
  top_applications: [{ name: "VS Code", focusMinutes: 120, percentage: 60 }],
  sync_status: "HEALTHY",
  last_sync_timestamp: new Date().toISOString(),
};

const mockInterruptions: DetectedInterruptionItem[] = [
  {
    id: "int-test-1",
    interruption_type: "APPLICATION_SWITCH",
    severity: "HIGH",
    confidence_score: 0.95,
    start_timestamp: new Date().toISOString(),
    end_timestamp: new Date().toISOString(),
    duration_seconds: 300,
    resumption_lag_seconds: 45,
    return_to_device_delay_seconds: 10,
    return_to_app_delay_seconds: 35,
    confirmed_task_resumption_delay_seconds: null,
    evidence_signals: ["Sudden switch away from VS Code"],
    session_id: "sess-1",
    feedback_classification: null,
    feedback_notes: null,
  },
];

afterEach(() => {
  vi.clearAllMocks();
});

describe("DesktopAgentStatus Component", () => {
  it("renders active monitoring status when agent is online", () => {
    render(
      <DesktopAgentStatus
        status={mockStatus}
        loading={false}
        onRefresh={vi.fn()}
        onTogglePause={vi.fn()}
        isTogglingPause={false}
      />,
    );

    expect(screen.getByText("Active Monitoring")).toBeInTheDocument();
    expect(screen.getByText("v0.2.0-win")).toBeInTheDocument();
    expect(screen.getByText("5 events")).toBeInTheDocument();
    expect(screen.getByText("Pause Monitoring")).toBeInTheDocument();
  });

  it("renders paused monitoring status when paused", () => {
    render(
      <DesktopAgentStatus
        status={{ ...mockStatus, is_paused: true, status: "paused" }}
        loading={false}
        onRefresh={vi.fn()}
        onTogglePause={vi.fn()}
        isTogglingPause={false}
      />,
    );

    expect(screen.getByText("Monitoring Paused")).toBeInTheDocument();
    expect(screen.getByText("Resume Monitoring")).toBeInTheDocument();
  });
});

describe("TelemetryOverviewCard Component", () => {
  it("renders metric cards with correct values", () => {
    render(<TelemetryOverviewCard overview={mockOverview} loading={false} />);

    expect(screen.getByText("342")).toBeInTheDocument();
    expect(screen.getByText("Observed Events")).toBeInTheDocument();
    expect(screen.getByText("HEALTHY")).toBeInTheDocument();
    expect(screen.getByText("Detected Interruptions")).toBeInTheDocument();
  });
});

describe("InterruptionExplorer Component", () => {
  it("renders detected interruptions and allows feedback submission", async () => {
    const onSubmitFeedback = vi.fn().mockResolvedValue(undefined);

    render(
      <InterruptionExplorer
        interruptions={mockInterruptions}
        onSubmitFeedback={onSubmitFeedback}
        loading={false}
      />,
    );

    expect(screen.getByText("APPLICATION SWITCH")).toBeInTheDocument();
    expect(screen.getByText("300s")).toBeInTheDocument();

    const genuineBtn = screen.getByRole("button", { name: /genuine interruption/i });
    fireEvent.click(genuineBtn);

    expect(onSubmitFeedback).toHaveBeenCalledWith("int-test-1", {
      classification: "GENUINE_INTERRUPTION",
      notes: undefined,
    });
  });
});

describe("TelemetryPrivacyControls Component", () => {
  it("renders quick pause buttons and triggers callback", () => {
    const onPause = vi.fn();
    const onResume = vi.fn();

    render(
      <TelemetryPrivacyControls
        isPaused={false}
        onPause={onPause}
        onResume={onResume}
        loading={false}
      />,
    );

    const pause15m = screen.getByRole("button", { name: "15m" });
    fireEvent.click(pause15m);
    expect(onPause).toHaveBeenCalledWith(15);
  });
});

describe("TelemetryDashboardPage Integration", () => {
  it("loads and renders all telemetry panels seamlessly", async () => {
    vi.mocked(telemetryApi.getAgentStatus).mockResolvedValue({
      data: mockStatus,
      error: null,
    });
    vi.mocked(telemetryApi.getOverview).mockResolvedValue({
      data: mockOverview,
      error: null,
    });
    vi.mocked(telemetryApi.getDetectedInterruptions).mockResolvedValue({
      data: mockInterruptions,
      error: null,
    });
    vi.mocked(telemetryApi.getRecoveryAnalytics).mockResolvedValue({
      data: {
        mean_resumption_lag_seconds: 45,
        median_resumption_lag_seconds: 40,
        mean_return_to_device_delay_seconds: 10,
        mean_return_to_app_delay_seconds: 35,
        mean_confirmed_resumption_delay_seconds: 50,
        total_interruptions_measured: 10,
        lag_distribution: [{ range: "< 30s", count: 5 }],
      },
      error: null,
    });
    vi.mocked(telemetryApi.getFrictionIndex).mockResolvedValue({
      data: {
        friction_index: 42,
        friction_tier: "MODERATE",
        component_scores: { lag: 40 },
        dominant_friction_driver: "resumption_lag",
        interpretation: "Moderate friction detected",
      },
      error: null,
    });
    vi.mocked(telemetryApi.getInterruptionTrends).mockResolvedValue({
      data: [{ hour_of_day: 10, interruption_count: 2, avg_resumption_lag_seconds: 30 }],
      error: null,
    });
    vi.mocked(telemetryApi.getPersonalBaseline).mockResolvedValue({
      data: {
        rolling_14d_mean_lag: 50,
        rolling_14d_interruption_freq: 4,
        today_relative_lag_ratio: 0.9,
        today_relative_freq_ratio: 1.0,
        baseline_tier: "SIMILAR",
      },
      error: null,
    });

    render(<TelemetryDashboardPage />);

    expect(screen.getByText("Behavioral Telemetry & Desktop Agent")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Active Monitoring")).toBeInTheDocument();
      expect(screen.getByText("342")).toBeInTheDocument();
      expect(screen.getByText("APPLICATION SWITCH")).toBeInTheDocument();
    });
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UnifiedCalendarView } from "@/components/calendar/unified-calendar-view";
import { schedulingApi } from "@/lib/api/services/scheduling";

vi.mock("@/lib/api/services/scheduling", () => ({
  schedulingApi: {
    getAvailability: vi.fn(),
    generate: vi.fn(),
    preview: vi.fn(),
    modifySlot: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  },
}));

describe("UnifiedCalendarView Component (Phase 5.9 Task 3 & 4)", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders external calendar commitments and discovered focus windows", async () => {
    (schedulingApi.getAvailability as any).mockResolvedValueOnce({
      user_id: "test-user-id",
      horizon_start: "2026-11-24T09:00:00Z",
      horizon_end: "2026-11-24T18:00:00Z",
      total_available_minutes: 360,
      busy_blocks: [
        {
          title: "Quarterly Ecosystem Review",
          start_time: "2026-11-24T10:00:00Z",
          end_time: "2026-11-24T11:00:00Z",
          source: "google_calendar",
          is_recovery_buffer: false,
        },
        {
          title: "Post-Meeting Recovery Buffer",
          start_time: "2026-11-24T11:00:00Z",
          end_time: "2026-11-24T11:15:00Z",
          source: "contextiq_buffer",
          is_recovery_buffer: true,
        },
      ],
      available_windows: [
        {
          start_time: "2026-11-24T13:00:00Z",
          end_time: "2026-11-24T16:00:00Z",
          duration_minutes: 180,
          focus_quality_score: 95,
          is_peak_focus: true,
        },
      ],
    });

    render(<UnifiedCalendarView />);

    await waitFor(() => {
      expect(screen.getByText("Quarterly Ecosystem Review")).toBeInTheDocument();
      expect(screen.getByText("Post-Meeting Recovery Buffer")).toBeInTheDocument();
      expect(screen.getByText(/Focus Window \(180m\)/i)).toBeInTheDocument();
      expect(screen.getByText("Peak Circadian")).toBeInTheDocument();
    });
  });

  it("generates and previews an adaptive schedule proposal", async () => {
    (schedulingApi.getAvailability as any).mockResolvedValueOnce({
      busy_blocks: [],
      available_windows: [],
    });

    (schedulingApi.generate as any).mockResolvedValueOnce({
      proposal_id: "prop-456",
      user_id: "test-user-id",
      status: "DRAFT",
      scheduled_slots: [
        {
          task_id: "task-001",
          task_title: "Implement Graph Sync Algorithm",
          start_time: "2026-11-24T13:00:00Z",
          end_time: "2026-11-24T14:30:00Z",
          duration_minutes: 90,
          focus_quality_score: 94,
          is_peak_focus: true,
          explanation: {
            primary_rationale: "Matched to circadian morning peak with low distraction likelihood",
            behavioral_factors: {},
            calendar_constraints_considered: ["No conflicting meetings"],
            rejected_alternatives: [],
            confidence_score: 0.95,
          },
        },
      ],
      unscheduled_tasks: [],
      total_scheduled_minutes: 90,
      created_at: "2026-11-24T12:00:00Z",
    });

    render(<UnifiedCalendarView />);

    const generateBtn = screen.getByRole("button", { name: /Generate Proposed Schedule/i });
    await user.click(generateBtn);

    await waitFor(() => {
      expect(screen.getByText("Implement Graph Sync Algorithm")).toBeInTheDocument();
      expect(
        screen.getByText(/Matched to circadian morning peak with low distraction likelihood/i)
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Approve & Commit/i })).toBeInTheDocument();
    });
  });

  it("approves and commits proposal to target provider", async () => {
    (schedulingApi.getAvailability as any).mockResolvedValue({
      busy_blocks: [],
      available_windows: [],
    });

    (schedulingApi.generate as any).mockResolvedValueOnce({
      proposal_id: "prop-789",
      status: "PENDING_APPROVAL",
      scheduled_slots: [
        {
          task_id: "task-002",
          task_title: "Review Architecture Pull Request",
          start_time: "2026-11-24T15:00:00Z",
          end_time: "2026-11-24T16:00:00Z",
          duration_minutes: 60,
          focus_quality_score: 88,
          is_peak_focus: false,
          explanation: { primary_rationale: "Afternoon focus alignment" },
        },
      ],
      unscheduled_tasks: [],
    });

    (schedulingApi.approve as any).mockResolvedValueOnce({
      proposal_id: "prop-789",
      status: "COMMITTED",
      total_slots: 1,
      committed_events: 1,
      created_calendar_event_ids: ["gcal-ev-999"],
      provider: "google_calendar",
      committed_at: "2026-11-24T12:05:00Z",
    });

    render(<UnifiedCalendarView />);

    // Generate
    const generateBtn = screen.getByRole("button", { name: /Generate Proposed Schedule/i });
    await user.click(generateBtn);

    // Approve
    const approveBtn = await screen.findByRole("button", { name: /Approve & Commit/i });
    await user.click(approveBtn);

    await waitFor(() => {
      expect(schedulingApi.approve).toHaveBeenCalledWith("prop-789", {
        target_provider: "google_calendar",
      });
      expect(
        screen.getByText(/Schedule successfully committed to google_calendar!/i)
      ).toBeInTheDocument();
    });
  });
});

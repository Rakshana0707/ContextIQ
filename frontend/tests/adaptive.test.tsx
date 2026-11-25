import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdaptiveTaskRanking } from "@/components/tasks/adaptive-task-ranking";
import { adaptiveApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  adaptiveApi: {
    getTaskRanking: vi.fn(),
    recordFeedback: vi.fn(),
  },
}));

describe("AdaptiveTaskRanking Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading skeleton and then ranked tasks", async () => {
    (adaptiveApi.getTaskRanking as any).mockResolvedValueOnce({
      data: {
        preset: "BALANCED",
        as_of: "2026-11-22T12:00:00Z",
        summary_insights: ["Matched 1 task to active focus window"],
        items: [
          {
            task_id: "task-101",
            title: "Write Architecture Design Doc",
            rank: 1,
            composite_score: 88.5,
            primary_driver: "FOCUS_WINDOW_MATCH",
            grounded_explanation: "Optimal alignment with high-focus morning window",
            estimated_minutes: 60,
            recovery_buffer_minutes: 15,
            is_blocked: false,
            context_tag: "DEEP_WORK",
            score_breakdown: {
              urgency_score: 0.8,
              forgetting_risk_score: 0.4,
              personal_suitability_score: 0.9,
              context_compatibility_score: 0.85,
              scheduling_feasibility_score: 0.9,
            },
            recommended_focus_window: {
              start_time: "09:00",
              end_time: "11:30",
            },
            constraints_applied: ["Circadian peak aligned"],
          },
        ],
      },
    });

    render(<AdaptiveTaskRanking />);

    await waitFor(() => {
      expect(screen.getByText("Write Architecture Design Doc")).toBeInTheDocument();
      expect(screen.getByText("#1")).toBeInTheDocument();
      expect(screen.getByText("88.5")).toBeInTheDocument();
      expect(screen.getByText(/Optimal alignment with high-focus morning window/i)).toBeInTheDocument();
    });
  });

  it("allows user to accept a ranked task", async () => {
    const user = userEvent.setup();
    const mockOnTaskStarted = vi.fn();

    (adaptiveApi.getTaskRanking as any).mockResolvedValueOnce({
      data: {
        preset: "BALANCED",
        as_of: "2026-11-22T12:00:00Z",
        summary_insights: [],
        items: [
          {
            task_id: "task-202",
            title: "Review Pull Request",
            rank: 1,
            composite_score: 75.0,
            primary_driver: "QUICK_WIN_ADMIN",
            grounded_explanation: "Low cognitive overhead task",
            estimated_minutes: 20,
            recovery_buffer_minutes: 5,
            is_blocked: false,
            score_breakdown: {
              urgency_score: 0.5,
              forgetting_risk_score: 0.2,
              personal_suitability_score: 0.8,
              context_compatibility_score: 0.8,
              scheduling_feasibility_score: 0.9,
            },
            constraints_applied: [],
          },
        ],
      },
    });

    (adaptiveApi.recordFeedback as any).mockResolvedValueOnce({
      data: { success: true },
    });

    render(<AdaptiveTaskRanking onTaskStarted={mockOnTaskStarted} />);

    await waitFor(() => {
      expect(screen.getByText("Review Pull Request")).toBeInTheDocument();
    });

    const startBtn = screen.getByRole("button", { name: /start now/i });
    await user.click(startBtn);

    expect(adaptiveApi.recordFeedback).toHaveBeenCalledWith(
      expect.objectContaining({
        task_id: "task-202",
        action: "ACCEPTED",
      }),
    );
    expect(mockOnTaskStarted).toHaveBeenCalledWith("task-202");
  });
});

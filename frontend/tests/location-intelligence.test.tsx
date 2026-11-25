import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocationIntelligenceView } from "@/components/context/location-intelligence-view";
import { locationContextApi } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<any>("@/lib/api");
  return {
    ...actual,
    locationContextApi: {
      getLocations: vi.fn(),
      createLocation: vi.fn(),
      deleteLocation: vi.fn(),
      recordCheckIn: vi.fn(),
      getLocationRecommendations: vi.fn(),
    },
  };
});

describe("LocationIntelligenceView Component (Phase 5.9 Task 6)", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders saved places, category badges, and upcoming contextual reminders", async () => {
    (locationContextApi.getLocations as any).mockResolvedValue([
      {
        id: "loc-campus",
        user_id: "user-1",
        name: "Stanford Quad",
        location_type: "CAMPUS",
        latitude: 37.4275,
        longitude: -122.1697,
        radius_meters: 150,
        is_active: true,
        reminders_enabled: true,
        arrival_reminder_enabled: true,
        departure_reminder_enabled: true,
        created_at: "2026-11-24T10:00:00Z",
        updated_at: "2026-11-24T10:00:00Z",
      },
    ]);

    (locationContextApi.getLocationRecommendations as any).mockImplementation(
      async (params: any) => {
        if (params.trigger_type === "DEPARTURE") {
          return {
            location_id: "loc-campus",
            location_name: "Stanford Quad",
            trigger_type: "DEPARTURE",
            reminders: [
              {
                task_id: "task-sig",
                title: "Advisor Thesis Signoff",
                message: "Before leaving Stanford Quad: 'Advisor Thesis Signoff' is still pending.",
                trigger_type: "DEPARTURE",
                association_source: "EXPLICIT",
                confidence_score: 1.0,
                recommendation_arm: "arm_3_one_more_thing",
              },
            ],
            total_reminders: 1,
            quiet_hours_active: false,
            focus_session_active: false,
            suppressed_count: 0,
          };
        }
        return {
          location_id: "loc-campus",
          location_name: "Stanford Quad",
          trigger_type: "ARRIVAL",
          reminders: [],
          total_reminders: 0,
          quiet_hours_active: false,
          focus_session_active: false,
          suppressed_count: 0,
        };
      }
    );

    render(<LocationIntelligenceView />);

    await waitFor(() => {
      expect(screen.getAllByText("Stanford Quad").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Advisor Thesis Signoff")).toBeInTheDocument();
      expect(screen.getByText("Before Leaving")).toBeInTheDocument();
      expect(screen.getByText("EXPLICIT (100%)")).toBeInTheDocument();
    });
  });

  it("simulates edge boundary check-ins without transmitting continuous GPS", async () => {
    (locationContextApi.getLocations as any).mockResolvedValue([
      {
        id: "loc-lib",
        user_id: "user-1",
        name: "Green Library",
        location_type: "LIBRARY",
        is_active: true,
        reminders_enabled: true,
      },
    ]);

    (locationContextApi.getLocationRecommendations as any).mockResolvedValue({
      reminders: [],
    });

    (locationContextApi.recordCheckIn as any).mockResolvedValueOnce({
      id: "cin-999",
      location_name: "Green Library",
      check_in_type: "GEOFENCE_ENTER",
      occurred_at: "2026-11-24T15:00:00Z",
    });

    render(<LocationIntelligenceView />);

    const arriveBtn = await screen.findByRole("button", { name: /Simulate Arrival \(Enter\)/i });
    await user.click(arriveBtn);

    await waitFor(() => {
      expect(locationContextApi.recordCheckIn).toHaveBeenCalledWith(
        expect.objectContaining({
          location_id: "loc-lib",
          check_in_type: "GEOFENCE_ENTER",
        })
      );
      expect(
        screen.getByText(/Recorded check-in 'GEOFENCE_ENTER' at Green Library!/i)
      ).toBeInTheDocument();
    });
  });
});

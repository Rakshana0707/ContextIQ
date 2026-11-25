import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import IntegrationsSettingsPage from "@/app/settings/integrations/page";
import { SyncHealthPanel } from "@/components/integrations/sync-health-panel";
import { integrationsApi } from "@/lib/api/services/integrations";
import { devicesApi } from "@/lib/api";

vi.mock("@/lib/api/services/integrations", () => ({
  integrationsApi: {
    listIntegrations: vi.fn(),
    connectProvider: vi.fn(),
    disconnectIntegration: vi.fn(),
    triggerSync: vi.fn(),
  },
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<any>("@/lib/api");
  return {
    ...actual,
    devicesApi: {
      list: vi.fn(),
      register: vi.fn(),
      revoke: vi.fn(),
    },
  };
});

describe("Integration Management & Sync Health (Phase 5.9 Task 2 & 8)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT display mock integrations as connected when no tokens exist", async () => {
    // Empty integrations returned from API
    (integrationsApi.listIntegrations as any).mockResolvedValue([]);
    (devicesApi.list as any).mockResolvedValue([]);

    render(<IntegrationsSettingsPage />);

    await waitFor(() => {
      // Both Google Calendar and Microsoft Outlook must be "Not Linked"
      const notLinkedBadges = screen.getAllByText("Not Linked");
      expect(notLinkedBadges.length).toBe(2);
      expect(screen.getByRole("button", { name: /Connect Google Calendar/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Connect Microsoft Outlook/i })).toBeInTheDocument();
    });
  });

  it("renders synchronization health panel with active devices and provider status", async () => {
    (integrationsApi.listIntegrations as any).mockResolvedValue([
      {
        id: "int-gcal-1",
        provider: "google_calendar",
        provider_email: "engineer@company.com",
        connection_status: "CONNECTED",
        sync_status: "SYNCED",
        last_synced_at: "2026-11-24T12:00:00Z",
      },
    ]);

    (devicesApi.list as any).mockResolvedValue([
      {
        id: "dev-win-1",
        user_id: "user-1",
        device_id: "workstation-x1",
        device_name: "ThinkPad Workstation",
        device_type: "DESKTOP",
        platform: "WINDOWS",
        application_version: "1.2.0",
        connection_status: "ONLINE",
        synchronization_status: "SYNCED",
        last_seen_timestamp: "2026-11-24T12:05:00Z",
        is_active: true,
      },
    ]);

    render(<SyncHealthPanel />);

    await waitFor(() => {
      expect(screen.getByText("Ecosystem Synchronization Health")).toBeInTheDocument();
      expect(screen.getByText("ThinkPad Workstation")).toBeInTheDocument();
      expect(screen.getByText("ONLINE")).toBeInTheDocument();
      expect(screen.getByText("engineer@company.com")).toBeInTheDocument();
      expect(screen.getByText("Healthy")).toBeInTheDocument();
    });
  });
});

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { activityApi, devicesApi, DeviceRead, UnifiedTimelineEventDTO, CrossDeviceSessionRead } from "@/lib/api";

export function UnifiedTimelineView() {
  const [devices, setDevices] = useState<DeviceRead[]>([]);
  const [events, setEvents] = useState<UnifiedTimelineEventDTO[]>([]);
  const [sessions, setSessions] = useState<CrossDeviceSessionRead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [selectedDevice, setSelectedDevice] = useState<string>("ALL");
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [applicationQuery, setApplicationQuery] = useState<string>("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [devList, tlEvents, sessionList] = await Promise.all([
        devicesApi.list().catch(() => []),
        activityApi.getTimeline({
          device_id: selectedDevice !== "ALL" ? selectedDevice : undefined,
          device_type: selectedType !== "ALL" ? selectedType : undefined,
          application: applicationQuery.trim() || undefined,
          limit: 50,
        }).catch(() => []),
        activityApi.getCrossDeviceSessions(24).catch(() => []),
      ]);

      setDevices(devList);
      setEvents(tlEvents);
      setSessions(sessionList);
    } finally {
      setLoading(false);
    }
  }, [selectedDevice, selectedType, applicationQuery]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getDeviceIcon = (deviceType: string) => {
    switch (deviceType.toUpperCase()) {
      case "DESKTOP":
        return "💻";
      case "MOBILE":
        return "📱";
      case "WEB":
        return "🌐";
      case "CALENDAR":
        return "📅";
      default:
        return "⚡";
    }
  };

  const handleRevokeDevice = async (deviceId: string) => {
    if (confirm(`Are you sure you want to revoke access for device: ${deviceId}?`)) {
      await devicesApi.revoke(deviceId);
      loadData();
    }
  };

  return (
    <div className="space-y-6 text-zinc-100">
      {/* Top Banner / Device Summary */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Unified Behavioral Timeline</h1>
          <p className="text-sm text-zinc-400">
            Cohesive cross-device activity stream synthesized across Desktop, Mobile, Web, and External Calendars.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => loadData()}
            className="rounded-lg bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-200 transition hover:bg-zinc-700"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Cross-Device Sessions Card */}
      {sessions.length > 0 && (
        <div className="rounded-xl border border-indigo-900/60 bg-zinc-900/80 p-5 shadow-lg backdrop-blur">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-indigo-400">
              Active Cross-Device Work Sessions
            </h2>
            <span className="rounded-full bg-indigo-950 px-2.5 py-0.5 text-xs font-semibold text-indigo-300">
              {sessions.length} Reconstructed
            </span>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {sessions.map((sess) => (
              <div
                key={sess.session_id}
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4 transition hover:border-zinc-700"
              >
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span>
                    Started: {new Date(sess.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="font-semibold text-zinc-300">
                    Duration: {Math.round(sess.duration_seconds / 60)} mins
                  </span>
                </div>

                <div className="mt-2 flex items-center gap-2">
                  <span className="text-base">{getDeviceIcon(sess.primary_device_type)}</span>
                  <span className="text-sm font-semibold text-white">
                    Primary: {sess.primary_device_type}
                  </span>
                  {sess.device_transitions_count > 0 && (
                    <span className="rounded bg-amber-950/80 px-2 py-0.5 text-xs font-medium text-amber-300">
                      ⚡ {sess.device_transitions_count} Device Switches
                    </span>
                  )}
                </div>

                {sess.cross_device_interruption_seconds > 0 && (
                  <p className="mt-2 text-xs text-rose-300">
                    Mobile disruption lag: {Math.round(sess.cross_device_interruption_seconds)}s
                  </p>
                )}

                <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-400">
                  {Object.entries(sess.device_time_breakdown).map(([dev, sec]) => (
                    <span key={dev} className="rounded bg-zinc-800 px-2 py-0.5">
                      {getDeviceIcon(dev)} {dev}: {Math.round(sec / 60)}m
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter Controls */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-xs">
        <div className="flex items-center gap-2">
          <label className="font-semibold text-zinc-400">Device:</label>
          <select
            value={selectedDevice}
            onChange={(e) => setSelectedDevice(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-zinc-200 focus:outline-none"
          >
            <option value="ALL">All Authorized Devices</option>
            {devices.map((d) => (
              <option key={d.device_id} value={d.device_id}>
                {getDeviceIcon(d.device_type)} {d.device_name} ({d.platform})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="font-semibold text-zinc-400">Category:</label>
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-zinc-200 focus:outline-none"
          >
            <option value="ALL">All Categories</option>
            <option value="DESKTOP">Desktop Only</option>
            <option value="MOBILE">Mobile Only</option>
            <option value="WEB">Web Only</option>
            <option value="CALENDAR">Calendar Commitments</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="font-semibold text-zinc-400">App:</label>
          <input
            type="text"
            placeholder="Search app..."
            value={applicationQuery}
            onChange={(e) => setApplicationQuery(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-zinc-200 placeholder-zinc-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Timeline Stream */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-12 text-center text-sm text-zinc-500">Loading unified behavioral timeline...</div>
        ) : events.length === 0 ? (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 py-12 text-center text-zinc-500">
            No events found matching the active device or application filters.
          </div>
        ) : (
          events.map((ev) => (
            <div
              key={ev.event_id}
              className="flex items-start gap-4 rounded-xl border border-zinc-800 bg-zinc-900/70 p-4 transition hover:border-zinc-700"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-800 text-lg">
                {getDeviceIcon(ev.device_type)}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">
                      {ev.application_identifier || ev.event_type}
                    </span>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
                      {ev.device_name || ev.device_type}
                    </span>
                    <span className="rounded bg-indigo-950/60 px-2 py-0.5 text-xs font-medium text-indigo-300">
                      {ev.platform}
                    </span>
                  </div>

                  <span className="text-xs text-zinc-500">
                    {new Date(ev.occurred_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </span>
                </div>

                <div className="mt-1 flex items-center gap-3 text-xs text-zinc-400">
                  <span>Source: {ev.source}</span>
                  {ev.duration_seconds != null && (
                    <span>Duration: {Math.round(ev.duration_seconds)}s</span>
                  )}
                  {ev.clock_skew_seconds !== 0 && (
                    <span className="text-amber-400/80">
                      Skew: {ev.clock_skew_seconds > 0 ? "+" : ""}
                      {ev.clock_skew_seconds.toFixed(1)}s
                    </span>
                  )}
                </div>

                {ev.payload && Object.keys(ev.payload).length > 0 && (
                  <p className="mt-1 truncate text-xs text-zinc-500">
                    {JSON.stringify(ev.payload)}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Authorized Devices Registry Drawer / Footer */}
      {devices.length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Registered Devices ({devices.length})
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {devices.map((d) => (
              <div
                key={d.device_id}
                className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 text-xs"
              >
                <div>
                  <div className="flex items-center gap-1.5 font-medium text-zinc-200">
                    <span>{getDeviceIcon(d.device_type)}</span>
                    <span>{d.device_name}</span>
                  </div>
                  <div className="mt-1 text-zinc-500">
                    {d.platform} • Last seen {new Date(d.last_seen_timestamp).toLocaleDateString()}
                  </div>
                </div>

                {d.is_active ? (
                  <button
                    onClick={() => handleRevokeDevice(d.device_id)}
                    className="rounded bg-rose-950/60 px-2 py-1 font-semibold text-rose-300 hover:bg-rose-900"
                  >
                    Revoke
                  </button>
                ) : (
                  <span className="text-zinc-500">Revoked</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bell,
  Building,
  CheckCircle2,
  Clock,
  Compass,
  GraduationCap,
  Home,
  Layers,
  MapPin,
  Plus,
  RefreshCw,
  Shield,
  ShieldCheck,
  Sparkles,
  Trash2,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  locationContextApi,
  LocationContextRead,
  LocationReminderDTO,
} from "@/lib/api";

export function LocationIntelligenceView() {
  const [locations, setLocations] = useState<LocationContextRead[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<LocationContextRead | null>(null);
  const [reminders, setReminders] = useState<LocationReminderDTO[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // New location form state
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newLocName, setNewLocName] = useState<string>("");
  const [newLocType, setNewLocType] = useState<string>("OFFICE");
  const [newRadius, setNewRadius] = useState<number>(150);

  // Consent settings state
  const [locationEnabled, setLocationEnabled] = useState<boolean>(true);
  const [geofencingEnabled, setGeofencingEnabled] = useState<boolean>(true);

  const loadLocations = useCallback(async () => {
    setLoading(true);
    try {
      const locList = await locationContextApi.getLocations(false);
      const safeList = Array.isArray(locList) ? locList : [];
      setLocations(safeList);
      if (safeList.length > 0 && !selectedLocation) {
        setSelectedLocation(safeList[0]);
      }
    } catch {
      setLocations([]);
      setMessage({ type: "error", text: "Failed to load saved locations." });
    } finally {
      setLoading(false);
    }
  }, [selectedLocation]);

  useEffect(() => {
    loadLocations();
  }, [loadLocations]);

  // Load reminders when selected location changes
  useEffect(() => {
    if (!selectedLocation) return;
    const fetchReminders = async () => {
      try {
        const resp = await locationContextApi.getLocationRecommendations({
          location_id: selectedLocation.id,
          trigger_type: "ARRIVAL",
        });
        const depResp = await locationContextApi.getLocationRecommendations({
          location_id: selectedLocation.id,
          trigger_type: "DEPARTURE",
        });
        setReminders([...(resp.reminders || []), ...(depResp.reminders || [])]);
      } catch {
        setReminders([]);
      }
    };
    fetchReminders();
  }, [selectedLocation]);

  const handleCreateLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLocName.trim()) return;
    setActionLoading(true);
    try {
      const created = await locationContextApi.createLocation({
        name: newLocName.trim(),
        location_type: newLocType,
        radius_meters: newRadius,
        reminders_enabled: true,
        arrival_reminder_enabled: true,
        departure_reminder_enabled: true,
      });
      setMessage({ type: "success", text: `Location '${created.name}' created successfully.` });
      setShowCreateModal(false);
      setNewLocName("");
      await loadLocations();
      setSelectedLocation(created);
    } catch {
      setMessage({ type: "error", text: "Failed to create location." });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteLocation = async (locId: string, locName: string) => {
    if (!confirm(`Are you sure you want to delete ${locName}?`)) return;
    try {
      await locationContextApi.deleteLocation(locId);
      setMessage({ type: "success", text: `Deleted location '${locName}'.` });
      if (selectedLocation?.id === locId) {
        setSelectedLocation(null);
      }
      await loadLocations();
    } catch {
      setMessage({ type: "error", text: "Failed to delete location." });
    }
  };

  const handleSimulateCheckIn = async (checkInType: "MANUAL" | "GEOFENCE_ENTER" | "GEOFENCE_EXIT") => {
    if (!selectedLocation) return;
    setActionLoading(true);
    try {
      const result = await locationContextApi.recordCheckIn({
        location_id: selectedLocation.id,
        check_in_type: checkInType,
        notes: `Simulated ${checkInType} from web dashboard`,
      });
      setMessage({
        type: "success",
        text: `Recorded check-in '${result.check_in_type}' at ${result.location_name}!`,
      });
      // Refresh recommendations
      const recs = await locationContextApi.getLocationRecommendations({
        location_id: selectedLocation.id,
        trigger_type: checkInType === "GEOFENCE_EXIT" ? "DEPARTURE" : "ARRIVAL",
      });
      setReminders(recs.reminders || []);
    } catch {
      setMessage({ type: "error", text: "Failed to record check-in." });
    } finally {
      setActionLoading(false);
    }
  };

  const getLocationIcon = (type: string) => {
    switch (type.toUpperCase()) {
      case "CAMPUS":
        return <GraduationCap className="h-4 w-4 text-emerald-500" />;
      case "LIBRARY":
        return <Compass className="h-4 w-4 text-indigo-500" />;
      case "LABORATORY":
        return <Zap className="h-4 w-4 text-amber-500" />;
      case "OFFICE":
      case "WORK":
        return <Building className="h-4 w-4 text-blue-500" />;
      case "HOME":
        return <Home className="h-4 w-4 text-purple-500" />;
      default:
        return <MapPin className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Alert Banner */}
      {message && (
        <div
          className={`p-3.5 rounded-xl text-xs flex items-center justify-between border ${
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400"
              : "bg-red-500/10 border-red-500/20 text-red-700 dark:text-red-400"
          }`}
        >
          <div className="flex items-center gap-2">
            {message.type === "success" ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="font-bold opacity-60 hover:opacity-100">
            ✕
          </button>
        </div>
      )}

      {/* Privacy Guardrails Banner */}
      <Card className="border-emerald-500/20 bg-emerald-50/20 dark:bg-emerald-950/20">
        <CardContent className="p-4 flex items-start gap-3">
          <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-foreground">Anti-Surveillance Privacy Guardrails</p>
            <p className="text-muted-foreground leading-relaxed">
              ContextIQ <strong>never</strong> records continuous GPS breadcrumbs or location history. The mobile companion performs coarse edge boundary detection and transmits only discrete transition events (e.g. <em>location_entered</em> or <em>location_exited</em>). You can toggle manual check-in mode or disable location reminders at any time.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Main Layout Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Saved Places List */}
        <Card className="border-border lg:col-span-1 shadow-xs">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <div className="space-y-0.5">
              <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                <MapPin className="h-4 w-4 text-indigo-500" />
                Saved Places & Geofences
              </CardTitle>
              <CardDescription className="text-xs">
                {(locations || []).length} configured places
              </CardDescription>
            </div>
            <Button
              size="sm"
              onClick={() => setShowCreateModal(true)}
              className="text-xs gap-1 h-8 bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Place
            </Button>
          </CardHeader>

          <CardContent className="space-y-2 pt-1">
            {loading ? (
              <div className="p-4 text-xs text-muted-foreground text-center animate-pulse">
                Loading saved places...
              </div>
            ) : (locations || []).length === 0 ? (
              <div className="p-4 rounded-xl border border-dashed border-border text-xs text-muted-foreground text-center">
                No locations configured yet. Add your campus, office, or library to activate smart reminders.
              </div>
            ) : (
              (locations || []).map((loc) => {
                const isSelected = selectedLocation?.id === loc.id;
                return (
                  <div
                    key={loc.id}
                    onClick={() => setSelectedLocation(loc)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all text-xs flex items-center justify-between ${
                      isSelected
                        ? "border-indigo-500/50 bg-indigo-50/30 dark:bg-indigo-950/30 shadow-xs"
                        : "border-border/60 hover:border-border hover:bg-muted/30"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                        {getLocationIcon(loc.location_type)}
                      </div>
                      <div>
                        <span className="font-semibold text-foreground block">{loc.name}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {loc.location_type} • {loc.radius_meters || 150}m geofence
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {loc.reminders_enabled ? (
                        <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px] text-muted-foreground">
                          Muted
                        </Badge>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        {/* Right Column: Selected Place Detail, Reminders & Simulator */}
        <div className="space-y-6 lg:col-span-2">
          {selectedLocation ? (
            <>
              {/* Place Detail Card */}
              <Card className="border-border shadow-xs">
                <CardHeader className="pb-3 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-muted flex items-center justify-center">
                      {getLocationIcon(selectedLocation.location_type)}
                    </div>
                    <div>
                      <CardTitle className="text-base font-bold text-foreground">
                        {selectedLocation.name}
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Category: {selectedLocation.location_type} • Radius: {selectedLocation.radius_meters || 150} meters
                      </CardDescription>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 gap-1 h-8"
                      onClick={() => handleDeleteLocation(selectedLocation.id, selectedLocation.name)}
                    >
                      <Trash2 className="h-3 w-3" />
                      Delete
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4 pt-1">
                  {/* Discrete Check-In Simulation Bar */}
                  <div className="p-3.5 rounded-xl bg-muted/40 border border-border/50 space-y-2 text-xs">
                    <span className="font-semibold text-foreground block">Discrete Boundary Testing & Manual Check-In</span>
                    <p className="text-[11px] text-muted-foreground">
                      Simulate native edge geofence transitions without physical GPS tracking.
                    </p>
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs gap-1.5 h-8 font-medium"
                        onClick={() => handleSimulateCheckIn("GEOFENCE_ENTER")}
                        disabled={actionLoading}
                      >
                        <MapPin className="h-3 w-3 text-emerald-500" />
                        Simulate Arrival (Enter)
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs gap-1.5 h-8 font-medium"
                        onClick={() => handleSimulateCheckIn("GEOFENCE_EXIT")}
                        disabled={actionLoading}
                      >
                        <ArrowRight className="h-3 w-3 text-amber-500" />
                        Simulate Departure (Exit)
                      </Button>
                      <Button
                        size="sm"
                        className="text-xs gap-1.5 h-8 font-medium bg-indigo-600 hover:bg-indigo-700 text-white"
                        onClick={() => handleSimulateCheckIn("MANUAL")}
                        disabled={actionLoading}
                      >
                        Manual Check-In Here
                      </Button>
                    </div>
                  </div>

                  {/* Contextual Smart Reminders */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <Bell className="h-3.5 w-3.5 text-indigo-500" />
                      Contextual Reminders Associated with {selectedLocation.name}
                    </h4>

                    {reminders.length === 0 ? (
                      <div className="p-3.5 rounded-xl border border-dashed border-border text-xs text-muted-foreground text-center">
                        No pending tasks associated with this location. Create tasks tagged with &quot;{selectedLocation.name}&quot; to trigger smart reminders.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {reminders.map((rem, idx) => (
                          <div
                            key={idx}
                            className={`p-3 rounded-xl border text-xs flex items-start justify-between gap-3 ${
                              rem.trigger_type === "DEPARTURE"
                                ? "border-amber-500/20 bg-amber-50/20 dark:bg-amber-950/20"
                                : "border-emerald-500/20 bg-emerald-50/20 dark:bg-emerald-950/20"
                            }`}
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-foreground">{rem.title}</span>
                                <Badge
                                  variant="outline"
                                  className={`text-[10px] ${
                                    rem.trigger_type === "DEPARTURE"
                                      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30"
                                      : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                                  }`}
                                >
                                  {rem.trigger_type === "DEPARTURE" ? "Before Leaving" : "Upon Arrival"}
                                </Badge>
                              </div>
                              <p className="text-[11px] text-muted-foreground">{rem.message}</p>
                            </div>

                            <Badge variant="outline" className="text-[10px] bg-muted font-mono shrink-0">
                              {rem.association_source} ({Math.round(rem.confidence_score * 100)}%)
                            </Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="p-8 rounded-xl border border-dashed border-border text-center text-xs text-muted-foreground">
              Select a location on the left or add a new place to inspect contextual triggers.
            </div>
          )}

          {/* Privacy & Location Consent Settings */}
          <Card className="border-border shadow-xs">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Shield className="h-4 w-4 text-emerald-500" />
                Location Privacy & Consent Preferences
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs pt-1">
              <div className="flex items-center justify-between p-2.5 rounded-lg border border-border/50 bg-card">
                <div>
                  <span className="font-semibold text-foreground block">Location-Aware Recommendations</span>
                  <span className="text-[11px] text-muted-foreground">Enable contextual task reminders based on your current physical environment.</span>
                </div>
                <input
                  type="checkbox"
                  checked={locationEnabled}
                  onChange={(e) => setLocationEnabled(e.target.checked)}
                  className="rounded border-border text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                />
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg border border-border/50 bg-card">
                <div>
                  <span className="font-semibold text-foreground block">Edge Circular Geofencing</span>
                  <span className="text-[11px] text-muted-foreground">Allow mobile operating system to monitor coarse 150m circular boundaries locally.</span>
                </div>
                <input
                  type="checkbox"
                  checked={geofencingEnabled}
                  onChange={(e) => setGeofencingEnabled(e.target.checked)}
                  className="rounded border-border text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Create Location Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Card className="w-full max-w-md border-border bg-card shadow-xl">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold text-foreground">Add Contextual Location</CardTitle>
              <CardDescription className="text-xs">
                Configure a named place for contextual task associations and arrival/departure reminders.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateLocation} className="space-y-3 text-xs">
                <div>
                  <label className="font-semibold text-foreground block mb-1">Place Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Stanford Green Library, Home Desk, Bio Lab"
                    value={newLocName}
                    onChange={(e) => setNewLocName(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background p-2 text-foreground text-xs"
                  />
                </div>

                <div>
                  <label className="font-semibold text-foreground block mb-1">Category</label>
                  <select
                    value={newLocType}
                    onChange={(e) => setNewLocType(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background p-2 text-foreground text-xs"
                  >
                    <option value="CAMPUS">Campus</option>
                    <option value="LIBRARY">Library</option>
                    <option value="LABORATORY">Laboratory</option>
                    <option value="OFFICE">Office</option>
                    <option value="HOME">Home</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>

                <div>
                  <label className="font-semibold text-foreground block mb-1">Geofence Radius (meters)</label>
                  <input
                    type="number"
                    min={50}
                    max={2000}
                    value={newRadius}
                    onChange={(e) => setNewRadius(Number(e.target.value))}
                    className="w-full rounded-lg border border-border bg-background p-2 text-foreground text-xs font-mono"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-xs"
                    onClick={() => setShowCreateModal(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={actionLoading}
                    className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                  >
                    {actionLoading ? "Saving..." : "Save Place"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

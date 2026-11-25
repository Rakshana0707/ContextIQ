/**
 * Mobile Location Capabilities Service (Phase 5.6 Task 7).
 *
 * Invariant:
 * - Uses foreground or user-initiated location checks only.
 * - Zero continuous background battery drain by default.
 * - Compares current GPS coordinates against user's saved workplace locations.
 */

import { apiClient } from './apiClient';

let expoLocation: any = null;
try {
  expoLocation = require('expo-location');
} catch {
  expoLocation = null;
}

export interface ContextualLocation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  radius_meters: number;
  is_active: boolean;
}

export interface ProximityMatch {
  location: ContextualLocation;
  distanceMeters: number;
  isWithinGeofence: boolean;
}

/**
 * Calculates distance in meters between two GPS coordinates using Haversine formula.
 */
export function calculateHaversineDistanceMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

export const locationService = {
  /**
   * Requests foreground-only location permission from user.
   */
  async requestForegroundPermissions(): Promise<boolean> {
    if (expoLocation && typeof expoLocation.requestForegroundPermissionsAsync === 'function') {
      const { status } = await expoLocation.requestForegroundPermissionsAsync();
      return status === 'granted';
    }
    return false;
  },

  /**
   * Captures a single current location fix (user-initiated / on foreground resume).
   */
  async getCurrentPosition(): Promise<{ latitude: number; longitude: number } | null> {
    if (expoLocation && typeof expoLocation.getCurrentPositionAsync === 'function') {
      try {
        const loc = await expoLocation.getCurrentPositionAsync({
          accuracy: expoLocation.Accuracy.Balanced,
        });
        return {
          latitude: loc.coords.latitude,
          longitude: loc.coords.longitude,
        };
      } catch {
        return null;
      }
    }
    return null;
  },

  /**
   * Checks whether current user position matches any designated workplace geofence.
   */
  async checkContextualProximity(
    currentLat: number,
    currentLon: number
  ): Promise<ProximityMatch[]> {
    try {
      const response = await apiClient.get<ContextualLocation[]>('/locations?active_only=true');
      const locations = response.data || [];

      return locations.map(loc => {
        const distance = calculateHaversineDistanceMeters(
          currentLat,
          currentLon,
          loc.latitude,
          loc.longitude
        );
        return {
          location: loc,
          distanceMeters: distance,
          isWithinGeofence: distance <= (loc.radius_meters || 150),
        };
      });
    } catch {
      return [];
    }
  },

  /**
   * Fetches user-defined contextual locations from /context/locations.
   */
  async getLocations(activeOnly = true): Promise<ContextualLocation[]> {
    try {
      const response = await apiClient.get<ContextualLocation[]>(`/context/locations?active_only=${activeOnly}`);
      return response.data || [];
    } catch {
      return [];
    }
  },

  /**
   * Creates a new user-defined location.
   */
  async createLocation(payload: Partial<ContextualLocation>): Promise<ContextualLocation | null> {
    try {
      const response = await apiClient.post<ContextualLocation>('/context/locations', payload);
      return response.data || null;
    } catch {
      return null;
    }
  },

  /**
   * Deletes a user-defined location.
   */
  async deleteLocation(locationId: string): Promise<boolean> {
    try {
      await apiClient.delete(`/context/locations/${locationId}`);
      return true;
    } catch {
      return false;
    }
  },

  /**
   * Records a discrete manual check-in or geofence boundary event.
   */
  async recordCheckIn(
    locationId: string | null,
    checkInType: 'MANUAL' | 'GEOFENCE_ENTER' | 'GEOFENCE_EXIT' = 'MANUAL',
    notes?: string
  ): Promise<any> {
    try {
      const response = await apiClient.post('/context/check-ins', {
        location_id: locationId,
        check_in_type: checkInType,
        notes,
        occurred_at: new Date().toISOString(),
      });
      return response.data || null;
    } catch {
      return null;
    }
  },

  /**
   * Fetches smart contextual reminders for a location and transition type.
   */
  async getLocationRecommendations(
    locationId?: string,
    triggerType: 'ARRIVAL' | 'DEPARTURE' | 'MANUAL' = 'ARRIVAL'
  ): Promise<any> {
    try {
      const params = new URLSearchParams({ trigger_type: triggerType });
      if (locationId) params.append('location_id', locationId);
      const response = await apiClient.get(`/context/location-recommendations?${params.toString()}`);
      return response.data || null;
    } catch {
      return null;
    }
  },
};

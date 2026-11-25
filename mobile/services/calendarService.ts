/**
 * Mobile Calendar Service (Phase 5.6).
 * Retrieves synchronized external calendar events, focus intervals, and recovery buffers.
 */

import { apiClient } from './apiClient';
import { getCachedData, setCachedData, CACHE_KEYS } from '../storage/offlineCache';

export interface MobileBusyBlock {
  title: string;
  start_time: string;
  end_time: string;
  source: string;
  is_recovery_buffer: boolean;
}

export interface MobileFocusWindow {
  start_time: string;
  end_time: string;
  duration_minutes: number;
  focus_quality_score: number;
  is_peak_focus: boolean;
}

export interface MobileCalendarSummary {
  horizon_start: string;
  horizon_end: string;
  total_available_minutes: number;
  busy_blocks: MobileBusyBlock[];
  available_windows: MobileFocusWindow[];
}

export const calendarService = {
  async getCalendarSummary(horizonDays: number = 3): Promise<MobileCalendarSummary> {
    try {
      const response = await apiClient.get<MobileCalendarSummary>(
        `/scheduling/availability?horizon_days=${horizonDays}`
      );
      const data = response.data;
      await setCachedData(CACHE_KEYS.CALENDAR_EVENTS, data);
      return data;
    } catch {
      const cached = await getCachedData<MobileCalendarSummary>(CACHE_KEYS.CALENDAR_EVENTS);
      if (cached) return cached;
      return {
        horizon_start: new Date().toISOString(),
        horizon_end: new Date(Date.now() + horizonDays * 86400000).toISOString(),
        total_available_minutes: 0,
        busy_blocks: [],
        available_windows: [],
      };
    }
  },
};

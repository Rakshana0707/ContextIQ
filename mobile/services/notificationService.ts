/**
 * Mobile Notification Intelligence Service (Phase 5.6 Task 6).
 * Manages authorized push alerts, quiet hours, cognitive suppression, and deep links.
 */

import { apiClient } from './apiClient';
import { getCachedData, setCachedData, CACHE_KEYS } from '../storage/offlineCache';

let expoNotifications: any = null;
try {
  expoNotifications = require('expo-notifications');
} catch {
  expoNotifications = null;
}

export interface MobileNotification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  category: 'TASK_REMINDER' | 'FOCUS_SHIELD' | 'BREAK_PROMPT' | 'BEHAVIORAL_NUDGE' | 'SYSTEM';
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  is_read: boolean;
  is_dismissed: boolean;
  deep_link?: string | null;
  created_at: string;
}

export interface NotificationPreferences {
  quiet_hours_enabled: boolean;
  quiet_hours_start: string; // e.g. "22:00"
  quiet_hours_end: string;   // e.g. "08:00"
  allow_critical_during_quiet: boolean;
  max_notifications_per_day: number;
}

export const notificationService = {
  /**
   * Requests OS notification permissions on Android and iOS.
   */
  async requestNotificationPermissions(): Promise<boolean> {
    if (expoNotifications && typeof expoNotifications.requestPermissionsAsync === 'function') {
      const { status } = await expoNotifications.requestPermissionsAsync();
      return status === 'granted';
    }
    return true;
  },

  /**
   * Retrieves user notification history from Notification Intelligence Manager.
   */
  async getNotifications(unreadOnly: boolean = false): Promise<MobileNotification[]> {
    try {
      const response = await apiClient.get<MobileNotification[]>(
        `/adaptive/notifications?unread_only=${unreadOnly}&limit=30`
      );
      const items = response.data;
      await setCachedData(CACHE_KEYS.NOTIFICATIONS, items);
      return items;
    } catch {
      const cached = await getCachedData<MobileNotification[]>(CACHE_KEYS.NOTIFICATIONS);
      return cached || [];
    }
  },

  /**
   * Fetches user quiet hours and suppression preferences.
   */
  async getPreferences(): Promise<NotificationPreferences> {
    try {
      const response = await apiClient.get<any>('/adaptive/notifications/preferences');
      return {
        quiet_hours_enabled: response.data.quiet_hours_enabled ?? true,
        quiet_hours_start: response.data.quiet_hours_start ?? '22:00',
        quiet_hours_end: response.data.quiet_hours_end ?? '08:00',
        allow_critical_during_quiet: response.data.allow_critical_during_quiet ?? true,
        max_notifications_per_day: response.data.max_notifications_per_day ?? 12,
      };
    } catch {
      return {
        quiet_hours_enabled: true,
        quiet_hours_start: '22:00',
        quiet_hours_end: '08:00',
        allow_critical_during_quiet: true,
        max_notifications_per_day: 12,
      };
    }
  },

  /**
   * Updates notification preferences and quiet hours.
   */
  async updatePreferences(prefs: Partial<NotificationPreferences>): Promise<NotificationPreferences> {
    const response = await apiClient.post<any>('/adaptive/notifications/preferences', prefs);
    return response.data;
  },

  /**
   * Acknowledges / marks a notification as read.
   */
  async acknowledgeNotification(notificationId: string): Promise<void> {
    await apiClient.post(`/adaptive/notifications/${notificationId}/acknowledge`);
    const cached = await getCachedData<MobileNotification[]>(CACHE_KEYS.NOTIFICATIONS);
    if (cached) {
      const updated = cached.map(n => (n.id === notificationId ? { ...n, is_read: true } : n));
      await setCachedData(CACHE_KEYS.NOTIFICATIONS, updated);
    }
  },

  /**
   * Dismisses a notification and updates cognitive fatigue score.
   */
  async dismissNotification(notificationId: string): Promise<void> {
    await apiClient.post(`/adaptive/notifications/${notificationId}/dismiss`, { annoyance_level: 1 });
    const cached = await getCachedData<MobileNotification[]>(CACHE_KEYS.NOTIFICATIONS);
    if (cached) {
      const updated = cached.map(n => (n.id === notificationId ? { ...n, is_dismissed: true } : n));
      await setCachedData(CACHE_KEYS.NOTIFICATIONS, updated);
    }
  },

  /**
   * Evaluates if current time falls within user quiet hours.
   */
  isQuietHoursActive(prefs: NotificationPreferences, now: Date = new Date()): boolean {
    if (!prefs.quiet_hours_enabled) return false;

    const [startH, startM] = prefs.quiet_hours_start.split(':').map(Number);
    const [endH, endM] = prefs.quiet_hours_end.split(':').map(Number);

    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    const startMinutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;

    if (startMinutes > endMinutes) {
      // Overnight quiet hours (e.g. 22:00 to 08:00)
      return currentMinutes >= startMinutes || currentMinutes < endMinutes;
    }
    return currentMinutes >= startMinutes && currentMinutes < endMinutes;
  },
};

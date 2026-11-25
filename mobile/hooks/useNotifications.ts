/**
 * Notification Management Hook for ContextIQ Mobile (Phase 5.6).
 */

import { useState, useEffect, useCallback } from 'react';
import {
  notificationService,
  MobileNotification,
  NotificationPreferences,
} from '../services/notificationService';

export function useNotifications() {
  const [notifications, setNotifications] = useState<MobileNotification[]>([]);
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [notifs, prefs] = await Promise.all([
        notificationService.getNotifications(),
        notificationService.getPreferences(),
      ]);
      setNotifications(notifs);
      setPreferences(prefs);
    } catch (err: any) {
      setError(err.message || 'Failed to load notifications');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const acknowledge = useCallback(async (id: string) => {
    try {
      await notificationService.acknowledgeNotification(id);
      setNotifications(prev => prev.map(n => (n.id === id ? { ...n, is_read: true } : n)));
    } catch (err: any) {
      setError(err.message || 'Acknowledge failed');
    }
  }, []);

  const dismiss = useCallback(async (id: string) => {
    try {
      await notificationService.dismissNotification(id);
      setNotifications(prev => prev.map(n => (n.id === id ? { ...n, is_dismissed: true } : n)));
    } catch (err: any) {
      setError(err.message || 'Dismiss failed');
    }
  }, []);

  const updateQuietHours = useCallback(async (enabled: boolean, start?: string, end?: string) => {
    try {
      const updated = await notificationService.updatePreferences({
        quiet_hours_enabled: enabled,
        quiet_hours_start: start || '22:00',
        quiet_hours_end: end || '08:00',
      });
      setPreferences(updated);
    } catch (err: any) {
      setError(err.message || 'Update quiet hours failed');
    }
  }, []);

  const unreadCount = notifications.filter(n => !n.is_read && !n.is_dismissed).length;

  return {
    notifications,
    preferences,
    unreadCount,
    isLoading,
    error,
    refreshNotifications: loadData,
    acknowledge,
    dismiss,
    updateQuietHours,
  };
}

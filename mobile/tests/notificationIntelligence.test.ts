import './setup';
import { notificationService, NotificationPreferences } from '../services/notificationService';

describe('Notification Intelligence & Cognitive Shielding (Phase 5.6 Task 6)', () => {
  test('evaluates quiet hours boundary correctly for overnight intervals', () => {
    const prefs: NotificationPreferences = {
      quiet_hours_enabled: true,
      quiet_hours_start: '22:00',
      quiet_hours_end: '08:00',
      allow_critical_during_quiet: true,
      max_notifications_per_day: 10,
    };

    // 23:30 is within quiet hours
    const lateNight = new Date(2026, 10, 24, 23, 30);
    expect(notificationService.isQuietHoursActive(prefs, lateNight)).toBe(true);

    // 04:15 is within quiet hours
    const earlyMorning = new Date(2026, 10, 24, 4, 15);
    expect(notificationService.isQuietHoursActive(prefs, earlyMorning)).toBe(true);

    // 14:00 is outside quiet hours
    const afternoon = new Date(2026, 10, 24, 14, 0);
    expect(notificationService.isQuietHoursActive(prefs, afternoon)).toBe(false);
  });

  test('respects quiet hours toggle when disabled', () => {
    const prefs: NotificationPreferences = {
      quiet_hours_enabled: false,
      quiet_hours_start: '22:00',
      quiet_hours_end: '08:00',
      allow_critical_during_quiet: true,
      max_notifications_per_day: 10,
    };

    const lateNight = new Date(2026, 10, 24, 23, 30);
    expect(notificationService.isQuietHoursActive(prefs, lateNight)).toBe(false);
  });

  test('acknowledges and marks notification as read', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        id: 'notif-1',
        is_read: true,
        message: 'Notification acknowledged.',
      }),
    });

    await expect(notificationService.acknowledgeNotification('notif-1')).resolves.not.toThrow();
  });
});

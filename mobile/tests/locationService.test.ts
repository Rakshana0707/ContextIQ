import './setup';
import {
  calculateHaversineDistanceMeters,
  locationService,
} from '../services/locationService';

describe('Location Capabilities & Workplace Geofencing (Phase 5.6 Task 7)', () => {
  test('calculates accurate Haversine distance between coordinates', () => {
    // Distance between Empire State Building (40.7484, -73.9857) and Chrysler Building (40.7516, -73.9755) is ~920m
    const distance = calculateHaversineDistanceMeters(40.7484, -73.9857, 40.7516, -73.9755);
    expect(distance).toBeGreaterThan(850);
    expect(distance).toBeLessThan(1000);

    // Identical coordinates should yield 0 meters
    const zeroDistance = calculateHaversineDistanceMeters(37.7749, -122.4194, 37.7749, -122.4194);
    expect(zeroDistance).toBe(0);
  });

  test('checks contextual proximity against active workplace locations', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [
        {
          id: 'loc-hq',
          name: 'Main Engineering HQ',
          latitude: 37.7749,
          longitude: -122.4194,
          radius_meters: 150,
          is_active: true,
        },
      ],
    });

    // Device is 30 meters away from HQ
    const matches = await locationService.checkContextualProximity(37.7751, -122.4194);
    expect(matches.length).toBe(1);
    expect(matches[0].location.name).toBe('Main Engineering HQ');
    expect(matches[0].isWithinGeofence).toBe(true);
  });

  test('records manual and geofence check-ins (Phase 5.8)', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({
        id: 'cin-123',
        location_id: 'loc-library',
        location_name: 'Campus Library',
        check_in_type: 'GEOFENCE_ENTER',
        occurred_at: '2026-11-24T15:00:00Z',
      }),
    });

    const checkin = await locationService.recordCheckIn('loc-library', 'GEOFENCE_ENTER');
    expect(checkin).toBeDefined();
    expect(checkin.check_in_type).toBe('GEOFENCE_ENTER');
  });

  test('retrieves smart location recommendations and departure reminders (Phase 5.8)', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        location_id: 'loc-office',
        location_name: 'Tech Office',
        trigger_type: 'DEPARTURE',
        reminders: [
          {
            title: 'Review pull request before leaving',
            message: "Before leaving Tech Office: 'Review pull request before leaving' is still pending.",
            recommendation_arm: 'arm_3_one_more_thing',
          },
        ],
        total_reminders: 1,
      }),
    });

    const recs = await locationService.getLocationRecommendations('loc-office', 'DEPARTURE');
    expect(recs).toBeDefined();
    expect(recs.total_reminders).toBe(1);
    expect(recs.reminders[0].recommendation_arm).toBe('arm_3_one_more_thing');
  });
});


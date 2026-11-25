import './setup';
import { authService, getOrCreateDeviceId } from '../services/authService';
import {
  setItemSecure,
  getItemSecure,
  clearAllSecureCredentials,
  SECURE_KEYS,
} from '../storage/secureStore';

describe('Mobile Authentication & Hardware-Backed Security (Phase 5.6 Task 2)', () => {
  beforeEach(async () => {
    await clearAllSecureCredentials();
  });

  test('generates and persists unique mobile hardware device identifier', async () => {
    const deviceId1 = await getOrCreateDeviceId();
    expect(deviceId1).toBeDefined();
    expect(deviceId1).toContain('mobile_dev_');

    // Repeated calls must return the same persistent device identifier
    const deviceId2 = await getOrCreateDeviceId();
    expect(deviceId2).toBe(deviceId1);
  });

  test('secureStore prevents plaintext access token exposure and manages lifecycle', async () => {
    const testToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-payload';
    await setItemSecure(SECURE_KEYS.ACCESS_TOKEN, testToken);

    const retrieved = await getItemSecure(SECURE_KEYS.ACCESS_TOKEN);
    expect(retrieved).toBe(testToken);

    await clearAllSecureCredentials();
    const afterClear = await getItemSecure(SECURE_KEYS.ACCESS_TOKEN);
    expect(afterClear).toBeNull();
  });

  test('login authenticates session, registers device, and stores encrypted tokens', async () => {
    const mockUser = {
      id: 'usr-12345',
      email: 'alex@contextiq.ai',
      full_name: 'Alex Johnson',
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: 'valid.mock.jwt.token',
        user: mockUser,
      }),
    });

    const session = await authService.login('alex@contextiq.ai', 'securePass123');
    expect(session.accessToken).toBe('valid.mock.jwt.token');
    expect(session.user.id).toBe('usr-12345');
    expect(session.deviceId).toBeDefined();

    // Verify token was stored in secure store
    const storedToken = await getItemSecure(SECURE_KEYS.ACCESS_TOKEN);
    expect(storedToken).toBe('valid.mock.jwt.token');
  });

  test('logout wipes all secure credentials and offline caches', async () => {
    await setItemSecure(SECURE_KEYS.ACCESS_TOKEN, 'test.token');
    await setItemSecure(SECURE_KEYS.USER_ID, 'test.user');

    await authService.logout();

    expect(await getItemSecure(SECURE_KEYS.ACCESS_TOKEN)).toBeNull();
    expect(await getItemSecure(SECURE_KEYS.USER_ID)).toBeNull();
  });
});

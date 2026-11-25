/**
 * Authentication & Device Identity Service for ContextIQ Mobile (Phase 5.6 Task 2).
 */

import { apiClient } from './apiClient';
import {
  setItemSecure,
  getItemSecure,
  deleteItemSecure,
  clearAllSecureCredentials,
  SECURE_KEYS,
} from '../storage/secureStore';
import { clearAllCachedData } from '../storage/offlineCache';
import { clearOfflineQueue } from '../storage/offlineQueue';

export interface MobileUser {
  id: string;
  email: string;
  full_name?: string | null;
  cognitive_profile?: any;
  created_at?: string;
}

export interface AuthSession {
  accessToken: string;
  user: MobileUser;
  deviceId: string;
}

/**
 * Generates or retrieves a persistent mobile device hardware identifier.
 */
export async function getOrCreateDeviceId(): Promise<string> {
  let deviceId = await getItemSecure(SECURE_KEYS.DEVICE_ID);
  if (!deviceId) {
    // Generate UUID-shaped mobile hardware identifier
    deviceId = `mobile_dev_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 10)}`;
    await setItemSecure(SECURE_KEYS.DEVICE_ID, deviceId);
  }
  return deviceId;
}

export const authService = {
  /**
   * Authenticates user against backend and saves encrypted session credentials.
   */
  async login(email: string, password: string = 'password123'): Promise<AuthSession> {
    const deviceId = await getOrCreateDeviceId();

    const response = await apiClient.post<any>('/users/login', {
      email,
      password,
    });

    const { access_token, user } = response.data;

    // Securely persist credentials
    await setItemSecure(SECURE_KEYS.ACCESS_TOKEN, access_token);
    await setItemSecure(SECURE_KEYS.USER_ID, user.id);

    // Register mobile device consent
    try {
      await apiClient.post('/privacy/consent', {
        device_id: deviceId,
        capture_active_window: true,
        capture_url: false,
        capture_idle_duration: true,
      });
    } catch {
      // Non-fatal if privacy consent endpoint is already configured
    }

    return {
      accessToken: access_token,
      user,
      deviceId,
    };
  },

  /**
   * Registers a new account with default cognitive parameters.
   */
  async register(email: string, password: string, fullName: string): Promise<AuthSession> {
    const deviceId = await getOrCreateDeviceId();

    const response = await apiClient.post<any>('/users/signup', {
      email,
      password,
      full_name: fullName,
      initial_tasks: [
        {
          title: 'Explore ContextIQ Mobile Companion',
          priority: 'HIGH',
          estimated_duration_minutes: 15,
        },
      ],
    });

    const { access_token, user } = response.data;

    await setItemSecure(SECURE_KEYS.ACCESS_TOKEN, access_token);
    await setItemSecure(SECURE_KEYS.USER_ID, user.id);

    return {
      accessToken: access_token,
      user,
      deviceId,
    };
  },

  /**
   * Checks current stored session validity.
   */
  async getCurrentSession(): Promise<AuthSession | null> {
    const token = await getItemSecure(SECURE_KEYS.ACCESS_TOKEN);
    const userId = await getItemSecure(SECURE_KEYS.USER_ID);
    const deviceId = await getOrCreateDeviceId();

    if (!token || !userId) {
      return null;
    }

    try {
      const resp = await apiClient.get<MobileUser>('/users/me');
      return {
        accessToken: token,
        user: resp.data,
        deviceId,
      };
    } catch {
      // Invalid/expired token
      await clearAllSecureCredentials();
      return null;
    }
  },

  /**
   * Securely logs out, wipes hardware-backed tokens and offline cache.
   */
  async logout(): Promise<void> {
    await clearAllSecureCredentials();
    await clearAllCachedData();
    await clearOfflineQueue();
  },
};

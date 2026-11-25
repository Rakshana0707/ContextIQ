/**
 * ContextIQ Mobile Central API Client (Phase 5.6).
 * Handles authentication header injection, device identification,
 * session refresh, and automatic offline fallback.
 */

import { getItemSecure, SECURE_KEYS, deleteItemSecure } from '../storage/secureStore';
import { enqueueOfflineAction } from '../storage/offlineQueue';

// Configurable backend API base endpoint
let customBaseUrl: string | null = null;

export function setApiBaseUrl(url: string) {
  customBaseUrl = url.replace(/\/+$/, '');
}

export function getApiBaseUrl(): string {
  if (customBaseUrl) return customBaseUrl;
  // Default to localhost for testing, or Android emulator host if on Android
  return 'http://10.0.2.2:8000/api/v1';
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  fromCache?: boolean;
}

let onSessionExpiredCallback: (() => void) | null = null;

export function registerSessionExpiredHandler(cb: () => void) {
  onSessionExpiredCallback = cb;
}

export const apiClient = {
  async request<T>(
    endpoint: string,
    options: {
      method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
      body?: any;
      headers?: Record<string, string>;
      offlineActionType?: any;
    } = {}
  ): Promise<ApiResponse<T>> {
    const method = options.method || 'GET';
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = `${getApiBaseUrl()}${cleanEndpoint}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options.headers,
    };

    // 1. Inject Bearer Access Token
    const token = await getItemSecure(SECURE_KEYS.ACCESS_TOKEN);
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // 2. Inject Device Identification Header
    const deviceId = await getItemSecure(SECURE_KEYS.DEVICE_ID);
    if (deviceId) {
      headers['X-Device-ID'] = deviceId;
    }

    // 3. User isolation header for development mode compatibility
    const userId = await getItemSecure(SECURE_KEYS.USER_ID);
    if (userId) {
      headers['X-User-Id'] = userId;
    }

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });

      // Handle 401 Session Expiration
      if (response.status === 401) {
        await deleteItemSecure(SECURE_KEYS.ACCESS_TOKEN);
        if (onSessionExpiredCallback) {
          onSessionExpiredCallback();
        }
        throw new Error('Session expired. Please log in again.');
      }

      if (!response.ok) {
        let errorDetail = `HTTP ${response.status} Error`;
        try {
          const errJson = await response.json();
          errorDetail = errJson.detail || errJson.message || errorDetail;
        } catch {
          // Response was not JSON
        }
        throw new Error(errorDetail);
      }

      let data: T;
      if (response.status === 204) {
        data = {} as T;
      } else {
        data = await response.json();
      }

      return {
        data,
        status: response.status,
      };
    } catch (networkError: any) {
      // Offline fallback: if write mutation and offlineActionType provided, enqueue action
      if (options.offlineActionType && method !== 'GET') {
        await enqueueOfflineAction(
          options.offlineActionType,
          cleanEndpoint,
          method,
          options.body
        );
      }
      throw networkError;
    }
  },

  async get<T>(endpoint: string, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET', headers });
  },

  async post<T>(endpoint: string, body?: any, offlineActionType?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'POST', body, offlineActionType });
  },

  async patch<T>(endpoint: string, body?: any, offlineActionType?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'PATCH', body, offlineActionType });
  },

  async put<T>(endpoint: string, body?: any, offlineActionType?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'PUT', body, offlineActionType });
  },

  async delete<T>(endpoint: string, offlineActionType?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE', offlineActionType });
  },
};

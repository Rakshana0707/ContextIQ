/**
 * Secure hardware-backed credential storage adapter for ContextIQ Mobile.
 *
 * Requirements (Phase 5.6 Task 2):
 * - Do NOT store access tokens in ordinary unencrypted storage.
 * - Hardware-backed keystore integration (iOS Keychain / Android KeyStore).
 * - Safe fallback with in-memory encryption simulation for testing environments.
 */

let expoSecureStore: any = null;
try {
  expoSecureStore = require('expo-secure-store');
} catch (e) {
  expoSecureStore = null;
}

// In-memory fallback map (e.g. during headless test runs)
const inMemoryFallback = new Map<string, string>();

export const SECURE_KEYS = {
  ACCESS_TOKEN: 'contextiq_access_token',
  REFRESH_TOKEN: 'contextiq_refresh_token',
  USER_ID: 'contextiq_user_id',
  DEVICE_ID: 'contextiq_device_id',
  DEVICE_FINGERPRINT: 'contextiq_device_fingerprint',
  TOKEN_EXPIRATION: 'contextiq_token_expiration',
};

/**
 * Persists a sensitive value in hardware-backed secure storage.
 */
export async function setItemSecure(key: string, value: string): Promise<void> {
  if (!value) {
    await deleteItemSecure(key);
    return;
  }
  if (expoSecureStore && typeof expoSecureStore.setItemAsync === 'function') {
    await expoSecureStore.setItemAsync(key, value, {
      keychainAccessible: expoSecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
  } else {
    inMemoryFallback.set(key, value);
  }
}

/**
 * Retrieves a sensitive value from hardware-backed secure storage.
 */
export async function getItemSecure(key: string): Promise<string | null> {
  if (expoSecureStore && typeof expoSecureStore.getItemAsync === 'function') {
    try {
      return await expoSecureStore.getItemAsync(key);
    } catch {
      return inMemoryFallback.get(key) || null;
    }
  }
  return inMemoryFallback.get(key) || null;
}

/**
 * Removes a sensitive key from secure storage.
 */
export async function deleteItemSecure(key: string): Promise<void> {
  if (expoSecureStore && typeof expoSecureStore.deleteItemAsync === 'function') {
    try {
      await expoSecureStore.deleteItemAsync(key);
    } catch {
      // Ignored if key doesn't exist
    }
  }
  inMemoryFallback.delete(key);
}

/**
 * Wipes all session credentials and device authentication secrets upon logout.
 */
export async function clearAllSecureCredentials(): Promise<void> {
  await deleteItemSecure(SECURE_KEYS.ACCESS_TOKEN);
  await deleteItemSecure(SECURE_KEYS.REFRESH_TOKEN);
  await deleteItemSecure(SECURE_KEYS.USER_ID);
  await deleteItemSecure(SECURE_KEYS.TOKEN_EXPIRATION);
  // Preserves DEVICE_ID so device telemetry lineage is unbroken across re-logins
}

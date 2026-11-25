# ContextIQ Mobile Architecture & Cross-Platform Guide (Phase 5.6)

This document provides a comprehensive architectural and engineering guide for the **ContextIQ Cross-Platform Mobile Companion Application** across Android and iOS platforms.

---

## 1. Executive Invariants & Privacy Philosophy

1. **Zero Unencrypted Plaintext Token Storage**:
   Access tokens, refresh tokens, and hardware identity keys are strictly persisted using hardware-backed cryptographic vaults (`expo-secure-store`). Standard unencrypted `AsyncStorage` or `localStorage` are strictly prohibited for authentication credentials.
2. **Battery & Location Safeguards (No Continuous Background Telemetry)**:
   Unlike the ContextIQ Windows Desktop Telemetry Agent (which runs as a resident background service on mains power), the mobile companion **does not promise or attempt unrestricted continuous background telemetry**. Location access is strictly limited to foreground or user-initiated workplace geofence checks to respect mobile battery life.
3. **Cognitive Load Suppression**:
   Mobile alerts strictly honor user quiet hours and cognitive shielding rules orchestrated by the Notification Intelligence Manager.
4. **Idempotent Offline-First Synchronization**:
   Offline mutations (task creation, updates, completion, recommendation acceptance) are queued with unique idempotency keys and replayed automatically upon network reconnection.

---

## 2. Platform Comparison Matrix

| Feature | Android Architecture | iOS Architecture | ContextIQ Implementation |
| :--- | :--- | :--- | :--- |
| **Secure Token Storage** | Android Keystore & `EncryptedSharedPreferences` (AES-256 GCM) | iOS Keychain Services (`kSecAttrAccessibleAfterFirstUnlock`) | `mobile/storage/secureStore.ts` |
| **Push & Local Notifications** | Notification Channels (`NotificationChannelCompat`), Android 13+ `POST_NOTIFICATIONS` runtime permission | Apple Push Notification service (APNs), `UNUserNotificationCenter` | `mobile/services/notificationService.ts` |
| **Background Execution** | Android Doze Mode & App Standby Buckets; `WorkManager` for deferred jobs | iOS Background App Refresh & `BGTaskScheduler` (strictly throttled) | Periodic sync upon foreground resume; zero battery drain background loops |
| **Location Access** | `ACCESS_COARSE_LOCATION` / `ACCESS_FINE_LOCATION` runtime prompt | `NSLocationWhenInUseUsageDescription` (Foreground only) | `mobile/services/locationService.ts` (Foreground-only) |
| **Deep Linking** | Android Intent Filters (`contextiq://`) | Universal Links & Custom URL Scheme (`contextiq://`) | React Navigation Deep Linking Configuration |

---

## 3. Background Execution Restrictions

### A. Android Doze Mode & App Standby Buckets
- Starting with Android 6.0 (API 23), the OS introduces **Doze Mode** when the device is unplugged and stationary with the screen off.
- In Android 9.0+ (API 28), **App Standby Buckets** categorize apps into *Active*, *Working Set*, *Frequent*, *Rare*, and *Restricted*.
- **ContextIQ Architectural Decision**: The companion app executes network requests and sync operations during active foreground sessions. When background sync is needed, high-priority FCM data messages or standard OS WorkManager intervals are utilized rather than foreground services or perpetual wake-locks.

### B. iOS Background App Refresh & BGTaskScheduler
- iOS enforces aggressive process termination for background tasks that exceed 30 seconds of CPU activity.
- The `BGAppRefreshTask` is scheduled solely at iOS's discretion based on user charging habits and battery level.
- **ContextIQ Architectural Decision**: The app relies on **Event-Driven Foreground Synchronization**. Whenever the user opens or resumes the app, `useOfflineSync` immediately verifies connectivity and replays any pending queue items.

---

## 4. Notification Permissions & Channels

### Android 13+ (API 33) Runtime Permissions
- On Android 13 and above, notifications require explicit runtime consent via the `android.permission.POST_NOTIFICATIONS` permission.
- Notification channels are segmented into:
  - `focus_shield`: High-priority interruptions and focus alerts.
  - `task_reminders`: Contextual deadline and micro-delay warnings.
  - `quiet_nudge`: Low-priority behavioral reflections.

### iOS UserNotifications Authorization
- Requires requesting authorization (`alert`, `badge`, `sound`) through `UNUserNotificationCenter`.
- Notifications in quiet hours are suppressed within the notification manager on the backend and validated locally before delivery.

---

## 5. Location Capabilities & Workplace Geofencing

- **Foreground Only**: Location permissions are requested strictly with "When In Use" / foreground permissions.
- **Geofence Matching**: The app uses the **Haversine Distance Formula** against user-designated workplace coordinates registered in `/api/v1/locations`.
- If the user is within `radius_meters` (default 150m) of an active office geofence upon opening the app, ContextIQ activates the workplace focus preset and checks pending location-anchored tasks.

---

## 6. Offline Queueing & Conflict Resolution

1. **Optimistic Updates**: When the user creates or marks a task complete offline, the local cache (`mobile/storage/offlineCache.ts`) updates immediately so the UI remains instant.
2. **Action Queue**: The mutation is written to `mobile/storage/offlineQueue.ts` with an idempotency key (`action_<timestamp>_<rand>`).
3. **Replay Engine**: When online connectivity returns:
   - The queue processes in FIFO order.
   - Headers include `X-Idempotency-Key` to guarantee no duplicate tasks or double-counted bandit rewards.
   - On HTTP 409 Conflict, server state takes precedence and local cache is reconciled.

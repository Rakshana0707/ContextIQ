/**
 * Offline Cache Layer for ContextIQ Mobile (Phase 5.6 Task 8).
 * Caches recent tasks, calendar summaries, and behavioral profile summaries.
 */

interface CacheEntry<T> {
  data: T;
  cachedAt: number;
  ttlMs: number;
}

const memoryCache = new Map<string, CacheEntry<any>>();

export const CACHE_KEYS = {
  TASKS: 'cached_tasks',
  CALENDAR_EVENTS: 'cached_calendar_events',
  BEHAVIORAL_PROFILE: 'cached_behavioral_profile',
  NOTIFICATIONS: 'cached_notifications',
  RECOMMENDATIONS: 'cached_recommendations',
  USER_PROFILE: 'cached_user_profile',
};

// Default TTL: 24 hours for offline reading
const DEFAULT_TTL_MS = 24 * 60 * 60 * 1000;

export async function setCachedData<T>(key: string, data: T, ttlMs: number = DEFAULT_TTL_MS): Promise<void> {
  memoryCache.set(key, {
    data,
    cachedAt: Date.now(),
    ttlMs,
  });
}

export async function getCachedData<T>(key: string): Promise<T | null> {
  const entry = memoryCache.get(key);
  if (!entry) return null;
  const isExpired = Date.now() - entry.cachedAt > entry.ttlMs;
  if (isExpired) {
    memoryCache.delete(key);
    return null;
  }
  return entry.data as T;
}

export async function removeCachedData(key: string): Promise<void> {
  memoryCache.delete(key);
}

export async function clearAllCachedData(): Promise<void> {
  memoryCache.clear();
}

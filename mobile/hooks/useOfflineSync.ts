/**
 * Offline Synchronization Hook for ContextIQ Mobile (Phase 5.6 Task 8).
 * Manages the offline mutation queue and automatic replay when connectivity is restored.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  getPendingActions,
  markActionSynced,
  incrementActionRetry,
  QueuedAction,
} from '../storage/offlineQueue';
import { apiClient } from '../services/apiClient';

export function useOfflineSync() {
  const [pendingActions, setPendingActions] = useState<QueuedAction[]>([]);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [lastSyncResult, setLastSyncResult] = useState<{ synced: number; failed: number } | null>(null);

  const refreshQueue = useCallback(async () => {
    const items = await getPendingActions();
    setPendingActions(items);
  }, []);

  useEffect(() => {
    refreshQueue();
    // Poll queue status periodically
    const timer = setInterval(refreshQueue, 5000);
    return () => clearInterval(timer);
  }, [refreshQueue]);

  const syncNow = useCallback(async () => {
    setIsSyncing(true);
    const actions = await getPendingActions();
    let synced = 0;
    let failed = 0;

    for (const action of actions) {
      try {
        await apiClient.request(action.endpoint, {
          method: action.method,
          body: action.payload,
          headers: {
            'X-Idempotency-Key': action.id,
          },
        });
        await markActionSynced(action.id);
        synced += 1;
      } catch (err: any) {
        failed += 1;
        await incrementActionRetry(action.id, err.message || 'Sync failed');
      }
    }

    setLastSyncResult({ synced, failed });
    await refreshQueue();
    setIsSyncing(false);
  }, [refreshQueue]);

  return {
    pendingActions,
    queueLength: pendingActions.length,
    isSyncing,
    lastSyncResult,
    syncNow,
    refreshQueue,
  };
}

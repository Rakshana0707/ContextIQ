import {
  enqueueOfflineAction,
  getPendingActions,
  markActionSynced,
  incrementActionRetry,
  clearOfflineQueue,
} from '../storage/offlineQueue';
import {
  setCachedData,
  getCachedData,
  clearAllCachedData,
  CACHE_KEYS,
} from '../storage/offlineCache';

describe('Offline Storage & Safe Synchronization (Phase 5.6 Task 8)', () => {
  beforeEach(async () => {
    await clearOfflineQueue();
    await clearAllCachedData();
  });

  test('enqueues mutations with unique idempotency keys', async () => {
    const action1 = await enqueueOfflineAction('CREATE_TASK', '/tasks', 'POST', {
      title: 'Offline Design Task',
    });
    const action2 = await enqueueOfflineAction('COMPLETE_TASK', '/tasks/123', 'PATCH', {
      status: 'COMPLETED',
    });

    expect(action1.id).toBeDefined();
    expect(action2.id).toBeDefined();
    expect(action1.id).not.toBe(action2.id);

    const pending = await getPendingActions();
    expect(pending.length).toBe(2);
    expect(pending[0].actionType).toBe('CREATE_TASK');
    expect(pending[1].actionType).toBe('COMPLETE_TASK');
  });

  test('marks synced actions and handles retry increments', async () => {
    const action = await enqueueOfflineAction('CREATE_TASK', '/tasks', 'POST', { title: 'Test' });

    await incrementActionRetry(action.id, 'Network timeout');
    let pending = await getPendingActions();
    expect(pending[0].retryCount).toBe(1);
    expect(pending[0].lastError).toBe('Network timeout');

    await markActionSynced(action.id);
    pending = await getPendingActions();
    expect(pending.length).toBe(0);
  });

  test('offlineCache caches and retrieves objects within TTL', async () => {
    const sampleTasks = [
      { id: 't1', title: 'Task One', status: 'PENDING' },
      { id: 't2', title: 'Task Two', status: 'COMPLETED' },
    ];

    await setCachedData(CACHE_KEYS.TASKS, sampleTasks);
    const retrieved = await getCachedData<typeof sampleTasks>(CACHE_KEYS.TASKS);

    expect(retrieved).toEqual(sampleTasks);
    expect(retrieved?.length).toBe(2);
  });
});

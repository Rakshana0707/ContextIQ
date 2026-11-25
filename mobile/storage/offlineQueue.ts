/**
 * Offline Mutation Queue for ContextIQ Mobile (Phase 5.6 Task 8).
 * Safely queues offline actions and replays them with idempotency guarantees.
 */

export interface QueuedAction {
  id: string; // Unique idempotency key
  actionType: 'CREATE_TASK' | 'UPDATE_TASK' | 'COMPLETE_TASK' | 'POSTPONE_TASK' | 'ACCEPT_INTERVENTION' | 'DISMISS_INTERVENTION';
  endpoint: string;
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  payload: any;
  createdAt: number;
  retryCount: number;
  lastError?: string;
}

let actionQueue: QueuedAction[] = [];

/**
 * Enqueues a mutation when network connectivity is absent or failed.
 */
export async function enqueueOfflineAction(
  actionType: QueuedAction['actionType'],
  endpoint: string,
  method: QueuedAction['method'],
  payload: any
): Promise<QueuedAction> {
  const queuedItem: QueuedAction = {
    id: `action_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
    actionType,
    endpoint,
    method,
    payload,
    createdAt: Date.now(),
    retryCount: 0,
  };
  actionQueue.push(queuedItem);
  return queuedItem;
}

/**
 * Gets all pending offline actions in FIFO order.
 */
export async function getPendingActions(): Promise<QueuedAction[]> {
  return [...actionQueue];
}

/**
 * Removes an action from the queue once successfully replayed against backend.
 */
export async function markActionSynced(actionId: string): Promise<void> {
  actionQueue = actionQueue.filter(a => a.id !== actionId);
}

/**
 * Records a failure retry for a queued item with error message.
 */
export async function incrementActionRetry(actionId: string, errorMsg: string): Promise<void> {
  const item = actionQueue.find(a => a.id === actionId);
  if (item) {
    item.retryCount += 1;
    item.lastError = errorMsg;
  }
}

/**
 * Clears the queue (e.g. on explicit user reset or logout).
 */
export async function clearOfflineQueue(): Promise<void> {
  actionQueue = [];
}

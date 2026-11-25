/**
 * Mobile Task Management Service (Phase 5.6 Task 4).
 * Fully offline-capable with local optimistic updates and forgetting risk integration.
 */

import { apiClient } from './apiClient';
import { getCachedData, setCachedData, CACHE_KEYS } from '../storage/offlineCache';

export interface MobileTask {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  estimated_duration_minutes?: number | null;
  due_at?: string | null;
  created_at: string;
  updated_at: string;
  forgetting_risk?: number; // 0.0 to 1.0 probability of forgetting
}

export const taskService = {
  /**
   * Retrieves tasks from backend or offline cache fallback.
   */
  async getTasks(forceRefresh: boolean = false): Promise<MobileTask[]> {
    if (!forceRefresh) {
      const cached = await getCachedData<MobileTask[]>(CACHE_KEYS.TASKS);
      if (cached && cached.length > 0) {
        return cached;
      }
    }

    try {
      const response = await apiClient.get<MobileTask[]>('/tasks');
      const tasks = response.data;

      // Persist in offline cache
      await setCachedData(CACHE_KEYS.TASKS, tasks);
      return tasks;
    } catch (error) {
      const fallback = await getCachedData<MobileTask[]>(CACHE_KEYS.TASKS);
      if (fallback) return fallback;
      throw error;
    }
  },

  /**
   * Creates a new task with optimistic offline support.
   */
  async createTask(payload: {
    title: string;
    description?: string;
    priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
    estimated_duration_minutes?: number;
    due_at?: string;
  }): Promise<MobileTask> {
    const tempId = `temp_${Date.now()}`;
    const optimisticTask: MobileTask = {
      id: tempId,
      user_id: 'pending',
      title: payload.title,
      description: payload.description || null,
      status: 'PENDING',
      priority: payload.priority || 'MEDIUM',
      estimated_duration_minutes: payload.estimated_duration_minutes || 30,
      due_at: payload.due_at || null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    // Update local cache optimistically
    const cached = (await getCachedData<MobileTask[]>(CACHE_KEYS.TASKS)) || [];
    await setCachedData(CACHE_KEYS.TASKS, [optimisticTask, ...cached]);

    try {
      const response = await apiClient.post<MobileTask>('/tasks', payload, 'CREATE_TASK');
      // Replace optimistic task with server response
      const updatedCache = cached.filter(t => t.id !== tempId);
      await setCachedData(CACHE_KEYS.TASKS, [response.data, ...updatedCache]);
      return response.data;
    } catch {
      // Offline fallback: optimistic task stays in cache and is queued in offlineQueue
      return optimisticTask;
    }
  },

  /**
   * Updates task attributes.
   */
  async updateTask(taskId: string, updates: Partial<MobileTask>): Promise<MobileTask> {
    const cached = (await getCachedData<MobileTask[]>(CACHE_KEYS.TASKS)) || [];
    const updatedCache = cached.map(t => (t.id === taskId ? { ...t, ...updates, updated_at: new Date().toISOString() } : t));
    await setCachedData(CACHE_KEYS.TASKS, updatedCache);

    try {
      const response = await apiClient.patch<MobileTask>(`/tasks/${taskId}`, updates, 'UPDATE_TASK');
      return response.data;
    } catch {
      return updatedCache.find(t => t.id === taskId)!;
    }
  },

  /**
   * Marks a task as complete.
   */
  async completeTask(taskId: string): Promise<MobileTask> {
    return this.updateTask(taskId, { status: 'COMPLETED' });
  },

  /**
   * Postpones a task by moving its due date forward.
   */
  async postponeTask(taskId: string, newDueAt: string): Promise<MobileTask> {
    return this.updateTask(taskId, { due_at: newDueAt });
  },

  /**
   * Updates task priority tier.
   */
  async updatePriority(taskId: string, priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'): Promise<MobileTask> {
    return this.updateTask(taskId, { priority });
  },

  /**
   * Evaluates or predicts forgetting risk for a task.
   */
  async getForgettingRisk(taskId: string): Promise<{ forgetting_probability: number; is_high_risk: boolean }> {
    try {
      const response = await apiClient.get<any>(`/predictions/tasks/${taskId}`);
      const prob = response.data.forgetting_probability ?? 0.35;
      return {
        forgetting_probability: prob,
        is_high_risk: prob >= 0.7,
      };
    } catch {
      // Baseline cold-start calculation
      return {
        forgetting_probability: 0.35,
        is_high_risk: false,
      };
    }
  },
};

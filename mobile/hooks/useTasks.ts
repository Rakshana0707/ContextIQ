/**
 * Task Management Hook for ContextIQ Mobile (Phase 5.6).
 */

import { useState, useEffect, useCallback } from 'react';
import { taskService, MobileTask } from '../services/taskService';

export function useTasks() {
  const [tasks, setTasks] = useState<MobileTask[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async (forceRefresh: boolean = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await taskService.getTasks(forceRefresh);
      setTasks(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load tasks');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const createTask = useCallback(async (payload: {
    title: string;
    description?: string;
    priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
    estimated_duration_minutes?: number;
    due_at?: string;
  }) => {
    try {
      const created = await taskService.createTask(payload);
      setTasks(prev => [created, ...prev.filter(t => t.id !== created.id)]);
      return created;
    } catch (err: any) {
      setError(err.message || 'Task creation failed');
      throw err;
    }
  }, []);

  const completeTask = useCallback(async (taskId: string) => {
    try {
      await taskService.completeTask(taskId);
      setTasks(prev => prev.map(t => (t.id === taskId ? { ...t, status: 'COMPLETED' } : t)));
    } catch (err: any) {
      setError(err.message || 'Complete task failed');
      throw err;
    }
  }, []);

  const postponeTask = useCallback(async (taskId: string, newDueAt: string) => {
    try {
      await taskService.postponeTask(taskId, newDueAt);
      setTasks(prev => prev.map(t => (t.id === taskId ? { ...t, due_at: newDueAt } : t)));
    } catch (err: any) {
      setError(err.message || 'Postpone task failed');
      throw err;
    }
  }, []);

  const updatePriority = useCallback(async (taskId: string, priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT') => {
    try {
      await taskService.updatePriority(taskId, priority);
      setTasks(prev => prev.map(t => (t.id === taskId ? { ...t, priority } : t)));
    } catch (err: any) {
      setError(err.message || 'Update priority failed');
      throw err;
    }
  }, []);

  return {
    tasks,
    isLoading,
    error,
    refreshTasks: () => fetchTasks(true),
    createTask,
    completeTask,
    postponeTask,
    updatePriority,
  };
}

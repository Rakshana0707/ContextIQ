import './setup';
import { taskService } from '../services/taskService';
import { clearAllCachedData } from '../storage/offlineCache';
import { clearOfflineQueue, getPendingActions } from '../storage/offlineQueue';

describe('Task Management Service (Phase 5.6 Task 4)', () => {
  beforeEach(async () => {
    await clearAllCachedData();
    await clearOfflineQueue();
  });

  test('creates task and updates local cache', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({
        id: 'task-real-100',
        user_id: 'usr-1',
        title: 'Complete System Architecture',
        priority: 'HIGH',
        status: 'PENDING',
        estimated_duration_minutes: 60,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    });

    const task = await taskService.createTask({
      title: 'Complete System Architecture',
      priority: 'HIGH',
      estimated_duration_minutes: 60,
    });

    expect(task.title).toBe('Complete System Architecture');
    expect(task.priority).toBe('HIGH');

    // Verify cache has this task
    const allTasks = await taskService.getTasks();
    expect(allTasks.some(t => t.title === 'Complete System Architecture')).toBe(true);
  });

  test('falls back to offline optimistic task and enqueues action on network failure', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network offline'));

    const task = await taskService.createTask({
      title: 'Offline Draft Task',
      priority: 'URGENT',
      estimated_duration_minutes: 45,
    });

    expect(task.title).toBe('Offline Draft Task');
    expect(task.id).toContain('temp_');

    // Verify mutation was queued
    const pending = await getPendingActions();
    expect(pending.length).toBe(1);
    expect(pending[0].actionType).toBe('CREATE_TASK');
  });

  test('evaluates forgetting risk prediction for a task', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        task_id: 'task-100',
        forgetting_probability: 0.82,
      }),
    });

    const risk = await taskService.getForgettingRisk('task-100');
    expect(risk.forgetting_probability).toBe(0.82);
    expect(risk.is_high_risk).toBe(true);
  });
});

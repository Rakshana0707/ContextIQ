/**
 * Mobile Contextual Recommendations Service (Phase 5.6 Task 5).
 * Integrates with ContextIQ Adaptive Intelligence and Contextual Bandit Engine.
 */

import { apiClient } from './apiClient';
import { getCachedData, setCachedData, CACHE_KEYS } from '../storage/offlineCache';

export interface MobileIntervention {
  id: string;
  user_id: string;
  intervention_type: string;
  category: 'FOCUS' | 'RECOVERY' | 'TASK' | 'CONTEXTUAL' | 'WORKLOAD';
  title: string;
  message: string;
  rationale?: string | null;
  expected_outcome?: string | null;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'GENERATED' | 'PRESENTED' | 'ACCEPTED' | 'DISMISSED' | 'DEFERRED' | 'EXPIRED';
  action_payload?: Record<string, any>;
  confidence_score: number;
  expected_completion_delta?: number;
  created_at: string;
}

export const recommendationService = {
  /**
   * Retrieves active, non-expired personalized recommendations.
   */
  async getRecommendations(): Promise<MobileIntervention[]> {
    try {
      const response = await apiClient.get<MobileIntervention[]>('/adaptive/interventions?limit=10');
      const items = response.data;
      await setCachedData(CACHE_KEYS.RECOMMENDATIONS, items);
      return items;
    } catch (err) {
      const cached = await getCachedData<MobileIntervention[]>(CACHE_KEYS.RECOMMENDATIONS);
      if (cached) return cached;
      return [];
    }
  },

  /**
   * Accepts an intervention and registers positive bandit feedback.
   */
  async acceptIntervention(interventionId: string): Promise<MobileIntervention> {
    const response = await apiClient.post<MobileIntervention>(
      `/adaptive/interventions/${interventionId}/accept`,
      { execution_latency_seconds: 5 },
      'ACCEPT_INTERVENTION'
    );
    return response.data;
  },

  /**
   * Dismisses an intervention with annoyance dampening.
   */
  async dismissIntervention(interventionId: string, reason?: string): Promise<MobileIntervention> {
    const response = await apiClient.post<MobileIntervention>(
      `/adaptive/interventions/${interventionId}/dismiss`,
      { user_feedback: reason || 'Not relevant at the moment' },
      'DISMISS_INTERVENTION'
    );
    return response.data;
  },

  /**
   * Defers presentation by N minutes.
   */
  async deferIntervention(interventionId: string, deferMinutes: number = 30): Promise<MobileIntervention> {
    const deferUntil = new Date(Date.now() + deferMinutes * 60 * 1000).toISOString();
    const response = await apiClient.post<MobileIntervention>(
      `/adaptive/interventions/${interventionId}/defer`,
      { deferred_until: deferUntil },
      'DISMISS_INTERVENTION'
    );
    return response.data;
  },
};

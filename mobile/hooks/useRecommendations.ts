/**
 * Contextual Recommendations Hook for ContextIQ Mobile (Phase 5.6).
 */

import { useState, useEffect, useCallback } from 'react';
import { recommendationService, MobileIntervention } from '../services/recommendationService';

export function useRecommendations() {
  const [recommendations, setRecommendations] = useState<MobileIntervention[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRecommendations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await recommendationService.getRecommendations();
      setRecommendations(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load recommendations');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  const accept = useCallback(async (id: string) => {
    try {
      await recommendationService.acceptIntervention(id);
      setRecommendations(prev => prev.filter(r => r.id !== id));
    } catch (err: any) {
      setError(err.message || 'Accept failed');
      throw err;
    }
  }, []);

  const dismiss = useCallback(async (id: string, reason?: string) => {
    try {
      await recommendationService.dismissIntervention(id, reason);
      setRecommendations(prev => prev.filter(r => r.id !== id));
    } catch (err: any) {
      setError(err.message || 'Dismiss failed');
      throw err;
    }
  }, []);

  const defer = useCallback(async (id: string, minutes: number = 30) => {
    try {
      await recommendationService.deferIntervention(id, minutes);
      setRecommendations(prev => prev.filter(r => r.id !== id));
    } catch (err: any) {
      setError(err.message || 'Defer failed');
      throw err;
    }
  }, []);

  return {
    recommendations,
    isLoading,
    error,
    refreshRecommendations: fetchRecommendations,
    accept,
    dismiss,
    defer,
  };
}

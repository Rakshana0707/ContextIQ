/**
 * Mobile Dashboard Hook for ContextIQ Mobile (Phase 5.6).
 */

import { useState, useEffect, useCallback } from 'react';
import { dashboardService, DashboardSummary } from '../services/dashboardService';

export function useDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await dashboardService.getDashboardSummary();
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  return {
    summary,
    isLoading,
    error,
    refreshDashboard: loadDashboard,
  };
}
